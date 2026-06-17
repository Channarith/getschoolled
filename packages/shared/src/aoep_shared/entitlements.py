"""Entitlements: the single ``can_start`` gate used across the platform.

The billing service owns plans/subscriptions/credits/metered usage and exposes a
single entitlements API: ``can_start(class_type, language, features)``. The plan
matrix lives here so the gate is pure and unit-testable, independent of Stripe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .languages import SUPPORTED_LANGUAGES
from .schemas import ClassType, PlanTier


@dataclass(frozen=True)
class PlanDefinition:
    tier: PlanTier
    languages: frozenset[str]
    solo_classes: bool
    cross_class_memory: bool
    recordings: bool
    analytics: bool


_ALL_LANGS = frozenset(SUPPORTED_LANGUAGES)
_BASIC_LANGS = frozenset({"en", "es", "fr", "de", "zh"})

PLANS: dict[PlanTier, PlanDefinition] = {
    PlanTier.FREE: PlanDefinition(
        tier=PlanTier.FREE,
        languages=frozenset({"en"}),
        solo_classes=False,
        cross_class_memory=False,
        recordings=False,
        analytics=False,
    ),
    PlanTier.BASIC: PlanDefinition(
        tier=PlanTier.BASIC,
        languages=_BASIC_LANGS,
        solo_classes=False,
        cross_class_memory=False,
        recordings=False,
        analytics=False,
    ),
    PlanTier.PRO: PlanDefinition(
        tier=PlanTier.PRO,
        languages=_ALL_LANGS,
        solo_classes=True,
        cross_class_memory=True,
        recordings=True,
        analytics=False,
    ),
    PlanTier.PREMIUM: PlanDefinition(
        tier=PlanTier.PREMIUM,
        languages=_ALL_LANGS,
        solo_classes=True,
        cross_class_memory=True,
        recordings=True,
        analytics=True,
    ),
}

# Feature flags that map onto plan attributes.
FEATURE_ATTR = {
    "cross_class_memory": "cross_class_memory",
    "recordings": "recordings",
    "analytics": "analytics",
}


@dataclass
class Decision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)


def can_start(
    tier: PlanTier,
    *,
    class_type: ClassType,
    language: str = "en",
    features: Iterable[str] = (),
) -> Decision:
    """Return whether a plan tier may start a class with the given options."""
    plan = PLANS[tier]
    reasons: list[str] = []

    if class_type is ClassType.SOLO and not plan.solo_classes:
        reasons.append(f"{tier.value} plan does not include 1:1 solo classes")

    if language not in plan.languages:
        reasons.append(f"{tier.value} plan does not include language {language!r}")

    for feature in features:
        attr = FEATURE_ATTR.get(feature)
        if attr is None:
            reasons.append(f"unknown feature {feature!r}")
        elif not getattr(plan, attr):
            reasons.append(f"{tier.value} plan does not include {feature}")

    return Decision(allowed=not reasons, reasons=reasons)
