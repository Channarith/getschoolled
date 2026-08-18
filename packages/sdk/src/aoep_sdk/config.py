"""Environment-driven SDK configuration."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field

from .errors import TransportError


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


def _is_local_url(url: str) -> bool:
    from urllib.parse import urlparse
    try:
        parsed = urlparse(_clean_url(url).lower())
    except Exception:
        return False
    host = parsed.hostname or ""
    return host in ("localhost", "127.0.0.1", "::1")


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
    def local(cls) -> "ServiceURLs":
        """Hard-coded localhost service map for isolated developer work."""

        return cls(**_LOCAL_URLS)

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

    def non_local_services(self) -> list[str]:
        """Return service names whose URLs are not loopback."""

        return [
            name
            for name, url in asdict(self).items()
            if not _is_local_url(url)
        ]


@dataclass(frozen=True)
class AOEPConfig:
    """Connection, authentication, and transport settings for :class:`AOEPClient`.

    Prefer :meth:`local` when extending the platform so experiments stay on the
    developer machine (sandbox payments, offline LLM fallbacks, no cloud secrets).
    """

    services: ServiceURLs = field(default_factory=ServiceURLs.local)
    bearer_token: str = ""
    internal_token: str = ""
    admin_secret: str = ""
    timeout_seconds: float = 10.0
    user_agent: str = "aoep-sdk-python"
    require_local: bool = False

    @classmethod
    def local(cls) -> "AOEPConfig":
        """Safe local defaults: localhost URLs and no privileged tokens."""

        return cls(
            services=ServiceURLs.local(),
            bearer_token="",
            internal_token="",
            admin_secret="",
            require_local=True,
        )

    @classmethod
    def from_env(cls) -> "AOEPConfig":
        timeout_raw = os.environ.get("AOEP_TIMEOUT_SECONDS", "10")
        try:
            timeout = float(timeout_raw)
        except ValueError:
            timeout = 10.0
        if timeout <= 0:
            timeout = 10.0
        require_local = os.environ.get("AOEP_REQUIRE_LOCAL", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
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
            require_local=require_local,
        )

    def assert_safe_for_extension(self) -> None:
        """Refuse remote targets when local-only mode is enabled.

        Extenders building on top of AOEP should default to the local stack so a
        mistake cannot talk to production. Privileged tokens are still allowed
        against loopback services (local identity/memory gates).
        """

        if not self.require_local:
            return
        remote = self.services.non_local_services()
        if remote:
            joined = ", ".join(remote)
            raise TransportError(
                "AOEP local-only mode refuses non-loopback service URLs "
                f"({joined}). Use AOEPConfig.local() or unset AOEP_BASE_URL / "
                "AOEP_*_URL overrides while developing."
            )
