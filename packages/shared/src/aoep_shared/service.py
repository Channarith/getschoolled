"""Shared FastAPI service scaffolding.

Every Python service builds its app through :func:`create_service` so they all
expose a consistent ``/health`` that reports the deploy mode and the effective
local/cloud implementation chosen for each component.

FastAPI is an optional import: the rest of aoep_shared (config, factory,
providers, entitlements, rag) has no web dependency and can be unit-tested
without FastAPI installed.
"""

from __future__ import annotations

from typing import Optional

from .config import AppConfig, load_config
from .factory import ProviderFactory
from .http_cache import install as _install_http_cache, standard_registry as _std_cache_registry
from .ratelimit import RateLimit, build_rate_limiter
from .schemas import HealthStatus
from .telemetry import TelemetryStore, init_external_exporters
from .version import API_VERSION, build_info, get_version


def create_service(
    name: str,
    *,
    config: Optional[AppConfig] = None,
    factory: Optional[ProviderFactory] = None,
):
    """Create a FastAPI app for ``name`` with a standard ``/health`` route."""
    from fastapi import FastAPI  # local import keeps web dep optional

    cfg = config or load_config()
    fac = factory or ProviderFactory(cfg)

    app = FastAPI(title=f"AOEP {name}", version=get_version())
    app.state.config = cfg
    app.state.factory = fac
    app.state.telemetry = TelemetryStore(name)
    # Best-effort external exporters (Sentry/OTLP) when configured + installed.
    init_external_exporters(name)

    # The browser web app calls services cross-origin during local dev. Allow
    # configured origins (comma-separated CORS_ORIGINS); default to "*" for the
    # local stack. Phase10 hardening tightens this for cloud.
    import os

    from fastapi.middleware.cors import CORSMiddleware

    origins_raw = os.environ.get("CORS_ORIGINS", "*")
    origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    import time as _time
    import uuid as _uuid

    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse, PlainTextResponse

    # ----- Rate limiting (per-IP token bucket; Redis-backed when REDIS_URL set) -
    # The default rule is intentionally generous so the platform behaves the
    # same as before for everything except egregious abuse. Tighten via env
    # (RATE_LIMIT / RATE_LIMIT_WINDOW). Bypass paths cover health/metrics so
    # liveness probes never get throttled.
    _rl_limit = int(os.environ.get("RATE_LIMIT", "120"))
    _rl_window = float(os.environ.get("RATE_LIMIT_WINDOW", "60"))
    _bypass_paths = (
        "/health", "/version", "/metrics", "/__meta",
        "/telemetry/summary", "/telemetry/errors", "/telemetry/logs",
        "/openapi.json", "/docs", "/redoc",
    )
    # Always build the limiter so middleware can be installed and toggled
    # at runtime via env. Disabling/enabling without restart matters for
    # test sessions and emergency throttling tweaks in production.
    app.state.rate_limiter = build_rate_limiter(RateLimit(_rl_limit, _rl_window))

    @app.middleware("http")
    async def _ratelimit_mw(request: Request, call_next):
        if os.environ.get("RATE_LIMIT_DISABLED", "").lower() in ("1", "true", "yes"):
            return await call_next(request)
        if request.url.path in _bypass_paths:
            return await call_next(request)
        limiter = app.state.rate_limiter
        # Prefer authenticated principal (X-User-Id) over IP so a single
        # logged-in user sharing a CGNAT egress doesn't share the bucket
        # with strangers.
        ident = (
            request.headers.get("x-user-id")
            or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "anon")
        )
        decision = limiter.allow(f"{name}:{ident}")
        if not decision.allowed:
            resp = JSONResponse(
                {"detail": "rate limit exceeded", "retry_after": round(decision.retry_after_seconds, 2)},
                status_code=429,
            )
            resp.headers["Retry-After"] = str(int(decision.retry_after_seconds + 0.999))
            resp.headers["X-RateLimit-Limit"] = str(decision.limit)
            resp.headers["X-RateLimit-Remaining"] = "0"
            return resp
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(int(decision.remaining))
        return response

    # ----- HTTP cache (Cache-Control + ETag) for hot read endpoints -----------
    if os.environ.get("HTTP_CACHE_DISABLED", "").lower() not in ("1", "true", "yes"):
        _install_http_cache(app, _std_cache_registry(), etag=True)
    _ = HTTPException  # silence unused-import warning when callers don't raise here

    @app.middleware("http")
    async def _telemetry_mw(request: Request, call_next):
        tel: TelemetryStore = app.state.telemetry
        # Route template (e.g. /courses/{id}) keeps cardinality bounded.
        route = request.url.path
        method = request.method
        rid = request.headers.get("x-request-id") or _uuid.uuid4().hex[:16]
        start = _time.perf_counter()
        tel.inc_inflight()
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001 - record then re-raise (-> 500)
            ms = (_time.perf_counter() - start) * 1000.0
            matched = request.scope.get("route")
            tmpl = getattr(matched, "path", route)
            tel.record_error(route=tmpl, method=method, exc=exc, request_id=rid)
            tel.observe_request(tmpl, method, 500, ms)
            tel.dec_inflight()
            raise
        ms = (_time.perf_counter() - start) * 1000.0
        tel.dec_inflight()
        matched = request.scope.get("route")
        tmpl = getattr(matched, "path", route)
        tel.observe_request(tmpl, method, response.status_code, ms)
        if response.status_code >= 500:
            tel.record_error(
                route=tmpl, method=method,
                exc=RuntimeError(f"{response.status_code} response"),
                request_id=rid, status=response.status_code)
        response.headers["X-Request-ID"] = rid
        response.headers["Server-Timing"] = f"app;dur={ms:.1f}"
        return response

    @app.get("/health", response_model=HealthStatus)
    def health() -> HealthStatus:  # pragma: no cover - exercised via TestClient
        return HealthStatus(
            service=name,
            status="ok",
            deploy_mode=cfg.deploy_mode.value,
            components=fac.component_summary(),
            version=get_version(),
        )

    @app.get("/version")
    def version() -> dict:
        """Version + build metadata. Standard on every service for automation."""
        return {"service": name, "deploy_mode": cfg.deploy_mode.value, **build_info()}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics():
        """Prometheus exposition (scrape target for local + cloud monitoring)."""
        return PlainTextResponse(app.state.telemetry.prometheus_text(),
                                 media_type="text/plain; version=0.0.4")

    @app.get("/telemetry/summary")
    def telemetry_summary() -> dict:
        """Performance + memory/runtime + error/log counts (JSON for the admin UI)."""
        return app.state.telemetry.summary()

    @app.get("/telemetry/errors")
    def telemetry_errors(limit: int = 50) -> dict:
        """Recent exceptions w/ traceback + request context for root-cause analysis."""
        return {"service": name, "errors": app.state.telemetry.recent_errors(limit)}

    @app.get("/telemetry/logs")
    def telemetry_logs(limit: int = 100, level: str | None = None) -> dict:
        """Recent structured events/log ring buffer."""
        return {"service": name, "events": app.state.telemetry.recent_events(limit, level)}

    @app.get("/__meta")
    def meta() -> dict:
        """Machine-readable endpoint index for automation/test discovery.

        Lists every route (methods + path) the service exposes, complementing
        /openapi.json with a compact, stable shape that test harnesses can crawl.
        """
        routes = []
        for r in app.router.routes:
            path = getattr(r, "path", None)
            methods = getattr(r, "methods", None)
            if not path or methods is None:
                continue
            verbs = sorted(m for m in methods if m not in ("HEAD", "OPTIONS"))
            if verbs:
                routes.append({"path": path, "methods": verbs})
        routes.sort(key=lambda x: x["path"])
        return {
            "service": name,
            "version": get_version(),
            "api_version": API_VERSION,
            "route_count": len(routes),
            "routes": routes,
            "openapi": "/openapi.json",
        }

    return app
