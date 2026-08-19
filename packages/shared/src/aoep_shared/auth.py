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
        iterations = min(int(iters), 1_000_000)  # cap to prevent DoS via malicious stored hash
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 _b64d(salt_b64), iterations)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(_b64e(dk), hash_b64)


# --------------------------------------------------------------------------- #
# Session tokens
# --------------------------------------------------------------------------- #
def sign_token(payload: dict, key: bytes, *, ttl_s: int = 86_400) -> str:
    # TODO: callers MUST include a "kind" or "purpose" claim (e.g. kind="auth" or
    # kind="password_reset") and verify_token callers MUST assert that claim, so that
    # tokens issued for one purpose cannot be accepted for another.
    now = int(time.time())
    iat = now
    exp = now + ttl_s
    body = {**payload, "iat": iat, "exp": exp}
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
    exp = body.get("exp")
    exp_f = float(exp) if exp is not None else 0.0
    if exp_f < (now if now is not None else time.time()):
        return None
    return body


# --------------------------------------------------------------------------- #
# Assessment signing key (separate from the session auth key)
# --------------------------------------------------------------------------- #
_DEV_ASSESSMENT_KEY = "dev-assessment-signing-key"


def assessment_signing_key() -> bytes:
    """Return the assessment token signing key.

    Always reads ASSESSMENT_SIGNING_KEY directly; never falls back to
    AUTH_SIGNING_KEY so the two key spaces stay isolated.
    """
    return os.environ.get("ASSESSMENT_SIGNING_KEY", _DEV_ASSESSMENT_KEY).encode()


def assessment_key_is_dev_default() -> bool:
    """True when ASSESSMENT_SIGNING_KEY is unset (using the insecure dev default)."""
    key = os.environ.get("ASSESSMENT_SIGNING_KEY", "")
    return not key or key == _DEV_ASSESSMENT_KEY
