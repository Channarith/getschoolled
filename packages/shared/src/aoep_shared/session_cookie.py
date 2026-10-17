"""HttpOnly session cookie shared by the web app and the API."""

from __future__ import annotations

import os

COOKIE_NAME = "aoep_session"


def _production() -> bool:
    return os.environ.get("DEPLOY_MODE", "local").lower() not in (
        "local", "dev", "development", "test",
    )


def attach_session_cookie(response, token: str) -> None:
    """Set the session cookie. The token is not readable from page scripts."""
    domain = (os.environ.get("SESSION_COOKIE_DOMAIN") or "").strip() or None
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=_production(),
        samesite="lax",
        max_age=86_400,
        path="/",
        domain=domain,
    )


def clear_session_cookie(response) -> None:
    domain = (os.environ.get("SESSION_COOKIE_DOMAIN") or "").strip() or None
    response.delete_cookie(COOKIE_NAME, path="/", domain=domain)
