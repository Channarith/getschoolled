"""Introductory free plan: seat cap, offer window, and trial expiry."""

from aoep_shared.free_plan import (
    FreePlanOffer,
    evaluate_free_offer,
    free_plan_blocks_agents,
    free_plan_blocks_group,
    free_plan_lesson_block,
    trial_expires_at,
)

_START = 1_000_000.0
_OFFER = FreePlanOffer(seat_limit=100, offer_days=14, trial_days=14, offer_start=_START)


def test_offer_is_open_for_the_first_claim_inside_the_window():
    status = evaluate_free_offer(0, _START + 3600, _OFFER)
    assert status.available
    assert status.seats_remaining == 100
    assert status.as_dict()["group_classes"] is False
    assert status.as_dict()["ai_agents"] is False


def test_offer_closes_after_100_claims():
    status = evaluate_free_offer(100, _START + 3600, _OFFER)
    assert not status.available
    assert "100" in status.reason
    assert status.seats_remaining == 0


def test_offer_closes_when_the_short_window_ends():
    status = evaluate_free_offer(3, _OFFER.offer_ends_at, _OFFER)
    assert not status.available
    assert "ended" in status.reason


def test_trial_lasts_14_days():
    claimed = _START + 10
    assert trial_expires_at(claimed, _OFFER) == claimed + 14 * 86400


def test_free_plan_blocks_group_and_agents_and_inactive_lessons():
    guest = None
    assert not free_plan_blocks_group(guest)
    assert not free_plan_blocks_agents(guest)
    assert free_plan_lesson_block(guest) == ""

    inactive = {"tier": "free", "free_plan": {"active": False}}
    assert free_plan_blocks_group(inactive)
    assert free_plan_blocks_agents(inactive)
    assert "14-day" in free_plan_lesson_block(inactive)

    active = {"tier": "free", "free_plan": {"active": True}}
    assert free_plan_blocks_group(active)
    assert free_plan_blocks_agents(active)
    assert free_plan_lesson_block(active) == ""

    paid = {"tier": "premium", "free_plan": {"active": False}}
    assert not free_plan_blocks_group(paid)
    assert free_plan_lesson_block(paid) == ""
