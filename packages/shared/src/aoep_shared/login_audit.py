"""Login audit helpers (IP, user agent, geo hint from request headers)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LoginContext:
    ip: str
    user_agent: str
    country_hint: str


def login_context_from_headers(
    *,
    x_forwarded_for: str = "",
    x_real_ip: str = "",
    cf_ipcountry: str = "",
    user_agent: str = "",
    client_ip: Optional[str] = None,
) -> LoginContext:
    """Build audit context from reverse-proxy headers (Cloudflare, nginx, etc.)."""
    ip = ""
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    if not ip:
        ip = (x_real_ip or "").strip()
    if not ip:
        ip = (client_ip or "").strip()
    country = (cf_ipcountry or "").strip().upper()[:2]
    return LoginContext(
        ip=ip[:64],
        user_agent=(user_agent or "")[:256],
        country_hint=country,
    )
