"""Who is really calling the teach endpoints.

`teach/start` and `teach/trial-run` take `is_admin`, `registered`, `enrollment_status` and `access` from the request body, and an
empty `access` means "authoring studio" (= full). Behind the public `/api/studio/*` proxy nothing checks them, so an anonymous
caller can send `{"is_admin": true}` (or leave `access` out) and get the full paid course, and a fresh `learner_id` is a fresh
10-minute trial. Setting STUDIO_VERIFY_CLAIMS=1 makes the server ignore those fields and ask the identity service (/auth/me) who the
bearer token belongs to. Off by default so nothing changes until the owner has checked IDENTITY_URL and AUTH_SIGNING_KEY on the
studio service; with it on, an identity outage fails closed (the caller gets the 10-minute sample).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

_CACHE: dict[str, tuple[float, Optional[dict]]] = {}
_TTL_S = 60.0
_CACHE_MAX = 2048


def verification_enabled() -> bool:
    return os.environ.get("STUDIO_VERIFY_CLAIMS", "").strip() == "1"


def _fetch_me(authorization: str) -> Optional[dict]:
    url = os.environ.get("IDENTITY_URL", "http://identity:8000").rstrip("/") + "/auth/me"
    req = urllib.request.Request(url, headers={"Authorization": authorization})
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return data if isinstance(data, dict) and (data.get("id") or data.get("email")) else None


def verified_caller(
    authorization: str,
    *,
    fetch: Optional[Callable[[str], Optional[dict]]] = None,
    now: Callable[[], float] = time.time,
) -> Optional[dict]:
    """The account behind a bearer token, or None (no token, bad token, identity unreachable)."""
    header = (authorization or "").strip()
    if not header:
        return None
    key = hashlib.sha256(header.encode("utf-8")).hexdigest()
    hit = _CACHE.get(key)
    t = now()
    if hit and hit[0] > t:
        return hit[1]
    who = (fetch or _fetch_me)(header)
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    # A miss is cached too, briefly, so a burst of bad tokens cannot hammer the identity service.
    _CACHE[key] = (t + (_TTL_S if who else 10.0), who)
    return who


def effective_access(
    *,
    authorization: str,
    access: str,
    registered: bool,
    is_admin: bool,
    enrollment_status: str,
    fetch: Optional[Callable[[str], Optional[dict]]] = None,
    now: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """The access fields to trust: the request's own when verification is off, the verified caller's when it is on."""
    if not verification_enabled():
        return {"access": access, "registered": registered, "is_admin": is_admin,
                "enrollment_status": enrollment_status, "verified": None, "caller": None}
    who = verified_caller(authorization, fetch=fetch, now=now)
    admin = bool(who and who.get("is_admin"))
    # No verified admin means no authoring-studio default: an empty request is the 10-minute sample, never "full".
    requested = (access or "").strip().lower() or ("" if admin else "sample")
    return {"access": requested, "registered": who is not None, "is_admin": admin,
            "enrollment_status": enrollment_status if who is not None else "", "verified": who is not None, "caller": who}
