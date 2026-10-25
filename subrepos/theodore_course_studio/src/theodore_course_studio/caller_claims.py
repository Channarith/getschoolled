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


SESSION_COOKIE = "aoep_session"  # the HttpOnly cookie the identity service sets at login (same signed token as the bearer)


def authorization_from(authorization: str, cookies: Optional[Any] = None) -> str:
    """The Authorization header if the caller sent one, else the login cookie as a bearer.

    The web app keeps the bearer in memory (the legacy localStorage copy is removed), so a same-origin iframe or a plain
    fetch carries only the HttpOnly session cookie. Both forms are verified the same way by the identity service.
    """
    header = (authorization or "").strip()
    if header:
        return header
    token = ""
    try:
        token = str((cookies or {}).get(SESSION_COOKIE, "")).strip()
    except AttributeError:
        token = ""
    return f"Bearer {token}" if token else ""


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


def verification_required(course_id: str, access: str) -> bool:
    """Claims are never trusted for a paid public course or an explicit 'full' request, even with the flag off.

    STUDIO_VERIFY_CLAIMS still controls the authoring studio and the trial-run composer (legacy callers); the paid gate
    must fail closed on its own so a non-entitled caller cannot ship `{"access":"full","is_admin":true}` to get a class.
    """
    from aoep_shared.course_studio_access import purchasable_course

    return verification_enabled() or bool(purchasable_course(course_id)) or (access or "").strip().lower() == "full"


def effective_access(
    *,
    authorization: str,
    access: str,
    registered: bool,
    is_admin: bool,
    enrollment_status: str,
    course_id: str = "",
    purchases: Any = None,
    fetch: Optional[Callable[[str], Optional[dict]]] = None,
    now: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """The access fields to trust: the request's own for legacy authoring calls, the verified caller's otherwise."""
    if not verification_required(course_id, access):
        return {"access": access, "registered": registered, "is_admin": is_admin,
                "enrollment_status": enrollment_status, "verified": None, "caller": None, "entitlement": None}
    from aoep_shared.course_entitlement import entitled_to_course, unlocks_full_class
    from aoep_shared.course_studio_access import purchasable_course

    who = verified_caller(authorization, fetch=fetch, now=now)
    admin = bool(who and who.get("is_admin"))
    mode = (access or "").strip().lower()
    if purchasable_course(course_id):
        ent = entitled_to_course(who, course_id, purchases=purchases)
        unlocked = unlocks_full_class(ent)
        requested = "full" if (unlocked and mode != "sample") else "sample"
        return {"access": requested, "registered": who is not None, "is_admin": admin,
                "enrollment_status": "paid" if unlocked else "", "verified": who is not None, "caller": who,
                "entitlement": ent}
    # Authoring studio with the flag on: no verified admin means no 'full' default.
    requested = mode or ("" if admin else "sample")
    return {"access": requested, "registered": who is not None, "is_admin": admin,
            "enrollment_status": enrollment_status if who is not None else "", "verified": who is not None, "caller": who,
            "entitlement": None}
