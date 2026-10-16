"""Entitlements gate: can_start matrix across plan tiers."""

from aoep_shared.entitlements import can_start
from aoep_shared.schemas import ClassType, PlanTier


def test_free_blocks_solo_and_non_english():
    d = can_start(PlanTier.FREE, class_type=ClassType.SOLO, language="es")
    assert not d.allowed
    assert any("solo" in r for r in d.reasons)
    assert any("es" in r for r in d.reasons)


def test_free_blocks_group_and_ai_agents():
    group = can_start(PlanTier.FREE, class_type=ClassType.GROUP, language="en")
    assert not group.allowed
    assert any("group" in reason for reason in group.reasons)
    agents = can_start(PlanTier.FREE, class_type=ClassType.GROUP, language="en", features=["ai_agents"])
    assert not agents.allowed
    assert any("ai_agents" in reason for reason in agents.reasons)


def test_paid_plans_include_group_and_ai_agents():
    for tier in (PlanTier.BASIC, PlanTier.PRO, PlanTier.PREMIUM):
        decision = can_start(tier, class_type=ClassType.GROUP, language="en", features=["ai_agents"])
        assert decision.allowed, tier


def test_pro_allows_solo_all_languages_and_memory():
    d = can_start(
        PlanTier.PRO,
        class_type=ClassType.SOLO,
        language="sw",
        features=["cross_class_memory", "recordings"],
    )
    assert d.allowed


def test_pro_blocks_analytics_but_premium_allows():
    assert not can_start(PlanTier.PRO, class_type=ClassType.GROUP, features=["analytics"]).allowed
    assert can_start(PlanTier.PREMIUM, class_type=ClassType.GROUP, features=["analytics"]).allowed


def test_unknown_feature_is_rejected():
    d = can_start(PlanTier.PREMIUM, class_type=ClassType.GROUP, features=["teleport"])
    assert not d.allowed
