"""Rewards engine: points, ledger, prize redemption."""

import pytest

from aoep_shared.rewards import (
    PointsLedger,
    PrizeKind,
    points_for_completion,
    prize_by_id,
    redeem_prize,
)


def test_points_scale_with_level_score_handson():
    assert points_for_completion("advanced", passed=True) > points_for_completion("beginner", passed=True)
    hi = points_for_completion("beginner", passed=True, score=1.0)
    lo = points_for_completion("beginner", passed=True, score=0.0)
    assert hi > lo
    assert points_for_completion("beginner", passed=True, hands_on=True) > \
        points_for_completion("beginner", passed=True)


def test_failed_gives_consolation_only():
    assert points_for_completion("advanced", passed=False) == 10


def test_ledger_balance_and_spend():
    led = PointsLedger()
    led.earn(150, "course_passed", "c1")
    led.earn(300, "course_passed", "c2")
    assert led.balance == 450
    led.spend(200, "redeem:discount_10", "discount_10")
    assert led.balance == 250
    with pytest.raises(ValueError):
        led.spend(1000, "too much")  # insufficient


def test_redeem_discount_voucher():
    led = PointsLedger()
    led.earn(500, "x")
    prize = prize_by_id("discount_25")
    r = redeem_prize(led, prize)
    assert r.kind == PrizeKind.DISCOUNT.value
    assert r.percent == 25 and r.voucher_code and r.voucher_code.startswith("AOEP-")
    assert led.balance == 0


def test_redeem_raffle_entry():
    led = PointsLedger()
    led.earn(2000, "x")
    prize = prize_by_id("raffle_ps5")
    r = redeem_prize(led, prize)
    assert r.kind == PrizeKind.RAFFLE.value
    assert r.raffle_entry_id and r.detail.get("prize") == "PlayStation 5"
    assert led.balance == 2000 - prize.cost_points


def test_redeem_gift_card_voucher():
    led = PointsLedger()
    led.earn(5000, "x")
    prize = prize_by_id("gift_amazon_5")
    assert prize.kind is PrizeKind.GIFT_CARD
    assert prize.kind_label == "Gift card"
    r = redeem_prize(led, prize)
    assert r.voucher_code and r.voucher_code.startswith("AOEP-")
    assert r.detail.get("brand") == "Amazon" and r.detail.get("value_usd") == 5
    assert led.balance == 0


def test_raffle_costs_raised():
    # Raffle entries should feel meaningful, not 150/400 pts.
    assert prize_by_id("raffle_ps5").cost_points >= 1000
    assert prize_by_id("raffle_gold").cost_points >= 1000


def test_redeem_insufficient_raises():
    led = PointsLedger()
    led.earn(50, "x")
    with pytest.raises(ValueError):
        redeem_prize(led, prize_by_id("discount_25"))
