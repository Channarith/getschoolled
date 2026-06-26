"""TOTP two-factor authentication (RFC 6238, stdlib-only)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
from typing import Optional
from urllib.parse import quote


def generate_totp_secret() -> str:
    """Return a base32 secret suitable for authenticator apps."""
    raw = os.urandom(20)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    padded = secret.upper().replace(" ", "")
    pad = "=" * (-len(padded) % 8)
    return base64.b32decode(padded + pad)


def totp_at(secret: str, *, counter: int, digits: int = 6) -> str:
    key = _decode_secret(secret)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def current_totp(secret: str, *, now: Optional[float] = None, period: int = 30) -> str:
    ts = int(now if now is not None else time.time())
    return totp_at(secret, counter=ts // period)


def verify_totp(
    secret: str,
    code: str,
    *,
    now: Optional[float] = None,
    period: int = 30,
    window: int = 1,
) -> bool:
    """Verify a 6-digit TOTP with ±``window`` steps of slack."""
    if not code or not code.isdigit() or len(code) != 6:
        return False
    ts = int(now if now is not None else time.time())
    step = ts // period
    for delta in range(-window, window + 1):
        if hmac.compare_digest(totp_at(secret, counter=step + delta), code):
            return True
    return False


def otpauth_uri(*, secret: str, email: str, issuer: str = "Salareen") -> str:
    label = quote(f"{issuer}:{email}", safe="")
    params = f"secret={secret}&issuer={quote(issuer, safe='')}&algorithm=SHA1&digits=6&period=30"
    return f"otpauth://totp/{label}?{params}"
