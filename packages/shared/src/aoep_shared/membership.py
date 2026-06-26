"""Membership class (standard vs VIP) derived from plan tier."""

from __future__ import annotations

from typing import Literal

MembershipClass = Literal["standard", "vip"]

VIP_TIERS = frozenset({"pro", "premium"})
STANDARD_TIERS = frozenset({"free", "basic"})


def membership_class_for_tier(tier: str) -> MembershipClass:
    """Map subscription tier to Netflix-style membership class."""
    t = (tier or "free").lower()
    if t in VIP_TIERS:
        return "vip"
    return "standard"


def tier_requires_payment(tier: str) -> bool:
    """Paid tiers need billing validation before activation."""
    return (tier or "free").lower() not in {"free"}
