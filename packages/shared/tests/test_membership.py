"""Membership class mapping."""

from aoep_shared.membership import membership_class_for_tier


def test_vip_is_premium_only():
    assert membership_class_for_tier("premium") == "vip"
    assert membership_class_for_tier("pro") == "standard"
    assert membership_class_for_tier("basic") == "standard"
