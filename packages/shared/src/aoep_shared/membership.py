"""Membership class (standard vs VIP) derived from plan tier."""

from __future__ import annotations

from typing import Literal

MembershipClass = Literal["standard", "vip"]

# Netflix-style: Standard = free/basic (with ads); VIP = premium (ad-free).
VIP_TIERS = frozenset({"premium"})
STANDARD_TIERS = frozenset({"free", "basic", "pro"})


def membership_class_for_tier(tier: str) -> MembershipClass:
    """Map subscription tier to Netflix-style membership class."""
    if (tier or "free").lower() in VIP_TIERS:
        return "vip"
    return "standard"
