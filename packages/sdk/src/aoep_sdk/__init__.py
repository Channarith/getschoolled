"""Official Python SDK for the Salareen AOEP ecosystem."""

from __future__ import annotations

from aoep_shared.version import API_VERSION, get_version

from .clients import (
    CurriculumClient,
    IdentityClient,
    MemoryClient,
    OrchestratorClient,
    ServiceClient,
)
from .config import AOEPConfig, ServiceURLs
from .errors import (
    AOEPError,
    APIError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    TransportError,
    ValidationError,
)
from .transport import JSONTransport


class AOEPClient:
    """Entry point for remote AOEP APIs.

    Typed clients cover the core developer workflows. The remaining service
    properties expose health/version and a generic ``request`` method so new
    platform endpoints are usable without waiting for an SDK release.
    """

    def __init__(self, config: AOEPConfig | None = None) -> None:
        self.config = config or AOEPConfig.from_env()
        self._transports = {
            name: JSONTransport(
                getattr(self.config.services, name),
                bearer_token=self.config.bearer_token,
                internal_token=self.config.internal_token,
                admin_secret=self.config.admin_secret,
                timeout_seconds=self.config.timeout_seconds,
                user_agent=self.config.user_agent,
            )
            for name in (
                "orchestrator",
                "speech",
                "perception",
                "memory",
                "curriculum",
                "billing",
                "integrations",
                "identity",
            )
        }
        self.orchestrator = OrchestratorClient(self._transports["orchestrator"])
        self.identity = IdentityClient(self._transports["identity"])
        self.curriculum = CurriculumClient(self._transports["curriculum"])
        self.memory = MemoryClient(self._transports["memory"])
        self.speech = ServiceClient(self._transports["speech"])
        self.perception = ServiceClient(self._transports["perception"])
        self.billing = ServiceClient(self._transports["billing"])
        self.integrations = ServiceClient(self._transports["integrations"])

    def set_bearer_token(self, token: str) -> None:
        """Apply a user session token to every service client."""

        for transport in self._transports.values():
            transport.set_bearer_token(token)

    def authenticate(self, email: str, password: str) -> dict:
        """Log in through identity and apply the returned token to all services."""

        result = self.identity.login(email, password, update_session=False)
        token = result.get("token")
        if not isinstance(token, str) or not token:
            raise TransportError("identity login response did not include a token")
        self.set_bearer_token(token)
        return result

    def service(self, name: str) -> ServiceClient:
        """Return a generic client for any configured service."""

        try:
            transport = self._transports[name]
        except KeyError as exc:
            raise ValueError(f"unknown AOEP service: {name}") from exc
        return ServiceClient(transport)


AoepClient = AOEPClient
__version__ = get_version()

__all__ = [
    "AOEPClient",
    "AOEPConfig",
    "AOEPError",
    "APIError",
    "API_VERSION",
    "AuthenticationError",
    "AoepClient",
    "CurriculumClient",
    "IdentityClient",
    "JSONTransport",
    "MemoryClient",
    "NotFoundError",
    "OrchestratorClient",
    "PermissionDeniedError",
    "RateLimitError",
    "ServiceClient",
    "ServiceURLs",
    "TransportError",
    "ValidationError",
    "__version__",
]
