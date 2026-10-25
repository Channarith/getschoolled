"""Provider calls for a course purchase: server price, account binding, signed webhooks. No real money moves here."""

from __future__ import annotations

import hashlib
import hmac
import json

from theodore_course_studio.course_pay import (
    paid_from_paypal_order, paid_from_stripe_session, same_site_return, start_card_checkout, start_paypal_checkout,
    verify_paypal_webhook, verify_stripe_signature,
)


class _Body:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> bool:
        return False


def test_return_url_must_stay_on_this_site():
    kept = same_site_return("http://testserver/studio?access=sample&paid=1", "testserver")
    assert kept == "http://testserver/studio?access=sample"
    try:
        same_site_return("https://evil.example/steal", "testserver")
    except ValueError as exc:
        assert "stay on this site" in str(exc)
    else:
        raise AssertionError("off-site return was accepted")


def test_card_checkout_uses_the_server_price_and_binds_the_account(monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY", "sk_test_example")
    seen = {}

    def opener(request, timeout=30):
        seen.update(url=request.full_url, body=request.data.decode(), auth=request.headers["Authorization"])
        return _Body({"id": "cs_test_123", "url": "https://checkout.stripe.com/c/pay/cs_test_123"})

    session = start_card_checkout(
        account_id="acct-1", course_id="drivers-ed", title="Driver's Education", amount_cents=1999,
        return_url="http://testserver/studio", email="a@example.com", opener=opener,
    )
    assert session["url"].startswith("https://checkout.stripe.com/")
    body = seen["body"]
    assert "unit_amount%5D=1999" in body or "unit_amount]=1999" in body
    assert "metadata%5Baccount_id%5D=acct-1" in body or "metadata[account_id]=acct-1" in body
    assert "customer_email" in body and "{CHECKOUT_SESSION_ID}" in body
    assert "card_number" not in body and "automatic_tax" not in body
    assert seen["auth"] == "Bearer sk_test_example"


def test_card_checkout_can_ask_stripe_to_calculate_tax(monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY", "sk_test_example")
    seen = {}
    start_card_checkout(
        account_id="a", course_id="drivers-ed", title="T", amount_cents=1999, return_url="http://t/s", automatic_tax=True,
        opener=lambda request, timeout=30: (seen.update(body=request.data.decode()), _Body({"id": "cs_1", "url": "https://x"}))[1],
    )
    assert "automatic_tax" in seen["body"] and "tax_behavior" in seen["body"]


def test_paypal_checkout_amount_comes_from_the_server_price(monkeypatch):
    monkeypatch.setenv("PAYPAL_API_KEY", "client")
    monkeypatch.setenv("PAYPAL_API_SECRET", "secret")
    calls = []

    def opener(request, timeout=30):
        calls.append((request.full_url, request.data))
        if request.full_url.endswith("/v1/oauth2/token"):
            return _Body({"access_token": "tok"})
        return _Body({"id": "ORDER1", "links": [{"rel": "approve", "href": "https://www.paypal.com/checkoutnow?token=ORDER1"}]})

    session = start_paypal_checkout(
        account_id="acct-1", course_id="drivers-ed", title="Driver's Education", amount_cents=1999,
        return_url="http://testserver/studio", opener=opener,
    )
    assert session["session_id"] == "ORDER1" and "paypal.com" in session["url"]
    order = json.loads([data for url, data in calls if url.endswith("/v2/checkout/orders")][0])
    assert order["purchase_units"][0]["amount"]["value"] == "19.99"
    assert order["purchase_units"][0]["custom_id"] == "acct-1:drivers-ed"


def test_a_stripe_session_normalizes_only_when_paid():
    base = {"id": "cs_1", "client_reference_id": "acct-1:drivers-ed", "metadata": {"account_id": "acct-1", "course_id": "drivers-ed"},
            "amount_total": 2144, "total_details": {"amount_tax": 145}, "currency": "usd",
            "customer_details": {"email": "a@example.com"}, "payment_intent": "pi_1"}
    assert paid_from_stripe_session({**base, "payment_status": "unpaid"}) is None
    paid = paid_from_stripe_session({**base, "payment_status": "paid"})
    assert (paid["account_id"], paid["course_id"], paid["amount_cents"], paid["tax_cents"]) == ("acct-1", "drivers-ed", 1999, 145)
    assert paid["provider_ref"] == "cs_1" and paid["payment_intent"] == "pi_1"


def test_a_paypal_order_normalizes_only_when_completed():
    order = {"id": "O1", "status": "COMPLETED", "payer": {"email_address": "p@example.com"},
             "purchase_units": [{"custom_id": "acct-1:drivers-ed", "payments": {"captures": [{"id": "CAP1", "amount": {"value": "19.99"}}]}}]}
    paid = paid_from_paypal_order(order)
    assert (paid["account_id"], paid["amount_cents"], paid["capture_id"]) == ("acct-1", 1999, "CAP1")
    assert paid_from_paypal_order({**order, "status": "APPROVED"}) is None


def _sign(payload: bytes, secret: str, ts: int) -> str:
    return f"t={ts},v1=" + hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()


def test_stripe_signature_accepts_only_a_fresh_correct_signature():
    body, secret, now = b'{"type":"x"}', "whsec_test", 1_800_000_000
    assert verify_stripe_signature(body, _sign(body, secret, now), secret, now=lambda: now)
    assert not verify_stripe_signature(body, _sign(body, "wrong", now), secret, now=lambda: now)  # forged
    assert not verify_stripe_signature(b'{"type":"y"}', _sign(body, secret, now), secret, now=lambda: now)  # body changed
    assert not verify_stripe_signature(body, _sign(body, secret, now - 3600), secret, now=lambda: now)  # replay
    assert not verify_stripe_signature(body, "", secret, now=lambda: now)
    assert not verify_stripe_signature(body, _sign(body, secret, now), "", now=lambda: now)  # secret not configured
    rotated = _sign(body, "old", now) + "," + _sign(body, secret, now).split(",", 1)[1]
    assert verify_stripe_signature(body, rotated, secret, now=lambda: now)


def test_paypal_webhook_is_verified_by_paypals_own_api(monkeypatch):
    monkeypatch.setenv("PAYPAL_API_KEY", "c")
    monkeypatch.setenv("PAYPAL_API_SECRET", "s")
    headers = {"PayPal-Auth-Algo": "a", "PayPal-Cert-Url": "https://api.paypal.com/c", "PayPal-Transmission-Id": "t",
               "PayPal-Transmission-Sig": "s", "PayPal-Transmission-Time": "now"}

    def good(request, timeout=30):
        if request.full_url.endswith("/v1/oauth2/token"):
            return _Body({"access_token": "tok"})
        return _Body({"verification_status": "SUCCESS"})

    def bad(request, timeout=30):
        if request.full_url.endswith("/v1/oauth2/token"):
            return _Body({"access_token": "tok"})
        return _Body({"verification_status": "FAILURE"})

    body = json.dumps({"event_type": "PAYMENT.CAPTURE.COMPLETED"}).encode()
    assert verify_paypal_webhook(headers, body, "WH-1", opener=good)
    assert not verify_paypal_webhook(headers, body, "WH-1", opener=bad)
    assert not verify_paypal_webhook(headers, body, "", opener=good)  # webhook id not configured
    assert not verify_paypal_webhook({}, body, "WH-1", opener=good)  # no signature headers
