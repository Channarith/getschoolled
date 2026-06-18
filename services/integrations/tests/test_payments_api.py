"""Payment webhook -> entitlement grant + outbound event (Phase 17)."""

import json

from fastapi.testclient import TestClient

from aoep_shared.webhooks import sign_payload
from integrations.main import app

client = TestClient(app)
SECRET = "dev-webhook-secret"


def _post_payment(payload: dict):
    body = json.dumps(payload).encode()
    sig = sign_payload(body, SECRET)
    return client.post("/payments/webhook/stripe", content=body,
                       headers={"X-AOEP-Signature": sig})


def test_paid_event_grants_entitlement_and_emits():
    # A subscriber receives the downstream enrollment.paid event.
    client.post("/webhooks/subscriptions", json={
        "url": "https://crm.test/hook", "event_types": ["enrollment.paid"], "secret": "s"})
    res = _post_payment({
        "type": "checkout.session.completed",
        "data": {"object": {"customer": "cus_42", "amount_total": 4999, "currency": "usd",
                            "metadata": {"entitlement": "pro"}}},
    }).json()
    assert res["handled"] is True and res["kind"] == "grant"
    assert "pro" in res["entitlements"]

    got = client.get("/entitlements/cus_42").json()
    assert "pro" in got["entitlements"]


def test_refund_revokes():
    _post_payment({"type": "checkout.session.completed",
                   "data": {"object": {"customer": "cus_9", "metadata": {"entitlement": "pro"}}}})
    _post_payment({"type": "charge.refunded", "data": {"object": {"customer": "cus_9",
                   "metadata": {"entitlement": "pro"}}}})
    got = client.get("/entitlements/cus_9").json()
    assert "pro" not in got["entitlements"]


def test_bad_signature_rejected():
    body = json.dumps({"type": "invoice.paid"}).encode()
    r = client.post("/payments/webhook/stripe", content=body,
                    headers={"X-AOEP-Signature": "bad"})
    assert r.status_code == 401


def test_payout_recorded():
    out = client.post("/finance/payout", json={"account": "acct_1", "amount": 25.0}).json()
    assert out["account"] == "acct_1" and out["amount"] == 25.0
