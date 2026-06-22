"""Internal-service authentication for tools that are NOT public APIs.

Some platform tools (the homework generator/grader, the corrections
queue, the harvester admin actions, ...) are not meant to be hit
directly by end users - they're used by the AI agentic teacher running
inside the agent-runtime + orchestrator. Exposing them to the public
internet would let a student bypass the teacher and grade their own
homework.

This module provides two small primitives used by the FastAPI services
to gate those endpoints:

* :func:`is_internal_caller` - True if the request carries a valid
  ``X-Internal-Token`` header signed by the platform's shared
  ``INTERNAL_TOKEN_KEY`` (or matches the static ``INTERNAL_TOKEN`` env
  for local dev), or comes from a service-account JWT with an
  ``aud=internal`` claim.

* :func:`require_internal` - FastAPI ``Depends`` that 403s the request
  unless :func:`is_internal_caller` accepts it. Use as::

      @app.post("/homework/generate", dependencies=[Depends(require_internal)])
      def homework_generate(...): ...

Failure mode is deliberately conservative: if no key is configured the
gate ALWAYS DENIES so the homework tool can never accidentally ship
open. Set ``INTERNAL_AUTH_DISABLED=1`` (e.g. in local tests) to bypass.
"""

import hmac
import logging
import os
import time
from typing import Optional

try:
    # Optional FastAPI runtime import. Keeping it optional means non-web
    # callers (training scripts, etc.) can import aoep_shared.auth bits
    # without dragging the web stack in.
    from fastapi import Request as _FastAPIRequest
except ImportError:  # pragma: no cover - non-web environments
    _FastAPIRequest = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _shared_key() -> Optional[bytes]:
    """Bytes form of ``INTERNAL_TOKEN_KEY``, the HMAC secret the platform
    uses to sign internal-service tokens. None if unconfigured."""
    raw = _env("INTERNAL_TOKEN_KEY")
    return raw.encode("utf-8") if raw else None


def _static_token() -> Optional[str]:
    """A simple shared-secret token, for local development only. Falls
    back to None in production (use the signed-token path instead)."""
    tok = _env("INTERNAL_TOKEN")
    return tok or None


def is_internal_caller(token_header: Optional[str]) -> bool:
    """Validate the ``X-Internal-Token`` header value.

    Acceptance rules (any one is sufficient):
      1. ``INTERNAL_AUTH_DISABLED=1`` env -> allow (tests, sandbox).
      2. ``INTERNAL_TOKEN`` env set and matches the header exactly
         (constant-time compare) -> allow.
      3. ``INTERNAL_TOKEN_KEY`` env set and the header is a valid
         signed token (HMAC) issued via :mod:`aoep_shared.auth`.
      4. Otherwise -> deny.

    No fallback to "allow if nothing configured" - that's the bug we're
    explicitly preventing.
    """
    if _env("INTERNAL_AUTH_DISABLED").lower() in ("1", "true", "yes"):
        return True
    if not token_header:
        return False

    static = _static_token()
    if static is not None and hmac.compare_digest(static, token_header):
        return True

    key = _shared_key()
    if key is not None:
        # Lazy import to keep this module's stdlib-only footprint clean.
        from .auth import verify_token

        body = verify_token(token_header, key, now=time.time())
        if body and body.get("scope") in ("internal", "agent", "teacher"):
            return True
    return False


def require_internal(request: _FastAPIRequest) -> dict:
    """FastAPI dependency. Use as
    ``dependencies=[Depends(require_internal)]`` on protected routes.

    Returns the (possibly empty) caller-claims dict so the handler can
    audit who made the call.
    """
    # Local import to keep the module FastAPI-optional for non-web users
    # of aoep_shared.
    from fastapi import HTTPException

    auth_header = request.headers.get("authorization", "")
    bearer = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""
    token = (
        request.headers.get("x-internal-token")
        or (bearer if bearer else None)
    )
    if not is_internal_caller(token):
        raise HTTPException(
            status_code=403,
            detail="this endpoint is internal-only "
                   "(used by the AI teacher agent); "
                   "supply a valid X-Internal-Token",
        )
    # Try to surface the claims so handlers can audit-log who used the
    # tool (the orchestrator / agent-runtime / a specific teacher).
    key = _shared_key()
    if key and token:
        from .auth import verify_token
        body = verify_token(token, key) or {}
        return {"caller": body.get("sub", "internal"),
                "scope": body.get("scope", "internal")}
    return {"caller": "internal", "scope": "internal"}
