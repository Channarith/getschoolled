"""Environment-driven SDK configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


_LOCAL_URLS = {
    "orchestrator": "http://localhost:8000",
    "speech": "http://localhost:8002",
    "perception": "http://localhost:8003",
    "memory": "http://localhost:8004",
    "curriculum": "http://localhost:8005",
    "billing": "http://localhost:8006",
    "integrations": "http://localhost:8007",
    "identity": "http://localhost:8008",
}


def _clean_url(value: str) -> str:
    return value.strip().rstrip("/")


@dataclass(frozen=True)
class ServiceURLs:
    """Base URLs for all public AOEP services."""

    orchestrator: str = _LOCAL_URLS["orchestrator"]
    speech: str = _LOCAL_URLS["speech"]
    perception: str = _LOCAL_URLS["perception"]
    memory: str = _LOCAL_URLS["memory"]
    curriculum: str = _LOCAL_URLS["curriculum"]
    billing: str = _LOCAL_URLS["billing"]
    integrations: str = _LOCAL_URLS["integrations"]
    identity: str = _LOCAL_URLS["identity"]

    @classmethod
    def from_env(cls) -> "ServiceURLs":
        """Resolve explicit service URLs, a shared cloud origin, or local defaults.

        Per-service ``AOEP_<SERVICE>_URL`` values take precedence over the legacy
        ``<SERVICE>_URL`` names. If ``AOEP_BASE_URL`` is set, missing service URLs
        are formed as ``<base>/<service>`` for ingress-based deployments.
        """

        base = _clean_url(os.environ.get("AOEP_BASE_URL", ""))
        values: dict[str, str] = {}
        for service, local_url in _LOCAL_URLS.items():
            explicit = (
                os.environ.get(f"AOEP_{service.upper()}_URL")
                or os.environ.get(f"{service.upper()}_URL")
                or ""
            )
            values[service] = _clean_url(
                explicit or (f"{base}/{service}" if base else local_url)
            )
        return cls(**values)


@dataclass(frozen=True)
class AOEPConfig:
    """Connection, authentication, and transport settings for :class:`AOEPClient`."""

    services: ServiceURLs = field(default_factory=ServiceURLs)
    bearer_token: str = ""
    internal_token: str = ""
    admin_secret: str = ""
    timeout_seconds: float = 10.0
    user_agent: str = "aoep-sdk-python"

    @classmethod
    def from_env(cls) -> "AOEPConfig":
        timeout_raw = os.environ.get("AOEP_TIMEOUT_SECONDS", "10")
        try:
            timeout = float(timeout_raw)
        except ValueError:
            timeout = 10.0
        if timeout <= 0:
            timeout = 10.0
        return cls(
            services=ServiceURLs.from_env(),
            bearer_token=os.environ.get("AOEP_BEARER_TOKEN", "").strip(),
            internal_token=(
                os.environ.get("AOEP_INTERNAL_TOKEN")
                or os.environ.get("INTERNAL_SERVICE_TOKEN")
                or os.environ.get("INTERNAL_TOKEN")
                or ""
            ).strip(),
            admin_secret=(
                os.environ.get("AOEP_ADMIN_SECRET")
                or os.environ.get("ADMIN_SECRET")
                or ""
            ).strip(),
            timeout_seconds=timeout,
            user_agent=os.environ.get("AOEP_USER_AGENT", "aoep-sdk-python").strip()
            or "aoep-sdk-python",
        )
