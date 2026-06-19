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

    from fastapi import Request
    from fastapi.responses import PlainTextResponse

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
