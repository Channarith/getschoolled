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

    app = FastAPI(title=f"AOEP {name}", version="0.1.0")
    app.state.config = cfg
    app.state.factory = fac

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

    @app.get("/health", response_model=HealthStatus)
    def health() -> HealthStatus:  # pragma: no cover - exercised via TestClient
        return HealthStatus(
            service=name,
            status="ok",
            deploy_mode=cfg.deploy_mode.value,
            components=fac.component_summary(),
        )

    return app
