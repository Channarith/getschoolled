"""Gate for anything that publishes or presents a harvested course.

A course may be served to learners only when its provenance says the source license is
usable commercially (or share-alike with harvest.allow_share_alike on). Courses made
before provenance existed carry no proof; they are reported as ``unverified`` so the
caller can decide (the audit script quarantines them in the corpus).

Any future publish step (posting to the curriculum catalog, a nightly export) must call
``course_servable`` first.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .licensing import HarvestPolicy, Tier, policy_from_env


def course_servable(data: Dict[str, Any], policy: Optional[HarvestPolicy] = None) -> Tuple[bool, str]:
    """Return (ok, reason) for a *.course.json dict."""
    policy = policy or policy_from_env()
    prov = data.get("provenance") or {}
    tier_value = str(data.get("license_tier") or prov.get("license_tier") or "")
    if not prov or not tier_value:
        return False, "unverified: no license provenance (made before license tiers, or authored locally)"
    try:
        tier = Tier(tier_value)
    except ValueError:
        return False, f"unknown license tier {tier_value!r}"
    if policy.tier_allowed(tier):
        return True, f"{tier.value} ({(prov.get('license') or {}).get('spdx', '')})"
    if tier is Tier.SHARE_ALIKE:
        return False, "share-alike license and harvest.allow_share_alike is off"
    return False, f"{tier.value} license cannot be used commercially"
