"""Payment happens after login, on the server's price, bound to the account; entitled accounts never pay.

Nothing here talks to a processor: provider calls are replaced, and no real money moves.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error

import pytest
from fastapi.testclient import TestClient

from aoep_shared.purchases import PurchaseStore, _MemoryBackend
from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.types import CourseSlide, StudioCourse

COURSE = "drivers-ed"
USERS = {
    "Bearer user": {"id": "u1", "email": "u1@example.com", "tier": "free", "membership_class": "standard", "is_admin": False},
    "Bearer other": {"id": "u2", "email": "u2@example.com", "tier": "basic", "membership_class": "standard", "is_admin": False},
    "Bearer premium": {"id": "u3", "email": "u3@example.com", "tier": "premium", "membership_class": "vip", "is_admin": False},
    "Bearer admin": {"id": "u4", "email": "u4@example.com", "tier": "premium", "membership_class": "vip", "is_admin": True},
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    import theodore_course_studio.main as main_mod
    import theodore_course_studio.pay_routes as routes
    import theodore_course_studio.caller_claims as claims
    import theodore_course_studio.course_pay as pay

    shared = CourseBuilder(data_dir=tmp_path / "data")
    monkeypatch.setattr(main_mod, "_builder", shared)
    monkeypatch.setattr(main_mod._teach, "_builder", shared)
    shared.save_course(StudioCourse(
        course_id=COURSE, title="Driver's Education", category="other",
        slides=[CourseSlide(index=0, title="One", body="First."), CourseSlide(index=1, title="Two", body="Second.")],
    ))
    store = PurchaseStore(_MemoryBackend())
    monkeypatch.setattr(routes, "_store_factory", lambda: store)
    monkeypatch.setattr(claims, "_fetch_me", lambda auth: USERS.get(auth))
    monkeypatch.delenv("STUDIO_VERIFY_CLAIMS", raising=False)  # the paid gate must hold with the flag OFF
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    claims._CACHE.clear()
    calls = {"card": [], "paypal": []}

    def card(**kw):
        calls["card"].append(kw)
        return {"session_id": "cs_new", "url": "https://checkout.stripe.com/c/pay/cs_new", "provider": "stripe", "method": "card"}

    def paypal(**kw):
        calls["paypal"].append(kw)
        return {"session_id": "ORDER1", "url": "https://www.paypal.com/checkoutnow?token=ORDER1", "provider": "paypal", "method": "paypal"}

    monkeypatch.setattr(pay, "start_card_checkout", card)
    monkeypatch.setattr(pay, "start_paypal_checkout", paypal)
    return {"client": TestClient(main_mod.app), "store": store, "calls": calls, "pay": pay, "monkeypatch": monkeypatch}


def _hdr(token: str) -> dict:
    return {"authorization": token} if token else {}


def _checkout(client, token, **body):
    payload = {"course_id": COURSE, "method": "card", "return_url": "http://testserver/learn/drivers-ed"}
    payload.update(body)
    return client.post("/api/studio/pay/checkout", json=payload, headers=_hdr(token))


# ---- entitlement and the offer
def test_anonymous_never_gets_a_price(env):
    body = env["client"].get("/api/studio/entitlement", params={"course_id": COURSE}).json()
    assert body["entitlement"] == "login_required" and "offer" not in body


def test_a_standard_member_is_offered_the_server_price(env):
    body = env["client"].get("/api/studio/entitlement", params={"course_id": COURSE}, headers=_hdr("Bearer user")).json()
    assert body["entitlement"] == "must_pay" and body["offer"]["amount_cents"] == 1999 and body["offer"]["label"] == "$19.99"


@pytest.mark.parametrize("token", ["Bearer premium", "Bearer admin"])
def test_premium_and_admin_never_see_a_price(env, token):
    body = env["client"].get("/api/studio/entitlement", params={"course_id": COURSE}, headers=_hdr(token)).json()
    assert body["entitlement"] == "free" and "offer" not in body


# ---- checkout
def test_anonymous_checkout_is_refused_with_a_login_prompt(env):
    res = _checkout(env["client"], "")
    assert res.status_code == 401 and "Log in" in res.json()["detail"]
    assert not env["calls"]["card"] and not env["calls"]["paypal"]


def test_a_bogus_token_is_anonymous(env):
    assert _checkout(env["client"], "Bearer nobody").status_code == 401


def test_checkout_uses_the_servers_price_title_and_the_verified_account(env):
    res = _checkout(env["client"], "Bearer user", amount_cents=1, price=1, title="Free!", learner_id="victim", account_id="victim")
    assert res.status_code == 200, res.text
    sent = env["calls"]["card"][0]
    assert sent["amount_cents"] == 1999 and sent["account_id"] == "u1" and sent["title"] == "Driver's Education"
    assert sent["email"] == "u1@example.com"
    assert res.json()["url"].startswith("https://checkout.stripe.com/") and res.json()["label"] == "$19.99"


def test_paypal_checkout_is_also_account_bound(env):
    res = _checkout(env["client"], "Bearer user", method="paypal")
    assert res.status_code == 200 and env["calls"]["paypal"][0]["account_id"] == "u1"


@pytest.mark.parametrize("token", ["Bearer premium", "Bearer admin"])
def test_entitled_accounts_get_no_checkout(env, token):
    res = _checkout(env["client"], token)
    assert res.status_code == 200 and res.json()["already_entitled"] is True and not env["calls"]["card"]


def test_an_account_that_already_paid_gets_no_second_checkout(env):
    env["store"].record_paid(account_id="u1", course_id=COURSE, amount_cents=1999, provider="stripe", provider_ref="cs_old")
    res = _checkout(env["client"], "Bearer user")
    assert res.json()["already_entitled"] is True and res.json()["entitlement"] == "paid"


def test_unknown_course_and_bad_method_and_offsite_return(env):
    assert _checkout(env["client"], "Bearer user", course_id="not-for-sale").status_code == 404
    assert _checkout(env["client"], "Bearer user", method="bitcoin").status_code == 422
    assert _checkout(env["client"], "Bearer user", return_url="https://evil.example/x").status_code == 400


def test_processor_failures_become_a_friendly_message_not_raw_text(env):
    def boom(**kw):
        raise RuntimeError("payment processor returned 401: sk_live_secret rejected")

    def offline(**kw):
        raise urllib.error.URLError("dns")

    env["monkeypatch"].setattr(env["pay"], "start_card_checkout", boom)
    res = _checkout(env["client"], "Bearer user")
    assert res.status_code == 503 and "sk_live" not in res.text and "try again" in res.json()["detail"].lower()
    env["monkeypatch"].setattr(env["pay"], "start_card_checkout", offline)
    assert _checkout(env["client"], "Bearer user").status_code == 503


def test_the_ledger_being_unavailable_pauses_payments_instead_of_granting(env):
    from aoep_shared.purchases import PurchaseStoreUnavailable
    import theodore_course_studio.pay_routes as routes

    def down():
        raise PurchaseStoreUnavailable("no redis")

    env["monkeypatch"].setattr(routes, "_store_factory", down)
    assert _checkout(env["client"], "Bearer user").status_code == 503


# ---- return-page confirmation
def _paid_session(account="u1", amount=1999, ref="cs_paid", status="paid"):
    return {"id": ref, "payment_status": status, "client_reference_id": f"{account}:{COURSE}",
            "metadata": {"account_id": account, "course_id": COURSE}, "amount_total": amount, "total_details": {"amount_tax": 0},
            "currency": "usd", "customer_details": {"email": "u1@example.com"}, "payment_intent": "pi_1"}


def test_confirm_records_a_paid_order_once(env):
    env["monkeypatch"].setattr(env["pay"], "card_session", lambda sid: _paid_session(ref=sid))
    first = env["client"].post("/api/studio/pay/confirm", json={"session_id": "cs_paid"}, headers=_hdr("Bearer user"))
    again = env["client"].post("/api/studio/pay/confirm", json={"session_id": "cs_paid"}, headers=_hdr("Bearer user"))
    assert first.status_code == 200 and first.json()["created"] is True
    assert again.status_code == 200 and again.json()["created"] is False and again.json()["order_id"] == first.json()["order_id"]
    assert env["store"].is_paid("u1", COURSE)


def test_confirm_refuses_anonymous_unpaid_foreign_and_underpaid(env):
    env["monkeypatch"].setattr(env["pay"], "card_session", lambda sid: _paid_session(ref=sid))
    assert env["client"].post("/api/studio/pay/confirm", json={"session_id": "cs_paid"}).status_code == 401
    assert env["client"].post("/api/studio/pay/confirm", json={"session_id": "cs_paid"}, headers=_hdr("Bearer other")).status_code == 403
    assert not env["store"].is_paid("u2", COURSE)
    env["monkeypatch"].setattr(env["pay"], "card_session", lambda sid: _paid_session(ref=sid, status="unpaid"))
    assert env["client"].post("/api/studio/pay/confirm", json={"session_id": "cs_x"}, headers=_hdr("Bearer user")).status_code == 402
    env["monkeypatch"].setattr(env["pay"], "card_session", lambda sid: _paid_session(ref=sid, amount=100))
    assert env["client"].post("/api/studio/pay/confirm", json={"session_id": "cs_cheap"}, headers=_hdr("Bearer user")).status_code == 402
    assert not env["store"].is_paid("u1", COURSE)


def test_one_payment_cannot_be_replayed_onto_another_account(env):
    env["monkeypatch"].setattr(env["pay"], "card_session", lambda sid: _paid_session(account="u1", ref=sid))
    env["client"].post("/api/studio/pay/confirm", json={"session_id": "cs_paid"}, headers=_hdr("Bearer user"))
    res = env["client"].post("/api/studio/pay/confirm", json={"session_id": "cs_paid"}, headers=_hdr("Bearer other"))
    assert res.status_code == 403 and not env["store"].is_paid("u2", COURSE)


# ---- Stripe webhook
def _stripe_post(env, event, secret="whsec_test", ts=None):
    body = json.dumps(event).encode()
    stamp = int(ts if ts is not None else time.time())
    sig = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return env["client"].post("/api/studio/pay/webhook/stripe", content=body, headers={"stripe-signature": f"t={stamp},v1={sig}"})


def test_a_signed_webhook_grants_the_course_and_a_duplicate_changes_nothing(env):
    event = {"type": "checkout.session.completed", "data": {"object": _paid_session()}}
    assert _stripe_post(env, event).status_code == 200
    assert _stripe_post(env, event).status_code == 200
    assert env["store"].is_paid("u1", COURSE) and len(env["store"].list_for_account("u1")) == 1


def test_forged_stale_and_unconfigured_webhooks_are_refused(env):
    event = {"type": "checkout.session.completed", "data": {"object": _paid_session()}}
    assert _stripe_post(env, event, secret="attacker").status_code == 400
    assert _stripe_post(env, event, ts=time.time() - 3600).status_code == 400
    assert env["client"].post("/api/studio/pay/webhook/stripe", json=event).status_code == 400
    env["monkeypatch"].delenv("STRIPE_WEBHOOK_SECRET")
    assert _stripe_post(env, event).status_code == 400
    assert not env["store"].is_paid("u1", COURSE)


def test_a_refund_or_dispute_revokes_access(env):
    _stripe_post(env, {"type": "checkout.session.completed", "data": {"object": _paid_session()}})
    assert env["store"].is_paid("u1", COURSE)
    assert _stripe_post(env, {"type": "charge.refunded", "data": {"object": {"payment_intent": "pi_1"}}}).status_code == 200
    assert not env["store"].is_paid("u1", COURSE)


# ---- PayPal webhook
def test_paypal_webhook_needs_paypals_verification(env):
    event = {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {
        "id": "CAP1", "custom_id": f"u1:{COURSE}", "amount": {"value": "19.99"},
        "supplementary_data": {"related_ids": {"order_id": "ORDER1"}}}}
    env["monkeypatch"].setattr(env["pay"], "verify_paypal_webhook", lambda *a, **k: False)
    assert env["client"].post("/api/studio/pay/webhook/paypal", json=event).status_code == 400
    assert not env["store"].is_paid("u1", COURSE)
    env["monkeypatch"].setattr(env["pay"], "verify_paypal_webhook", lambda *a, **k: True)
    assert env["client"].post("/api/studio/pay/webhook/paypal", json=event).status_code == 200
    assert env["store"].is_paid("u1", COURSE)
    refund = {"event_type": "PAYMENT.CAPTURE.REFUNDED", "resource": {"supplementary_data": {"related_ids": {"order_id": "ORDER1"}}}}
    env["client"].post("/api/studio/pay/webhook/paypal", json=refund)
    assert not env["store"].is_paid("u1", COURSE)


# ---- the gate on the full course itself (flag OFF in these tests)
def _start(env, token="", **claims):
    body = {"session_id": f"s-{time.time_ns()}", "course_id": COURSE, "learner_id": f"l-{time.time_ns()}", "use_voice_agent": False}
    body.update(claims)
    res = env["client"].post("/api/studio/teach/start", json=body, headers=_hdr(token))
    assert res.status_code == 200, res.text
    return res.json()["access_mode"]


def test_client_claims_cannot_open_the_paid_course_even_with_the_flag_off(env):
    assert _start(env, "", access="full", is_admin=True, registered=True, enrollment_status="paid") == "sample"
    assert _start(env, "", is_admin=True) == "sample"  # an empty access is no longer the authoring studio for a paid course
    assert _start(env, "Bearer user", access="full", is_admin=True, registered=True, enrollment_status="paid") == "sample"
    assert _start(env, "Bearer nobody", access="full", is_admin=True) == "sample"


def test_identity_outage_fails_closed_to_the_sample(env):
    env["monkeypatch"].setattr("theodore_course_studio.caller_claims._fetch_me", lambda auth: None)
    assert _start(env, "Bearer admin", access="full") == "sample"


def test_entitled_accounts_get_the_full_course(env):
    assert _start(env, "Bearer premium", access="full") == "full"
    assert _start(env, "Bearer admin", access="full") == "full"
    assert _start(env, "Bearer user", access="full") == "sample"
    env["store"].record_paid(account_id="u1", course_id=COURSE, amount_cents=1999, provider="stripe", provider_ref="cs_9")
    assert _start(env, "Bearer user", access="full") == "full"
    assert _start(env, "Bearer user", access="sample") == "sample"  # the demo is always the demo


def test_a_refund_closes_the_course_again(env):
    order, _ = env["store"].record_paid(account_id="u1", course_id=COURSE, amount_cents=1999, provider="stripe", provider_ref="cs_9")
    assert _start(env, "Bearer user", access="full") == "full"
    env["store"].mark_refunded(order["order_id"], reason="requested", by="admin")
    assert _start(env, "Bearer user", access="full") == "sample"


# ---- purchases list
def test_purchases_list_is_private_to_the_account(env):
    env["store"].record_paid(account_id="u1", course_id=COURSE, amount_cents=1999, provider="stripe", provider_ref="cs_9")
    assert env["client"].get("/api/studio/account/purchases").status_code == 401
    mine = env["client"].get("/api/studio/account/purchases", headers=_hdr("Bearer user")).json()["purchases"]
    assert [p["course_id"] for p in mine] == [COURSE] and "provider_ref" not in mine[0]
    assert env["client"].get("/api/studio/account/purchases", headers=_hdr("Bearer other")).json()["purchases"] == []


# ---- the login cookie authenticates like a bearer, and cross-site posts are refused
def test_the_session_cookie_authenticates_like_a_bearer(env):
    env["client"].cookies.set("aoep_session", "user")
    env["monkeypatch"].setattr("theodore_course_studio.caller_claims._fetch_me", lambda auth: USERS["Bearer user"] if auth == "Bearer user" else None)
    body = env["client"].get("/api/studio/entitlement", params={"course_id": COURSE}).json()
    assert body["entitlement"] == "must_pay"
    assert _start(env, "", access="full") == "sample"  # a standard member's cookie still opens only the sample


def test_a_cross_site_post_is_refused_even_with_a_valid_login(env):
    res = env["client"].post(
        "/api/studio/pay/checkout", headers={**_hdr("Bearer user"), "origin": "https://evil.example"},
        json={"course_id": COURSE, "method": "card", "return_url": "http://testserver/x"},
    )
    assert res.status_code == 403 and not env["calls"]["card"]
