"""Exceptions raised by the AOEP Python SDK."""

from __future__ import annotations

from typing import Any


class AOEPError(Exception):
    """Base exception for SDK failures."""


class TransportError(AOEPError):
    """The service could not be reached or returned an invalid response."""


class APIError(AOEPError):
    """A service returned a non-success HTTP response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        detail: Any = None,
        request_id: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail
        self.request_id = request_id


class AuthenticationError(APIError):
    """Authentication is missing or invalid."""


class PermissionDeniedError(APIError):
    """The caller is authenticated but cannot perform this action."""


class NotFoundError(APIError):
    """The requested resource does not exist."""


class RateLimitError(APIError):
    """The service rate limit was exceeded."""


class ValidationError(APIError):
    """The service rejected the request payload."""
