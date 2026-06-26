"""Consumer subscription pricing (Netflix-style) and calendar billing.

Standard (``basic``) is $19.99/month with ads. VIP (``premium``) is $29.99/month
ad-free. Paid plans renew monthly on the calendar day the member signed up
(anchor day); shorter months bill on the last day (e.g. Jan 31 -> Feb 28/29).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from .schemas import PlanTier

STANDARD_PRICE_USD = 19.99
VIP_PRICE_USD = 29.99

# Tiers offered on the consumer signup / billing picker.
CONSUMER_TIERS = frozenset({PlanTier.FREE.value, PlanTier.BASIC.value, PlanTier.PREMIUM.value})


@dataclass(frozen=True)
class ConsumerPlan:
    tier: str
    display_name: str
    price_usd: float
    billing_interval: str  # "monthly"
    ads: bool
    blurb: str


CONSUMER_PLANS: dict[str, ConsumerPlan] = {
    PlanTier.FREE.value: ConsumerPlan(
        tier=PlanTier.FREE.value,
        display_name="Free",
        price_usd=0.0,
        billing_interval="monthly",
        ads=True,
        blurb="English classes with ads",
    ),
    PlanTier.BASIC.value: ConsumerPlan(
        tier=PlanTier.BASIC.value,
        display_name="Standard",
        price_usd=STANDARD_PRICE_USD,
        billing_interval="monthly",
        ads=True,
        blurb="5 languages, billed monthly on your signup day",
    ),
    PlanTier.PREMIUM.value: ConsumerPlan(
        tier=PlanTier.PREMIUM.value,
        display_name="VIP",
        price_usd=VIP_PRICE_USD,
        billing_interval="monthly",
        ads=False,
        blurb="All languages, ad-free, analytics — billed monthly on your signup day",
    ),
}


def consumer_plan_for_tier(tier: str) -> Optional[ConsumerPlan]:
    return CONSUMER_PLANS.get((tier or PlanTier.FREE.value).lower())


def price_usd_for_tier(tier: str) -> float:
    plan = consumer_plan_for_tier(tier)
    return plan.price_usd if plan else 0.0


def tier_requires_payment(tier: str) -> bool:
    return price_usd_for_tier(tier) > 0.0


def anchor_day_from_timestamp(ts: float) -> int:
    """Calendar day (1–31) of signup in UTC."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().day


def billing_date_for_month(year: int, month: int, anchor_day: int) -> date:
    """Return the billing date in ``year``/``month`` for ``anchor_day``.

    When ``anchor_day`` exceeds the month's length (e.g. 31 in February),
    use the last day of that month.
    """
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor_day, last))


def _add_one_month(d: date, anchor_day: int) -> date:
    if d.month == 12:
        year, month = d.year + 1, 1
    else:
        year, month = d.year, d.month + 1
    return billing_date_for_month(year, month, anchor_day)


def next_billing_on_or_after(from_day: date, anchor_day: int) -> date:
    """Next billing date on ``anchor_day`` that is strictly after ``from_day``."""
    candidate = billing_date_for_month(from_day.year, from_day.month, anchor_day)
    if candidate > from_day:
        return candidate
    return _add_one_month(from_day, anchor_day)


def initial_next_billing_at(signup_ts: float, *, anchor_day: Optional[int] = None) -> float:
    """Unix timestamp (UTC midnight) of the first renewal after signup."""
    signup = datetime.fromtimestamp(signup_ts, tz=timezone.utc).date()
    day = anchor_day if anchor_day is not None else signup.day
    nxt = next_billing_on_or_after(signup, day)
    return datetime(nxt.year, nxt.month, nxt.day, tzinfo=timezone.utc).timestamp()


def advance_next_billing_at(current_next_ts: float, anchor_day: int) -> float:
    """Advance one billing period from the current next-billing timestamp."""
    current = datetime.fromtimestamp(current_next_ts, tz=timezone.utc).date()
    nxt = _add_one_month(current, anchor_day)
    return datetime(nxt.year, nxt.month, nxt.day, tzinfo=timezone.utc).timestamp()


def subscription_public(
    *,
    tier: str,
    subscription_started_at: Optional[float],
    billing_anchor_day: Optional[int],
    next_billing_at: Optional[float],
    billing_amount_usd: Optional[float],
) -> dict:
    """Serialize subscription fields for API responses."""
    plan = consumer_plan_for_tier(tier)
    return {
        "tier": tier,
        "display_name": plan.display_name if plan else tier,
        "price_usd": billing_amount_usd if billing_amount_usd is not None else price_usd_for_tier(tier),
        "billing_interval": "monthly",
        "ads": plan.ads if plan else True,
        "subscription_started_at": subscription_started_at,
        "billing_anchor_day": billing_anchor_day,
        "next_billing_at": next_billing_at,
    }
