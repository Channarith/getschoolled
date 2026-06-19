#!/usr/bin/env python3
"""API stress / performance / quality harness (dependency-free, stdlib only).

Exercises the platform's HTTP services under concurrency and reports, per
scenario:
  - functional correctness (expected status + optional response-body check) -> QUALITY
  - latency p50 / p95 / p99 / max (ms)                                       -> SPEED
  - throughput (req/s) and error rate                                        -> PERFORMANCE

It probes each service's /health first and SKIPS unavailable services, so it
runs against whatever is up (local dev, compose, or a staging URL). Exit code is
non-zero when an SLA threshold is breached, so it doubles as a regression gate.

Usage:
  python3 qa/stress.py --orchestrator-url http://localhost:8000 \
      --curriculum-url http://localhost:8005 --concurrency 16 --requests 300
  python3 qa/stress.py --smoke           # 1 request per scenario, gentle
  python3 qa/stress.py --json out.json   # machine-readable report
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
@dataclass
class Response:
    status: int
    body: bytes
    elapsed_ms: float
    error: Optional[str] = None

    def json(self) -> dict:
        try:
            return json.loads(self.body.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {}


def http_request(method: str, url: str, *, body: Optional[dict] = None,
                 timeout: float = 10.0) -> Response:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
            return Response(resp.status, payload, (time.perf_counter() - start) * 1000.0)
    except urllib.error.HTTPError as exc:
        return Response(exc.code, exc.read() or b"", (time.perf_counter() - start) * 1000.0)
    except Exception as exc:  # noqa: BLE001 - connection refused / timeout / etc.
        return Response(0, b"", (time.perf_counter() - start) * 1000.0, error=str(exc))


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #
@dataclass
class Scenario:
    name: str
    method: str
    path: str
    body: Optional[dict] = None
    # body_fn(context) -> dict, for per-request dynamic bodies (e.g. a session id)
    body_fn: Optional[Callable[[dict], dict]] = None
    expect_status: int = 200
    # A predicate over the parsed JSON response asserting QUALITY/correctness.
    check: Optional[Callable[[dict], bool]] = None


@dataclass
class ScenarioResult:
    name: str
    requests: int
    errors: int
    functional_failures: int
    latencies_ms: List[float] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        return self.errors / self.requests if self.requests else 0.0

    @property
    def functional_pass_rate(self) -> float:
        ok = self.requests - self.functional_failures
        return ok / self.requests if self.requests else 0.0

    def pct(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        return percentile(self.latencies_ms, p)

    def rps(self, wall_s: float) -> float:
        return self.requests / wall_s if wall_s > 0 else 0.0


def percentile(values: List[float], p: float) -> float:
    """Linear-interpolated percentile (p in 0..100)."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def run_scenario(base_url: str, scenario: Scenario, *, concurrency: int,
                 total: int, context: Optional[dict] = None,
                 timeout: float = 10.0) -> ScenarioResult:
    context = context or {}
    result = ScenarioResult(name=scenario.name, requests=0, errors=0, functional_failures=0)
    url = base_url.rstrip("/") + scenario.path

    def one() -> Response:
        body = scenario.body
        if scenario.body_fn is not None:
            body = scenario.body_fn(context)
        return http_request(scenario.method, url, body=body, timeout=timeout)

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(one) for _ in range(total)]
        for fut in as_completed(futures):
            resp = fut.result()
            result.requests += 1
            result.latencies_ms.append(resp.elapsed_ms)
            if resp.error or resp.status == 0:
                result.errors += 1
                result.functional_failures += 1
                continue
            ok = resp.status == scenario.expect_status
            if ok and scenario.check is not None:
                try:
                    ok = bool(scenario.check(resp.json()))
                except Exception:  # noqa: BLE001
                    ok = False
            if not ok:
                result.functional_failures += 1
            if not (200 <= resp.status < 500):
                # 5xx counts as a server error for the error rate.
                result.errors += 1
    return result


# --------------------------------------------------------------------------- #
# Service scenario builders (probe /health, then exercise key endpoints)
# --------------------------------------------------------------------------- #
def service_available(base_url: str) -> bool:
    return http_request("GET", base_url.rstrip("/") + "/health", timeout=3.0).status == 200


def common_scenarios() -> List[Scenario]:
    """Scenarios every service exposes (via create_service) - smoke + discovery."""
    return [
        Scenario("health", "GET", "/health", check=lambda j: j.get("status") == "ok"),
        Scenario("version", "GET", "/version", check=lambda j: bool(j.get("version"))),
        Scenario("meta", "GET", "/__meta", check=lambda j: j.get("route_count", 0) >= 1),
    ]


def orchestrator_scenarios(base_url: str) -> tuple[List[Scenario], dict]:
    """Build orchestrator scenarios; set up a session for the ask path."""
    context: dict = {}
    # Setup: pick a lesson and start a session (so the ask scenario is realistic).
    lessons = http_request("GET", base_url.rstrip("/") + "/api/lessons").json()
    if isinstance(lessons, list) and lessons:
        lid = lessons[0]["lesson_id"]
        sess = http_request("POST", base_url.rstrip("/") + "/api/sessions",
                            body={"lesson_id": lid, "class_type": "group"}).json()
        context["session_id"] = (sess.get("session") or {}).get("session_id")

    scenarios = [
        *common_scenarios(),
        Scenario("disclosure", "GET", "/api/disclosure", check=lambda j: j.get("is_ai") is True),
        Scenario("lessons", "GET", "/api/lessons", check=lambda j: isinstance(j, list)),
        Scenario("embody", "POST", "/api/embody", body={"text": "Welcome", "gesture": "wave"},
                 check=lambda j: len(j.get("actions", [])) >= 1),
    ]
    if context.get("session_id"):
        scenarios.append(Scenario(
            "ask", "POST", f"/api/sessions/{context['session_id']}/ask",
            body={"text": "What is a fraction?", "language": "en"},
            check=lambda j: bool(j.get("text")),
        ))
    return scenarios, context


def curriculum_scenarios(base_url: str) -> tuple[List[Scenario], dict]:
    # Discover a course id so the ad-breaks scenario is realistic.
    context: dict = {}
    courses = http_request("GET", base_url.rstrip("/") + "/courses/search").json()
    if isinstance(courses, list) and courses:
        context["course_id"] = courses[0].get("course_id")

    scenarios = [
        *common_scenarios(),
        Scenario("validate_claim", "POST", "/validate/claim",
                 body={"text": "plants release oxygen during photosynthesis"},
                 check=lambda j: j.get("status") in ("supported", "unverified", "contradicted")),
        Scenario("catalog", "GET", "/catalog", check=lambda j: "courses" in j),
        Scenario("courses_search", "GET", "/courses/search", check=lambda j: isinstance(j, list)),
        Scenario("catalog_export", "GET", "/catalog/export?format=json",
                 check=lambda j: "titles" in j),
        Scenario("authorship", "POST", "/homework/authorship",
                 body={"text": "Plants make glucose. Cells use oxygen for energy."},
                 check=lambda j: j.get("label") in ("ai", "human", "uncertain")),
    ]
    if context.get("course_id"):
        scenarios.append(Scenario(
            "ad_breaks", "GET", f"/courses/{context['course_id']}/ad-breaks?tier=free",
            check=lambda j: "breaks" in j,
        ))
    return scenarios, context


def integrations_scenarios(base_url: str) -> tuple[List[Scenario], dict]:
    scenarios = [
        *common_scenarios(),
        Scenario("create_client", "POST", "/clients",
                 body={"name": "stress", "scopes": ["catalog:read"]},
                 check=lambda j: str(j.get("api_key", "")).startswith("aoep_")),
        Scenario("notify", "POST", "/notify", body={"channel": "#qa", "text": "stress"},
                 check=lambda j: j.get("ok") is True),
    ]
    return scenarios, {}


def memory_scenarios(base_url: str) -> tuple[List[Scenario], dict]:
    scenarios = [
        *common_scenarios(),
        Scenario("flags_evaluate", "GET", "/flags/evaluate?tier=free",
                 check=lambda j: isinstance(j.get("flags"), dict)),
        Scenario("survey_template", "GET", "/survey/post-class",
                 check=lambda j: "enabled" in j),
        Scenario("legal_notices", "GET", "/legal/notices",
                 check=lambda j: isinstance(j.get("notices"), list)),
        Scenario("compliance", "GET", "/compliance/us",
                 check=lambda j: isinstance(j, dict)),
    ]
    return scenarios, {}


def identity_scenarios(base_url: str) -> tuple[List[Scenario], dict]:
    import time as _t

    scenarios = [
        *common_scenarios(),
        Scenario("rewards_catalog", "GET", "/rewards/catalog",
                 check=lambda j: isinstance(j, (list, dict))),
        Scenario("signup", "POST", "/auth/signup",
                 body_fn=lambda ctx: {
                     "email": f"stress+{_t.time_ns()}@example.com",
                     "password": "pw-stress-123", "display_name": "Stress"},
                 check=lambda j: bool(j.get("token") or j.get("account"))),
    ]
    return scenarios, {}


def generic_scenarios(base_url: str) -> tuple[List[Scenario], dict]:
    """For services we only smoke (health/version/meta) - billing/speech/perception."""
    return common_scenarios(), {}


SERVICES = {
    "orchestrator": orchestrator_scenarios,
    "speech": generic_scenarios,
    "perception": generic_scenarios,
    "memory": memory_scenarios,
    "curriculum": curriculum_scenarios,
    "billing": generic_scenarios,
    "integrations": integrations_scenarios,
    "identity": identity_scenarios,
}


# --------------------------------------------------------------------------- #
# Runner + reporting
# --------------------------------------------------------------------------- #
def run(base_urls: Dict[str, str], *, concurrency: int, total: int,
        timeout: float = 10.0) -> dict:
    report: dict = {"services": {}, "started_at": time.time()}
    for svc, builder in SERVICES.items():
        base = base_urls.get(svc)
        if not base:
            continue
        if not service_available(base):
            report["services"][svc] = {"available": False}
            continue
        scenarios, context = builder(base)
        svc_report = {"available": True, "base_url": base, "scenarios": {}}
        for sc in scenarios:
            wall_start = time.perf_counter()
            res = run_scenario(base, sc, concurrency=concurrency, total=total,
                               context=context, timeout=timeout)
            wall = time.perf_counter() - wall_start
            svc_report["scenarios"][sc.name] = {
                "requests": res.requests,
                "error_rate": round(res.error_rate, 4),
                "functional_pass_rate": round(res.functional_pass_rate, 4),
                "p50_ms": round(res.pct(50), 2),
                "p95_ms": round(res.pct(95), 2),
                "p99_ms": round(res.pct(99), 2),
                "max_ms": round(max(res.latencies_ms) if res.latencies_ms else 0.0, 2),
                "rps": round(res.rps(wall), 1),
            }
        report["services"][svc] = svc_report
    report["finished_at"] = time.time()
    return report


def evaluate(report: dict, *, max_error_rate: float, max_p95_ms: float,
             min_functional: float) -> List[str]:
    """Return a list of SLA breaches (empty = pass)."""
    breaches: List[str] = []
    for svc, sr in report["services"].items():
        if not sr.get("available"):
            continue
        for name, s in sr["scenarios"].items():
            tag = f"{svc}.{name}"
            if s["error_rate"] > max_error_rate:
                breaches.append(f"{tag}: error_rate {s['error_rate']} > {max_error_rate}")
            if s["functional_pass_rate"] < min_functional:
                breaches.append(f"{tag}: functional_pass {s['functional_pass_rate']} < {min_functional}")
            if s["p95_ms"] > max_p95_ms:
                breaches.append(f"{tag}: p95 {s['p95_ms']}ms > {max_p95_ms}ms")
    return breaches


def print_report(report: dict) -> None:
    print(f"\n{'SERVICE.SCENARIO':<34}{'REQ':>6}{'ERR%':>7}{'FUNC%':>7}{'p50':>8}{'p95':>8}{'p99':>8}{'RPS':>9}")
    print("-" * 87)
    for svc, sr in report["services"].items():
        if not sr.get("available"):
            print(f"{svc:<34}{'(unavailable - skipped)':>53}")
            continue
        for name, s in sr["scenarios"].items():
            print(f"{svc + '.' + name:<34}{s['requests']:>6}{s['error_rate'] * 100:>6.1f}"
                  f"{s['functional_pass_rate'] * 100:>7.1f}{s['p50_ms']:>8.1f}{s['p95_ms']:>8.1f}"
                  f"{s['p99_ms']:>8.1f}{s['rps']:>9.1f}")
    print()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--orchestrator-url", default="http://localhost:8000")
    ap.add_argument("--speech-url", default="http://localhost:8002")
    ap.add_argument("--perception-url", default="http://localhost:8003")
    ap.add_argument("--memory-url", default="http://localhost:8004")
    ap.add_argument("--curriculum-url", default="http://localhost:8005")
    ap.add_argument("--billing-url", default="http://localhost:8006")
    ap.add_argument("--integrations-url", default="http://localhost:8007")
    ap.add_argument("--identity-url", default="http://localhost:8008")
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--requests", type=int, default=300, help="requests per scenario")
    ap.add_argument("--smoke", action="store_true", help="1 light pass per scenario")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--max-error-rate", type=float, default=0.01)
    ap.add_argument("--max-p95-ms", type=float, default=1500.0)
    ap.add_argument("--min-functional", type=float, default=0.99)
    ap.add_argument("--json", default=None, help="write the JSON report to this path")
    args = ap.parse_args(argv)

    concurrency = 2 if args.smoke else args.concurrency
    total = 4 if args.smoke else args.requests

    base_urls = {
        "orchestrator": args.orchestrator_url,
        "speech": args.speech_url,
        "perception": args.perception_url,
        "memory": args.memory_url,
        "curriculum": args.curriculum_url,
        "billing": args.billing_url,
        "integrations": args.integrations_url,
        "identity": args.identity_url,
    }
    report = run(base_urls, concurrency=concurrency, total=total, timeout=args.timeout)
    print_report(report)

    breaches = evaluate(report, max_error_rate=args.max_error_rate,
                        max_p95_ms=args.max_p95_ms, min_functional=args.min_functional)
    report["breaches"] = breaches
    report["passed"] = not breaches

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"report written to {args.json}")

    any_available = any(s.get("available") for s in report["services"].values())
    if not any_available:
        print("WARNING: no services were reachable; nothing was stressed.")
        return 0  # not a failure of the harness itself
    if breaches:
        print("SLA BREACHES:")
        for b in breaches:
            print(f"  - {b}")
        return 1
    print("All scenarios passed SLA (functional + error-rate + p95).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
