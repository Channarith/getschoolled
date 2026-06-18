"""Authentication primitives (password hashing + signed session tokens).

Stdlib only (no external crypto dep): PBKDF2-HMAC-SHA256 salted password hashing
and HMAC-signed, expiring session tokens. Used by the identity service. The token
format is a compact "<b64url(payload)>.<b64url(sig)>" (JWT-like but dependency-
free); swap to RS256/JWT behind the same interface for production federation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 200_000


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(password: str, *, salt: Optional[bytes] = None,
                  iterations: int = _ITERATIONS) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${_b64e(salt)}${_b64e(dk)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = encoded.split("$")
        if algo != _ALGO:
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 _b64d(salt_b64), int(iters))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(_b64e(dk), hash_b64)


# --------------------------------------------------------------------------- #
# Session tokens
# --------------------------------------------------------------------------- #
def sign_token(payload: dict, key: bytes, *, ttl_s: int = 86_400) -> str:
    body = {**payload, "iat": int(time.time()), "exp": int(time.time()) + ttl_s}
    raw = _b64e(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    sig = _b64e(hmac.new(key, raw.encode("ascii"), hashlib.sha256).digest())
    return f"{raw}.{sig}"


def verify_token(token: str, key: bytes, *, now: Optional[float] = None) -> Optional[dict]:
    try:
        raw, sig = token.split(".")
    except ValueError:
        return None
    expected = _b64e(hmac.new(key, raw.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        body = json.loads(_b64d(raw))
    except (ValueError, json.JSONDecodeError):
        return None
    if float(body.get("exp", 0)) < (now if now is not None else time.time()):
        return None
    return body
