"""Netflix-style plan pricing and calendar billing."""

from datetime import date, datetime, timezone

from aoep_shared.plan_pricing import (
    CONSUMER_PLANS,
    PRO_PRICE_USD,
    STANDARD_PRICE_USD,
    VIP_PRICE_USD,
    advance_next_billing_at,
    anchor_day_from_timestamp,
    billing_date_for_month,
    initial_next_billing_at,
    next_billing_on_or_after,
    price_usd_for_tier,
    tier_requires_payment,
)
from aoep_shared.membership import membership_class_for_tier


def test_checkout_charges_plan_prices():
    from aoep_shared.providers.payment import _checkout_amount

    assert _checkout_amount("free") == (0, "0.00")
    assert _checkout_amount("basic") == (1900, "19.00")
    assert _checkout_amount("pro") == (2900, "29.00")
    assert _checkout_amount("premium") == (3900, "39.00")
    assert _checkout_amount("vip") == (3900, "39.00")


def test_standard_and_vip_prices():
    assert price_usd_for_tier("free") == 0.0
    assert price_usd_for_tier("basic") == STANDARD_PRICE_USD == 19
    assert price_usd_for_tier("pro") == PRO_PRICE_USD == 29
    assert price_usd_for_tier("premium") == VIP_PRICE_USD == 39
    assert [plan.price_usd for plan in CONSUMER_PLANS.values()] == [0.0, 19.0, 29.0, 39.0]


def test_consumer_plan_labels():
    assert CONSUMER_PLANS["basic"].display_name == "Standard"
    assert CONSUMER_PLANS["pro"].display_name == "Pro"
    assert CONSUMER_PLANS["premium"].display_name == "VIP"
    assert CONSUMER_PLANS["basic"].ads is True
    assert CONSUMER_PLANS["pro"].ads is False
    assert CONSUMER_PLANS["premium"].ads is False


def test_tier_requires_payment():
    assert tier_requires_payment("basic")
    assert tier_requires_payment("pro")
    assert tier_requires_payment("premium")
    assert not tier_requires_payment("free")


def test_membership_class():
    assert membership_class_for_tier("basic") == "standard"
    assert membership_class_for_tier("premium") == "vip"


def test_anchor_day_from_signup():
    ts = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc).timestamp()
    assert anchor_day_from_timestamp(ts) == 15


def test_billing_date_clamps_to_month_end():
    assert billing_date_for_month(2026, 2, 31) == date(2026, 2, 28)
    assert billing_date_for_month(2024, 2, 31) == date(2024, 2, 29)


def test_jan_31_signup_next_bill_is_feb_last_day():
    signup = date(2026, 1, 31)
    nxt = next_billing_on_or_after(signup, anchor_day=31)
    assert nxt == date(2026, 2, 28)


def test_same_day_signup_next_month():
    signup_ts = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc).timestamp()
    nxt_ts = initial_next_billing_at(signup_ts)
    nxt = datetime.fromtimestamp(nxt_ts, tz=timezone.utc).date()
    assert nxt == date(2026, 4, 15)


def test_advance_billing_from_feb_clamp():
    feb_bill = datetime(2026, 2, 28, tzinfo=timezone.utc).timestamp()
    nxt_ts = advance_next_billing_at(feb_bill, anchor_day=31)
    nxt = datetime.fromtimestamp(nxt_ts, tz=timezone.utc).date()
    assert nxt == date(2026, 3, 31)
