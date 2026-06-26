"""Billing validation helpers."""

from datetime import datetime

from aoep_shared.billing_validation import (
    luhn_valid,
    mask_card_last4,
    validate_billing_address,
    validate_card,
)


def test_luhn_accepts_test_visa():
    assert luhn_valid("4242424242424242")


def test_luhn_rejects_bad_number():
    assert not luhn_valid("4242424242424241")


def test_validate_card_expired():
    errs = validate_card("4242424242424242", 1, 2020, "123", now=datetime(2026, 1, 1))
    assert any("expired" in e for e in errs)


def test_validate_us_address_requires_state():
    errs = validate_billing_address(
        line1="123 Main St", city="Austin", postal_code="78701", country="US", state="",
    )
    assert any("state" in e for e in errs)


def test_mask_last4():
    assert mask_card_last4("4242424242424242") == "4242"
