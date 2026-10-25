"""Refund rules: configurable, and 'no' always routes to a person."""

from aoep_shared.refund_policy import (
    CERTIFICATE_ISSUED, ELIGIBLE, NEEDS_REVIEW, NOT_PAID, STORE_PURCHASE, TOO_MUCH_PROGRESS, WINDOW_PASSED, RefundPolicy, evaluate,
)

DAY = 86400.0
NOW = 1_800_000_000.0


def _order(days_ago=1.0, provider="stripe", status="paid"):
    return {"order_id": "SAL-1", "provider": provider, "status": status, "created_at": NOW - days_ago * DAY}


def _ev(order, **kw):
    kw.setdefault("progress_pct", 0.0)
    return evaluate(order, policy=RefundPolicy(), now=lambda: NOW, **kw)


def test_a_fresh_untouched_web_purchase_is_eligible_and_auto_approved():
    verdict = _ev(_order())
    assert verdict["eligible"] and verdict["reason"] == ELIGIBLE and verdict["auto"] and verdict["days_left"] == 13


def test_the_window_progress_and_certificate_rules():
    assert _ev(_order(days_ago=15))["reason"] == WINDOW_PASSED
    assert _ev(_order(), progress_pct=21)["reason"] == TOO_MUCH_PROGRESS
    assert _ev(_order(), progress_pct=20)["eligible"]  # the limit itself is allowed
    assert _ev(_order(), certificate_issued=True)["reason"] == CERTIFICATE_ISSUED
    assert not _ev(_order(), certificate_issued=True)["eligible"]


def test_unknown_progress_goes_to_a_person_not_a_silent_no():
    verdict = _ev(_order(), progress_pct=None)
    assert verdict["reason"] == NEEDS_REVIEW and not verdict["eligible"] and "Support" in verdict["message"]


def test_store_purchases_are_refunded_by_the_store():
    verdict = _ev(_order(provider="apple"))
    assert verdict["reason"] == STORE_PURCHASE and "App Store" in verdict["message"] and not verdict["eligible"]
    assert _ev(_order(provider="google"))["reason"] == STORE_PURCHASE


def test_closed_orders_are_not_refundable_twice():
    assert _ev(_order(status="refunded"))["reason"] == NOT_PAID


def test_every_number_is_configuration(monkeypatch):
    monkeypatch.setenv("REFUND_WINDOW_DAYS", "30")
    monkeypatch.setenv("REFUND_MAX_PROGRESS_PCT", "50")
    monkeypatch.setenv("REFUND_BLOCK_AFTER_CERTIFICATE", "0")
    monkeypatch.setenv("REFUND_AUTO_APPROVE", "0")
    policy = RefundPolicy.from_env()
    verdict = evaluate(_order(days_ago=25), progress_pct=40, certificate_issued=True, policy=policy, now=lambda: NOW)
    assert verdict["eligible"] and not verdict["auto"]  # eligible by the rules, but every request goes to support
    assert policy.public() == {"window_days": 30, "max_progress_pct": 50, "block_after_certificate": False, "auto_approve": False}
