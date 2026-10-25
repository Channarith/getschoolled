"""Tax at checkout, receipts, email, refunds (customer and admin), policy. No processor is contacted."""

from __future__ import annotations

import time

import pytest

from test_pay_routes import COURSE, USERS, _checkout, _hdr, _paid_session, _start, env  # noqa: F401  (env is the fixture)

PAID_NOW = {"account_id": "u1", "course_id": COURSE, "amount_cents": 1999, "provider": "stripe", "provider_ref": "cs_r1",
            "email": "u1@example.com", "last4": "4242", "meta": {"payment_intent": "pi_r1"}}


def _buy(env, **over):
    args = {**PAID_NOW, **over}
    order, _ = env["store"].record_paid(**args)
    return order


@pytest.fixture
def refunds(env):
    calls = {"stripe": [], "paypal": []}
    env["monkeypatch"].setattr(env["pay"], "stripe_refund", lambda pi, amount, **kw: calls["stripe"].append((pi, amount, kw)) or {"id": "re_1"})
    env["monkeypatch"].setattr(env["pay"], "paypal_refund", lambda cap, amount, **kw: calls["paypal"].append((cap, amount, kw)) or {"id": "R1"})
    return calls


# ---- tax at checkout
def test_manual_tax_asks_for_a_state_then_adds_a_tax_line(env, monkeypatch):
    monkeypatch.setenv("COURSE_TAX_MODE", "manual")
    monkeypatch.setenv("COURSE_TAX_RATES_JSON", '{"CA": 0.0725}')
    missing = _checkout(env["client"], "Bearer user")
    assert missing.status_code == 422 and "state" in missing.json()["detail"].lower()
    ok = _checkout(env["client"], "Bearer user", billing_state="CA")
    assert ok.status_code == 200 and env["calls"]["card"][0]["tax_cents"] == 145
    quote = env["client"].get("/api/studio/pay/quote", params={"course_id": COURSE, "state": "CA"}, headers=_hdr("Bearer user")).json()
    assert (quote["amount_cents"], quote["tax_cents"], quote["total_cents"], quote["total_label"]) == (1999, 145, 2144, "$21.44")


def test_no_tax_mode_asks_for_no_location_and_adds_nothing(env):
    assert _checkout(env["client"], "Bearer user").status_code == 200 and env["calls"]["card"][0]["tax_cents"] == 0


def test_a_quote_needs_a_login(env):
    assert env["client"].get("/api/studio/pay/quote", params={"course_id": COURSE}).status_code == 401


def test_provider_tax_mode_asks_stripe_to_calculate(env, monkeypatch):
    monkeypatch.setenv("COURSE_TAX_MODE", "provider")
    _checkout(env["client"], "Bearer user")
    assert env["calls"]["card"][0]["automatic_tax"] is True


# ---- receipts
def test_a_receipt_is_private_to_the_buyer(env):
    order = _buy(env)
    url = f"/api/studio/account/receipts/{order['order_id']}.html"
    assert env["client"].get(url).status_code == 401
    assert env["client"].get(url, headers=_hdr("Bearer other")).status_code == 404  # someone else's order looks like nothing
    page = env["client"].get(url, headers=_hdr("Bearer user"))
    assert page.status_code == 200 and "SAL-" in page.text and "ending 4242" in page.text and "no-store" in page.headers["cache-control"]


def test_pdf_receipt_downloads_when_available(env):
    order = _buy(env)
    res = env["client"].get(f"/api/studio/account/receipts/{order['order_id']}.pdf", headers=_hdr("Bearer user"))
    assert res.status_code in (200, 501)
    if res.status_code == 200:
        assert res.content.startswith(b"%PDF") and res.headers["content-type"] == "application/pdf"


def test_the_receipt_code_verifies_and_a_tampered_one_does_not(env):
    from aoep_shared import receipts

    order = _buy(env)
    good = receipts.verification_code(order)
    ok = env["client"].get("/api/studio/receipts/verify", params={"order": order["order_id"], "code": good}).json()
    assert ok["valid"] is True and ok["total"] == "$19.99" and "email" not in ok
    assert env["client"].get("/api/studio/receipts/verify", params={"order": order["order_id"], "code": "0" * 16}).json() == {"valid": False}
    assert env["client"].get("/api/studio/receipts/verify", params={"order": "SAL-nope", "code": good}).json() == {"valid": False}


def test_email_me_this_receipt_is_honest_when_nothing_can_send(env, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    order = _buy(env)
    res = env["client"].post(f"/api/studio/account/receipts/{order['order_id']}/email", headers=_hdr("Bearer user"))
    assert res.status_code == 503 and "PDF" in res.json()["detail"]


def test_email_sends_once_and_a_second_request_is_a_no_op(env, monkeypatch):
    from aoep_shared import receipts

    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(receipts, "send_receipt_email", lambda receipt, to, **kw: sent.append(to) or {"sent": True, "reason": ""})
    order = _buy(env)
    url = f"/api/studio/account/receipts/{order['order_id']}/email"
    first = env["client"].post(url, headers=_hdr("Bearer user"))
    second = env["client"].post(url, headers=_hdr("Bearer user"))
    assert first.json() == {"sent": True, "already_sent": False} and second.json() == {"sent": False, "already_sent": True}
    assert sent == ["u1@example.com"]


def test_confirming_a_payment_emails_the_receipt_when_smtp_is_configured(env, monkeypatch):
    from aoep_shared import receipts

    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(receipts, "send_receipt_email", lambda receipt, to, **kw: sent.append(receipt["order_id"]) or {"sent": True, "reason": ""})
    env["monkeypatch"].setattr(env["pay"], "card_session", lambda sid: _paid_session(ref=sid))
    env["client"].post("/api/studio/pay/confirm", json={"session_id": "cs_paid"}, headers=_hdr("Bearer user"))
    env["client"].post("/api/studio/pay/confirm", json={"session_id": "cs_paid"}, headers=_hdr("Bearer user"))
    assert len(sent) == 1  # one receipt per order, however many times the return page loads


def test_the_purchase_list_carries_the_receipt_link_and_refund_status(env):
    order = _buy(env)
    row = env["client"].get("/api/studio/account/purchases", headers=_hdr("Bearer user")).json()["purchases"][0]
    assert row["receipt_url"].endswith(f"{order['order_id']}.html") and row["refund"]["eligible"] is True


# ---- customer refunds
def _refund(env, token="Bearer user", order_id=None, **kw):
    return env["client"].post(f"/api/studio/account/purchases/{order_id}/refund-request", headers=_hdr(token), **kw)


def test_an_untouched_recent_purchase_is_refunded_automatically_and_access_ends(env, refunds):
    order = _buy(env)
    res = _refund(env, order_id=order["order_id"])
    assert res.status_code == 200 and res.json()["refunded"] is True and "credit-note" in res.json()["credit_note_url"]
    assert refunds["stripe"][0][:2] == ("pi_r1", 1999) and refunds["stripe"][0][2]["order_id"] == order["order_id"]
    assert env["store"].get(order["order_id"])["status"] == "refunded" and not env["store"].is_paid("u1", COURSE)
    assert _start(env, "Bearer user", access="full") == "sample"  # the class is closed again
    again = _refund(env, order_id=order["order_id"])
    assert again.json()["refunded"] is False and len(refunds["stripe"]) == 1  # no second refund, ever


def test_a_credit_note_exists_only_after_a_refund(env, refunds):
    order = _buy(env)
    url = f"/api/studio/account/receipts/{order['order_id']}.html?type=credit-note"
    assert env["client"].get(url, headers=_hdr("Bearer user")).status_code == 404
    _refund(env, order_id=order["order_id"])
    note = env["client"].get(url, headers=_hdr("Bearer user"))
    assert note.status_code == 200 and "Credit note" in note.text and "Refunded:" in note.text


def test_a_learner_who_opened_the_class_is_routed_to_support_not_refused_silently(env, refunds):
    order = _buy(env)
    assert _start(env, "Bearer user", access="full") == "full"
    res = _refund(env, order_id=order["order_id"]).json()
    assert res["refunded"] is False and res["routed_to_support"] is True and "review" in res["message"].lower()
    assert not refunds["stripe"] and env["store"].is_paid("u1", COURSE)
    assert env["store"].get(order["order_id"])["meta"]["refund_requested"]["reason"] == "needs_review"
    assert any(row["event"] == "refund_requested" for row in env["store"].audit_log())
    listed = env["client"].get("/api/studio/account/purchases", headers=_hdr("Bearer user")).json()["purchases"][0]
    assert listed["refund_requested"] is True


def test_after_the_window_the_request_goes_to_support(env, refunds):
    order = _buy(env)
    old = env["store"].get(order["order_id"])
    old["created_at"] -= 20 * 86400
    env["store"]._save(old)
    res = _refund(env, order_id=order["order_id"]).json()
    assert res["refunded"] is False and res["reason"] == "window_passed" and res["routed_to_support"] is True and not refunds["stripe"]


def test_store_purchases_are_sent_to_the_store(env, refunds):
    order = _buy(env, provider="apple", provider_ref="tx-1", meta={})
    res = _refund(env, order_id=order["order_id"]).json()
    assert res["refunded"] is False and "App Store" in res["message"] and res["routed_to_support"] is False and not refunds["stripe"]


def test_a_provider_failure_changes_nothing_and_says_so(env):
    def boom(*a, **k):
        raise RuntimeError("stripe returned 500")

    env["monkeypatch"].setattr(env["pay"], "stripe_refund", boom)
    order = _buy(env)
    res = _refund(env, order_id=order["order_id"])
    assert res.status_code == 503 and "Nothing was changed" in res.json()["detail"] and "stripe returned" not in res.text
    assert env["store"].is_paid("u1", COURSE)


def test_you_cannot_refund_someone_elses_purchase_or_post_cross_site(env, refunds):
    order = _buy(env)
    assert _refund(env, "Bearer other", order_id=order["order_id"]).status_code == 404
    assert env["client"].post(f"/api/studio/account/purchases/{order['order_id']}/refund-request",
                              headers={**_hdr("Bearer user"), "origin": "https://evil.example"}).status_code == 403
    assert env["client"].post(f"/api/studio/account/purchases/{order['order_id']}/refund-request").status_code == 401
    assert not refunds["stripe"] and env["store"].is_paid("u1", COURSE)


def test_support_only_mode_sends_every_request_to_a_person(env, refunds, monkeypatch):
    monkeypatch.setenv("REFUND_AUTO_APPROVE", "0")
    order = _buy(env)
    res = _refund(env, order_id=order["order_id"]).json()
    assert res["refunded"] is False and not refunds["stripe"]


def test_a_late_duplicate_payment_event_does_not_reopen_a_refunded_class(env, refunds):
    order = _buy(env)
    _refund(env, order_id=order["order_id"])
    env["store"].record_paid(**{**PAID_NOW, "meta": {}})  # the webhook for the same session arrives after the refund
    assert not env["store"].is_paid("u1", COURSE)


# ---- admin refunds
def test_only_a_verified_admin_can_refund_through_the_provider(env, refunds):
    order = _buy(env)
    url = f"/api/studio/admin/purchases/{order['order_id']}/refund"
    assert env["client"].post(url, json={}).status_code == 401
    assert env["client"].post(url, json={}, headers=_hdr("Bearer user")).status_code == 403
    assert env["client"].post(url, json={"is_admin": True}, headers=_hdr("Bearer premium")).status_code == 403  # a claim is nothing
    assert not refunds["stripe"] and env["store"].is_paid("u1", COURSE)
    ok = env["client"].post(url, json={"reason": "goodwill"}, headers=_hdr("Bearer admin"))
    assert ok.status_code == 200 and ok.json()["amount_cents"] == 1999 and refunds["stripe"][0][1] == 1999
    assert env["store"].get(order["order_id"])["refunded"]["by"] == "u4"
    again = env["client"].post(url, json={}, headers=_hdr("Bearer admin")).json()
    assert again["already"] is True and len(refunds["stripe"]) == 1


def test_admin_partial_refund_amount_is_validated_and_paypal_uses_its_capture(env, refunds):
    order = _buy(env, provider="paypal", provider_ref="ORDER9", meta={"capture_id": "CAP9"})
    url = f"/api/studio/admin/purchases/{order['order_id']}/refund"
    assert env["client"].post(url, json={"amount_cents": 0}, headers=_hdr("Bearer admin")).status_code == 422
    assert env["client"].post(url, json={"amount_cents": 99999}, headers=_hdr("Bearer admin")).status_code == 422
    assert env["client"].post("/api/studio/admin/purchases/SAL-nope/refund", json={}, headers=_hdr("Bearer admin")).status_code == 404
    ok = env["client"].post(url, json={"amount_cents": 1000}, headers=_hdr("Bearer admin"))
    assert ok.status_code == 200 and refunds["paypal"][0][:2] == ("CAP9", 1000)


# ---- policy
def test_the_policy_endpoint_reports_what_the_server_enforces(env, monkeypatch):
    base = env["client"].get("/api/studio/policy").json()
    assert base["draft"] is True and base["refund"] == {"window_days": 14, "max_progress_pct": 20, "block_after_certificate": True, "auto_approve": True}
    assert "not a DMV-approved" in base["disclaimer"] and base["seller"]["legal_name"] == "[to be set by the seller]"
    monkeypatch.setenv("REFUND_WINDOW_DAYS", "30")
    assert env["client"].get("/api/studio/policy").json()["refund"]["window_days"] == 30
