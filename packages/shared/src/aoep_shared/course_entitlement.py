"""Who may take a paid full course: one server-side decision.

``entitled_to_course(user, course_id)`` is the only place that decides. ``user`` is the verified account from the
identity service (``/auth/me``), never a field the browser sent. Result:

  login_required  no verified account: nobody pays and nothing unlocks (the demo ends at "create or log in")
  free            admin, VIP (membership_class "vip"), or a tier listed in COURSE_FREE_TIERS (default "premium")
  paid            this account has a paid, not refunded, not revoked purchase of this course
  must_pay        signed in, not entitled: the price is shown and checkout is offered

Config (names only): COURSE_FREE_TIERS (comma list, default "premium"; VIP is the identity service's name for premium).
Pro stays a paying tier unless the owner adds "pro" there.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Protocol

LOGIN_REQUIRED = "login_required"
FREE = "free"
PAID = "paid"
MUST_PAY = "must_pay"
ENTITLEMENTS = (LOGIN_REQUIRED, FREE, PAID, MUST_PAY)


class _Purchases(Protocol):
    def is_paid(self, account_id: str, course_id: str) -> bool: ...


def free_tiers() -> frozenset[str]:
    raw = os.environ.get("COURSE_FREE_TIERS", "premium")
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def account_id(user: Optional[Mapping[str, Any]]) -> str:
    if not isinstance(user, Mapping):
        return ""
    return str(user.get("id") or "").strip()


def is_free_member(user: Optional[Mapping[str, Any]]) -> bool:
    """Admin, VIP, or a tier the owner listed as free for courses."""
    if not isinstance(user, Mapping):
        return False
    if user.get("is_admin") is True:
        return True
    if str(user.get("membership_class") or "").strip().lower() == "vip":
        return True
    return str(user.get("tier") or "").strip().lower() in free_tiers()


def entitled_to_course(
    user: Optional[Mapping[str, Any]],
    course_id: str,
    *,
    purchases: Optional[_Purchases] = None,
) -> str:
    """Return one of ENTITLEMENTS for this verified account and course."""
    uid = account_id(user)
    if not uid:
        return LOGIN_REQUIRED
    if is_free_member(user):
        return FREE
    if purchases is not None and course_id and purchases.is_paid(uid, course_id):
        return PAID
    return MUST_PAY


def unlocks_full_class(entitlement: str) -> bool:
    return entitlement in (FREE, PAID)
