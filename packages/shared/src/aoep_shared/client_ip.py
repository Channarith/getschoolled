"""Client address for rate limiting, without trusting what the client says about itself.

``X-Forwarded-For`` is a list every proxy appends to, so the FIRST entry is whatever the client chose to send and the entries
the platform's own proxies added are at the END. Taking the first entry lets a client mint a new rate-limit bucket on every
request. We count ``AOEP_TRUSTED_PROXY_HOPS`` proxies (default 1: the ingress) from the right instead, and fall back to the
socket peer when the header is missing, shorter than the hop count, or not an IP address.
"""
from __future__ import annotations

import ipaddress
import os
from typing import Mapping, Optional


def trusted_hops() -> int:
    try:
        return max(0, int(os.environ.get("AOEP_TRUSTED_PROXY_HOPS", "1")))
    except ValueError:
        return 1


def _as_ip(value: str) -> Optional[str]:
    v = (value or "").strip().strip("[]")
    if v.count(":") == 1 and "." in v:   # ipv4:port
        v = v.rsplit(":", 1)[0]
    try:
        return str(ipaddress.ip_address(v))
    except ValueError:
        return None


def client_ip(headers: Mapping[str, str], peer: Optional[str]) -> str:
    """The address to key a rate limit on: the entry ``trusted_hops()`` from the right of X-Forwarded-For, else the peer."""
    hops = trusted_hops()
    fallback = _as_ip(peer or "") or (peer or "anon")
    if hops == 0:
        return fallback
    parts = [p.strip() for p in (headers.get("x-forwarded-for") or "").split(",") if p.strip()]
    if len(parts) < hops:
        return fallback
    return _as_ip(parts[-hops]) or fallback
