"""Constant-time string comparison that never raises on non-ASCII input.

``hmac.compare_digest`` raises ``TypeError`` for ``str`` arguments containing
non-ASCII characters, which turned a malformed header or token into a 500.
"""

from __future__ import annotations

import hmac
from typing import Union

_Text = Union[str, bytes, None]


def _bytes(value: _Text) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8", "surrogatepass")


def equals(a: _Text, b: _Text) -> bool:
    return hmac.compare_digest(_bytes(a), _bytes(b))
