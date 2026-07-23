"""Dependency-free JSON transport shared by all SDK service clients."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Mapping

from .errors import (
    APIError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    TransportError,
    ValidationError,
)


_ERRORS: dict[int, type[APIError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    422: ValidationError,
    429: RateLimitError,
}


class JSONTransport:
    """Small, injectable HTTP transport with AOEP auth and error mapping."""

    def __init__(
        self,
        base_url: str,
        *,
        bearer_token: str = "",
        internal_token: str = "",
        admin_secret: str = "",
        timeout_seconds: float = 10.0,
        user_agent: str = "aoep-sdk-python",
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url cannot be empty")
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token.strip()
        self.internal_token = internal_token.strip()
        self.admin_secret = admin_secret.strip()
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def set_bearer_token(self, token: str) -> None:
        """Update the user session token used by subsequent requests."""

        self.bearer_token = token.strip()

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        url = self.base_url + "/" + path.lstrip("/")
        if query:
            clean_query = {
                key: value
                for key, value in query.items()
                if value is not None and value != ""
            }
            if clean_query:
                url += "?" + urllib.parse.urlencode(clean_query, doseq=True)

        request_id = uuid.uuid4().hex
        request_headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "X-Request-ID": request_id,
        }
        if self.bearer_token:
            request_headers["Authorization"] = f"Bearer {self.bearer_token}"
        if self.internal_token:
            request_headers["X-Internal-Token"] = self.internal_token
        if self.admin_secret:
            request_headers["X-Admin-Secret"] = self.admin_secret
        request_headers.update(headers or {})

        data = None
        if json_body is not None:
            data = json.dumps(dict(json_body)).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            url,
            data=data,
            headers=request_headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            self._raise_api_error(exc, request_id)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TransportError(f"{method.upper()} {url} failed: {exc}") from exc

        if not raw:
            return None
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportError(
                f"{method.upper()} {url} returned invalid JSON"
            ) from exc

    @staticmethod
    def _raise_api_error(exc: urllib.error.HTTPError, request_id: str) -> None:
        raw = exc.read()
        try:
            payload = json.loads(raw) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {"detail": raw.decode("utf-8", errors="replace")}
        detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        message = str(detail) if detail else f"AOEP API returned HTTP {exc.code}"
        error_type = _ERRORS.get(exc.code, APIError)
        response_request_id = exc.headers.get("X-Request-ID", request_id)
        raise error_type(
            message,
            status_code=exc.code,
            detail=detail,
            request_id=response_request_id,
        ) from exc
