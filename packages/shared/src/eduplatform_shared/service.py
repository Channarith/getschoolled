"""Helpers for building consistent FastAPI services.

Every Python service exposes ``GET /health`` reporting its effective deploy
mode. ``create_service_app`` centralizes that wiring (and permissive dev CORS)
so individual services only add their domain endpoints.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eduplatform_shared.config import get_settings
from eduplatform_shared.schemas import HealthStatus


def create_service_app(service_name: str, *, version: str = "0.1.0") -> FastAPI:
    app = FastAPI(title=service_name, version=version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthStatus)
    def health() -> HealthStatus:  # pragma: no cover - exercised via TestClient
        return HealthStatus(
            service=service_name, deploy_mode=get_settings().deploy_mode.value
        )

    return app
