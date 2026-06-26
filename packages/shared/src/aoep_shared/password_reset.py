"""Password reset tokens (signed, short-lived, single-purpose)."""

from __future__ import annotations

from typing import Optional

from .auth import sign_token, verify_token


def issue_reset_token(account_id: str, email: str, key: bytes, *, ttl_s: int = 3600) -> str:
    return sign_token(
        {"sub": account_id, "email": email, "purpose": "password_reset"},
        key,
        ttl_s=ttl_s,
    )


def verify_reset_token(token: str, key: bytes, *, now: Optional[float] = None) -> Optional[dict]:
    body = verify_token(token, key, now=now)
    if not body or body.get("purpose") != "password_reset":
        return None
    return body
