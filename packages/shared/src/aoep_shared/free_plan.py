"""Introductory free plan: a short trial for the first 100 people.

The free plan is English lessons with ads. It does not include group classes
or AI agents. After the offer window or the seat cap, new people cannot
select it, and a claimed trial ends on its own expiry.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

FREE_PLAN_SEAT_LIMIT = 100
FREE_PLAN_OFFER_DAYS = 14
FREE_PLAN_TRIAL_DAYS = 14
# The offer opens with this release and closes two weeks later unless env
# overrides the start or the length.
_DEFAULT_OFFER_START = datetime(2026, 10, 15, tzinfo=timezone.utc).timestamp()

_DAY = 86400.0


@dataclass(frozen=True)
class FreePlanOffer:
    seat_limit: int = FREE_PLAN_SEAT_LIMIT
    offer_days: int = FREE_PLAN_OFFER_DAYS
    trial_days: int = FREE_PLAN_TRIAL_DAYS
    offer_start: float = _DEFAULT_OFFER_START

    @property
    def offer_ends_at(self) -> float:
        return self.offer_start + self.offer_days * _DAY


@dataclass(frozen=True)
class FreePlanStatus:
    available: bool
    reason: str
    seats_limit: int
    seats_claimed: int
    seats_remaining: int
    offer_ends_at: float
    trial_days: int

    def as_dict(self) -> dict:
        return {
            "available": self.available,
            "reason": self.reason,
            "seats_limit": self.seats_limit,
            "seats_claimed": self.seats_claimed,
            "seats_remaining": self.seats_remaining,
            "offer_ends_at": self.offer_ends_at,
            "trial_days": self.trial_days,
            "group_classes": False,
            "ai_agents": False,
        }


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def load_offer() -> FreePlanOffer:
    """Read seat, window, and trial settings. Env overrides are for tests and ops."""
    return FreePlanOffer(
        seat_limit=_env_int("FREE_PLAN_SEAT_LIMIT", FREE_PLAN_SEAT_LIMIT),
        offer_days=_env_int("FREE_PLAN_OFFER_DAYS", FREE_PLAN_OFFER_DAYS),
        trial_days=_env_int("FREE_PLAN_TRIAL_DAYS", FREE_PLAN_TRIAL_DAYS),
        offer_start=_env_float("FREE_PLAN_OFFER_START", _DEFAULT_OFFER_START),
    )


def evaluate_free_offer(
    seats_claimed: int,
    now: float,
    offer: FreePlanOffer | None = None,
) -> FreePlanStatus:
    """Whether a new person may still claim the free plan."""
    offer = offer or load_offer()
    claimed = max(0, int(seats_claimed))
    remaining = max(0, offer.seat_limit - claimed)
    if now >= offer.offer_ends_at:
        reason = "The free plan has ended."
        available = False
    elif claimed >= offer.seat_limit:
        reason = f"The free plan is full. It was limited to the first {offer.seat_limit} people."
        available = False
    else:
        reason = ""
        available = True
    return FreePlanStatus(
        available=available,
        reason=reason,
        seats_limit=offer.seat_limit,
        seats_claimed=claimed,
        seats_remaining=remaining,
        offer_ends_at=offer.offer_ends_at,
        trial_days=offer.trial_days,
    )


def trial_expires_at(claimed_at: float, offer: FreePlanOffer | None = None) -> float:
    offer = offer or load_offer()
    return claimed_at + offer.trial_days * _DAY


def free_trial_active(
    claimed_at: float | None,
    expires_at: float | None,
    now: float,
) -> bool:
    return bool(claimed_at and expires_at and expires_at > now)


def free_plan_blocks_group(profile: dict | None) -> bool:
    """Group classes are never part of the free plan."""
    return bool(profile) and str(profile.get("tier") or "") == "free"


def free_plan_blocks_agents(profile: dict | None) -> bool:
    """AI agents are never part of the free plan."""
    return bool(profile) and str(profile.get("tier") or "") == "free"


def free_plan_lesson_block(profile: dict | None) -> str:
    """Logged-in free accounts can open English lessons only during an active trial.

    Guests and paid plans are unchanged. A missing profile (identity unreachable)
    does not block the class.
    """
    if not profile or str(profile.get("tier") or "") != "free":
        return ""
    free = profile.get("free_plan") if isinstance(profile.get("free_plan"), dict) else {}
    if free.get("active"):
        return ""
    return (
        "The free plan is not available. It is a 14-day trial for the first 100 people, "
        "and then it goes away."
    )
