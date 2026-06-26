"""Membership class mapping."""

from aoep_shared.membership import membership_class_for_tier, tier_requires_payment


def test_vip_tiers():
    assert membership_class_for_tier("pro") == "vip"
    assert membership_class_for_tier("premium") == "vip"


def test_standard_tiers():
    assert membership_class_for_tier("free") == "standard"
    assert membership_class_for_tier("basic") == "standard"


def test_paid_tiers_require_payment():
    assert tier_requires_payment("basic")
    assert not tier_requires_payment("free")
