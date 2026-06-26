"""Sync membership tier on identity after payment (internal token)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional


def identity_base_url() -> str:
    return (os.environ.get("IDENTITY_URL") or "http://localhost:8008").rstrip("/")


def internal_token() -> str:
    return os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")


def sync_account_tier(account_id: str, tier: str, *, timeout_s: float = 5.0) -> bool:
    """POST tier upgrade to identity internal endpoint. Returns True on success."""
    url = f"{identity_base_url()}/internal/membership/tier"
    body = json.dumps({"account_id": account_id, "tier": tier}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Internal-Token": internal_token(),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False
