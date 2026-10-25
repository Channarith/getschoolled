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

from .client_ip import client_ip
from .config import AppConfig, env_float, env_int, load_config
from .factory import ProviderFactory
from .http_cache import install as _install_http_cache, standard_registry as _std_cache_registry
from .ratelimit import RateLimit, build_rate_limiter
from .schemas import HealthStatus
from .telemetry import TelemetryStore, init_external_exporters
from .version import API_VERSION, build_info, get_version
from .safe_compare import equals as _equals


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

    import os

    import time as _time
    import uuid as _uuid

    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse, PlainTextResponse

    # ----- Rate limiting (per-IP token bucket; Redis-backed when REDIS_URL set) -
    # The default rule is intentionally generous so the platform behaves the
    # same as before for everything except egregious abuse. Tighten via env
    # (RATE_LIMIT / RATE_LIMIT_WINDOW). Bypass paths cover health/metrics so
    # liveness probes never get throttled.
    _rl_limit = env_int(os.environ.get("RATE_LIMIT"), 120)
    _rl_window = env_float(os.environ.get("RATE_LIMIT_WINDOW"), 60.0)
    _bypass_paths = (
        "/health", "/version", "/metrics", "/__meta",
        "/telemetry/summary", "/telemetry/errors", "/telemetry/logs",
        "/openapi.json", "/docs", "/redoc",
    )
    # Always build the limiter so middleware can be installed and toggled
    # at runtime via env. Disabling/enabling without restart matters for
    # test sessions and emergency throttling tweaks in production.
    app.state.rate_limiter = build_rate_limiter(RateLimit(_rl_limit, _rl_window))
    _OP_FAIL_RULE = RateLimit(env_int(os.environ.get("AOEP_OP_FAIL_LIMIT"), 10),
                              env_float(os.environ.get("AOEP_OP_FAIL_WINDOW"), 900.0))

    def _op_throttle_off() -> bool:
        return os.environ.get("RATE_LIMIT_DISABLED", "").lower() in ("1", "true", "yes") or \
            os.environ.get("AOEP_OP_THROTTLE_DISABLED", "").lower() in ("1", "true", "yes")

    @app.middleware("http")
    async def _ratelimit_mw(request: Request, call_next):
        if os.environ.get("RATE_LIMIT_DISABLED", "").lower() in ("1", "true", "yes"):
            return await call_next(request)
        limiter = app.state.rate_limiter
        # Bug 6: X-User-Id is a client-supplied header and cannot be trusted
        # for rate-limit identity — it would let any client claim any user's
        # bucket and bypass throttling.  Always use the network IP instead.
        # X-Forwarded-For is client-supplied too: take the entry our own proxy added (see client_ip).
        ident = client_ip(request.headers, request.client.host if request.client else None)
        # Operator credentials get a lockout of their own: a wrong X-Admin-Secret / X-Metrics-Token counts against the
        # caller's address and 10 misses in 15 minutes stop further guesses (the secret is a shared string, not a login).
        # This runs BEFORE the bypass list: /metrics and /telemetry/* accept those headers, so they must be covered too.
        tried_operator = bool(request.headers.get("x-admin-secret") or request.headers.get("x-metrics-token"))
        fail_key = f"{name}:opfail:{ident}"
        if tried_operator and not _op_throttle_off():
            probe = limiter.allow(fail_key, cost=0, rule=_OP_FAIL_RULE)
            if probe.remaining < 1:
                return JSONResponse({"detail": "too many failed operator credentials"}, status_code=429,
                                    headers={"Retry-After": str(int(_OP_FAIL_RULE.window))})
        if request.url.path in _bypass_paths:
            response = await call_next(request)
            if tried_operator and response.status_code in (401, 403) and not _op_throttle_off():
                limiter.allow(fail_key, cost=1, rule=_OP_FAIL_RULE)
            return response
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
        if tried_operator and response.status_code in (401, 403) and not _op_throttle_off():
            limiter.allow(fail_key, cost=1, rule=_OP_FAIL_RULE)
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

    class _SessionCookieAuth:
        """Copy the HttpOnly session cookie into Authorization for existing deps."""

        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope.get("type") == "http":
                headers = list(scope.get("headers") or [])
                has_auth = any(key == b"authorization" for key, _ in headers)
                token = ""
                if not has_auth:
                    for key, value in headers:
                        if key != b"cookie":
                            continue
                        for part in value.decode("latin1").split(";"):
                            name, _, raw = part.strip().partition("=")
                            if name == "aoep_session" and raw:
                                token = raw
                    if token:
                        headers.append((b"authorization", f"Bearer {token}".encode()))
                        scope = dict(scope)
                        scope["headers"] = headers
            await self.app(scope, receive, send)

    app.add_middleware(_SessionCookieAuth)

    # The browser web app calls services cross-origin during local dev.
    # Cookie auth needs an explicit origin list; "*" cannot send credentials.
    #
    # Added LAST so CORS is the OUTERMOST middleware (add_middleware prepends):
    # short-circuit responses from inner middleware — rate-limit 429s in
    # particular — must still carry Access-Control-Allow-Origin, or browsers
    # surface them as opaque CORS failures instead of handleable errors.
    from fastapi.middleware.cors import CORSMiddleware

    _deploy_mode = os.environ.get("DEPLOY_MODE", "local").lower()
    _cors_env = os.environ.get("CORS_ORIGINS", "")
    if _cors_env:
        origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
    elif _deploy_mode in ("local", "dev", "debug", "test"):
        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
        ]
    else:
        origins = ["https://salareen.com", "https://www.salareen.com"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    from fastapi import Request
    globals()["Request"] = Request

    def _require_ops(request: Request):
        """Lock metrics and error logs outside local deploys."""

        from fastapi import HTTPException

        deploy = os.environ.get("DEPLOY_MODE", "local").lower()
        if deploy in ("local", "dev", "development", "debug", "test"):
            return
        from .internal_auth import is_internal_caller

        presented = request.headers.get("x-internal-token") or ""
        admin = request.headers.get("x-admin-secret") or ""
        metrics_token = request.headers.get("x-metrics-token") or ""
        expected_admin = os.environ.get("ADMIN_SECRET") or ""
        expected_metrics = os.environ.get("METRICS_TOKEN") or ""
        if is_internal_caller(presented):
            return
        if expected_admin and _equals(admin, expected_admin):
            return
        if expected_metrics and _equals(metrics_token, expected_metrics):
            return
        raise HTTPException(status_code=401, detail="operator credential required")

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics(request: Request):
        """Prometheus exposition (scrape target for local + cloud monitoring)."""
        _require_ops(request)
        return PlainTextResponse(app.state.telemetry.prometheus_text(),
                                 media_type="text/plain; version=0.0.4")

    @app.get("/telemetry/summary")
    def telemetry_summary(request: Request) -> dict:
        """Performance + memory/runtime + error/log counts (JSON for the admin UI)."""
        _require_ops(request)
        return app.state.telemetry.summary()

    @app.get("/telemetry/errors")
    def telemetry_errors(request: Request, limit: int = 50) -> dict:
        """Recent exceptions w/ traceback + request context for root-cause analysis."""
        _require_ops(request)
        return {"service": name, "errors": app.state.telemetry.recent_errors(limit)}

    @app.get("/telemetry/logs")
    def telemetry_logs(request: Request, limit: int = 100, level: str | None = None) -> dict:
        """Recent structured events/log ring buffer."""
        _require_ops(request)
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
