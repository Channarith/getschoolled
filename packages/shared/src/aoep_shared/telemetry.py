"""In-process telemetry: performance, memory, errors, logs (local + cloud).

Dependency-free observability so every service can report:
- performance  : per-route request counts, latency (p50/p95/p99), in-flight, RPS-ish
- memory/runtime: resident memory (RSS), CPU time, GC counts, thread count, uptime
- bugs/errors  : a ring buffer of recent exceptions with traceback + request context
                 (for root-cause analysis), plus error rate per route
- logs         : a ring buffer of recent structured events / access log

It exposes a Prometheus text exposition (``/metrics``) for scraping by the cloud
stack (Prometheus/Grafana) and JSON summaries (``/telemetry/*``) the admin UI can
aggregate. Optional Sentry/OTLP export is enabled by env only when the library is
present, so the offline/local stack keeps working with zero extra dependencies.

Read by services through ``create_service`` (middleware + endpoints).
"""

from __future__ import annotations

import gc
import os
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

_MAX_LAT_SAMPLES = 1024
_MAX_ERRORS = 200
_MAX_EVENTS = 500


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _status_bucket(status: int) -> str:
    return f"{status // 100}xx"


@dataclass
class RouteStat:
    count: int = 0
    errors: int = 0                       # 5xx + unhandled
    status: Dict[str, int] = field(default_factory=dict)
    latencies_ms: Deque[float] = field(default_factory=lambda: deque(maxlen=_MAX_LAT_SAMPLES))
    last_ms: float = 0.0

    def observe(self, status_code: int, ms: float) -> None:
        self.count += 1
        self.last_ms = ms
        self.latencies_ms.append(ms)
        b = _status_bucket(status_code)
        self.status[b] = self.status.get(b, 0) + 1
        if status_code >= 500:
            self.errors += 1

    def perf(self) -> Dict[str, float]:
        lat = list(self.latencies_ms)
        return {
            "count": self.count,
            "errors": self.errors,
            "p50_ms": round(_percentile(lat, 50), 2),
            "p95_ms": round(_percentile(lat, 95), 2),
            "p99_ms": round(_percentile(lat, 99), 2),
            "max_ms": round(max(lat), 2) if lat else 0.0,
            "last_ms": round(self.last_ms, 2),
            "error_rate": round(self.errors / self.count, 4) if self.count else 0.0,
        }


def process_metrics() -> Dict[str, float]:
    """Runtime/memory metrics from stdlib only (Linux /proc, fallbacks elsewhere)."""
    rss_mb = 0.0
    try:  # Linux container path (local + cloud)
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    rss_mb = round(int(line.split()[1]) / 1024.0, 1)
                    break
    except OSError:
        try:
            import resource

            ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # ru_maxrss is KB on Linux, bytes on macOS.
            rss_mb = round(ru / 1024.0, 1) if ru > 1_000_000 else round(ru / 1024.0, 1)
        except Exception:  # noqa: BLE001
            rss_mb = 0.0

    times = os.times()
    counts = gc.get_count()
    return {
        "rss_mb": rss_mb,
        "cpu_user_s": round(times.user, 2),
        "cpu_system_s": round(times.system, 2),
        "threads": threading.active_count(),
        "gc_gen0": counts[0],
        "gc_gen1": counts[1],
        "gc_gen2": counts[2],
        "gc_objects": len(gc.get_objects()),
    }


class TelemetryStore:
    """Per-service telemetry: perf, errors, events, in-flight, uptime."""

    def __init__(self, service: str) -> None:
        self.service = service
        self.started_at = time.time()
        self._routes: Dict[str, RouteStat] = {}
        self._errors: Deque[dict] = deque(maxlen=_MAX_ERRORS)
        self._events: Deque[dict] = deque(maxlen=_MAX_EVENTS)
        self._inflight = 0
        self._total_requests = 0
        self._lock = threading.Lock()

    # -- request lifecycle ------------------------------------------------- #
    def inc_inflight(self) -> None:
        with self._lock:
            self._inflight += 1

    def dec_inflight(self) -> None:
        with self._lock:
            self._inflight = max(0, self._inflight - 1)

    def observe_request(self, route: str, method: str, status: int, ms: float) -> None:
        key = f"{method} {route}"
        with self._lock:
            self._total_requests += 1
            self._routes.setdefault(key, RouteStat()).observe(status, ms)

    def record_error(self, *, route: str, method: str, exc: BaseException,
                     request_id: str = "", status: int = 500) -> None:
        with self._lock:
            self._errors.append({
                "ts": time.time(),
                "route": route,
                "method": method,
                "status": status,
                "type": type(exc).__name__,
                "message": str(exc)[:500],
                "traceback": "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__))[-4000:],
                "request_id": request_id,
            })

    def event(self, level: str, message: str, **fields) -> None:
        with self._lock:
            self._events.append({"ts": time.time(), "level": level,
                                 "message": message, **fields})

    # -- reporting --------------------------------------------------------- #
    def uptime_s(self) -> float:
        return round(time.time() - self.started_at, 1)

    def totals(self) -> dict:
        with self._lock:
            total = self._total_requests
            errs = sum(r.errors for r in self._routes.values())
        return {
            "requests": total,
            "errors": errs,
            "error_rate": round(errs / total, 4) if total else 0.0,
            "inflight": self._inflight,
        }

    def routes_perf(self) -> Dict[str, dict]:
        with self._lock:
            return {k: v.perf() for k, v in self._routes.items()}

    def recent_errors(self, limit: int = 50) -> List[dict]:
        with self._lock:
            return list(self._errors)[-limit:][::-1]

    def recent_events(self, limit: int = 100, level: Optional[str] = None) -> List[dict]:
        with self._lock:
            evs = list(self._events)
        if level:
            evs = [e for e in evs if e.get("level") == level]
        return evs[-limit:][::-1]

    def summary(self) -> dict:
        return {
            "service": self.service,
            "uptime_s": self.uptime_s(),
            "process": process_metrics(),
            "totals": self.totals(),
            "routes": self.routes_perf(),
            "error_count": len(self._errors),
            "event_count": len(self._events),
            "exporters": detect_exporters(),
        }

    # -- Prometheus exposition -------------------------------------------- #
    def prometheus_text(self) -> str:
        svc = self.service
        lines: List[str] = []

        def esc(v: str) -> str:
            return v.replace("\\", "\\\\").replace('"', '\\"')

        proc = process_metrics()
        lines.append("# HELP aoep_process_resident_memory_mb Resident memory (MB).")
        lines.append("# TYPE aoep_process_resident_memory_mb gauge")
        lines.append(f'aoep_process_resident_memory_mb{{service="{svc}"}} {proc["rss_mb"]}')
        lines.append("# HELP aoep_process_uptime_seconds Process uptime.")
        lines.append("# TYPE aoep_process_uptime_seconds gauge")
        lines.append(f'aoep_process_uptime_seconds{{service="{svc}"}} {self.uptime_s()}')
        lines.append("# HELP aoep_process_threads Active threads.")
        lines.append("# TYPE aoep_process_threads gauge")
        lines.append(f'aoep_process_threads{{service="{svc}"}} {proc["threads"]}')
        lines.append("# HELP aoep_process_cpu_seconds_total CPU seconds (user+sys).")
        lines.append("# TYPE aoep_process_cpu_seconds_total counter")
        lines.append(f'aoep_process_cpu_seconds_total{{service="{svc}"}} '
                     f'{proc["cpu_user_s"] + proc["cpu_system_s"]}')
        lines.append("# HELP aoep_inflight_requests In-flight HTTP requests.")
        lines.append("# TYPE aoep_inflight_requests gauge")
        lines.append(f'aoep_inflight_requests{{service="{svc}"}} {self._inflight}')

        lines.append("# HELP aoep_requests_total HTTP requests by route/method/status class.")
        lines.append("# TYPE aoep_requests_total counter")
        lines.append("# HELP aoep_request_latency_ms Request latency quantiles (ms).")
        lines.append("# TYPE aoep_request_latency_ms gauge")
        with self._lock:
            routes = dict(self._routes)
        for key, rs in routes.items():
            method, _, route = key.partition(" ")
            for bucket, n in rs.status.items():
                lines.append(
                    f'aoep_requests_total{{service="{svc}",route="{esc(route)}",'
                    f'method="{esc(method)}",status="{bucket}"}} {n}')
            lat = list(rs.latencies_ms)
            for q in (50, 95, 99):
                lines.append(
                    f'aoep_request_latency_ms{{service="{svc}",route="{esc(route)}",'
                    f'method="{esc(method)}",quantile="0.{q}"}} {round(_percentile(lat, q), 2)}')
        return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Optional external exporters (enabled by env only when the lib is installed).
# --------------------------------------------------------------------------- #
def detect_exporters() -> Dict[str, bool]:
    """Report which external observability exporters are configured + available."""
    out = {"sentry": False, "otlp": False}
    if os.environ.get("SENTRY_DSN"):
        try:
            import sentry_sdk  # noqa: F401
            out["sentry"] = True
        except Exception:  # noqa: BLE001
            out["sentry"] = False
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        try:
            import opentelemetry  # noqa: F401
            out["otlp"] = True
        except Exception:  # noqa: BLE001
            out["otlp"] = False
    return out


def init_external_exporters(service: str) -> Dict[str, bool]:
    """Best-effort init of Sentry/OTLP when configured AND installed; else no-op.

    Cloud deployments set SENTRY_DSN / OTEL_EXPORTER_OTLP_ENDPOINT and install the
    optional libs; local/offline runs leave them unset and this is a no-op.
    """
    status = {"sentry": False, "otlp": False}
    dsn = os.environ.get("SENTRY_DSN")
    if dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=dsn, traces_sample_rate=float(
                os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")))
            sentry_sdk.set_tag("service", service)
            status["sentry"] = True
        except Exception:  # noqa: BLE001
            status["sentry"] = False
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        # Real OTLP wiring is done by the opentelemetry distro if installed; we
        # only report availability here to avoid a hard dependency.
        try:
            import opentelemetry  # noqa: F401
            status["otlp"] = True
        except Exception:  # noqa: BLE001
            status["otlp"] = False
    return status
