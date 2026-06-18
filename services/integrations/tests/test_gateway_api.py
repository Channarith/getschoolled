"""Integrations gateway API tests (Phase 16)."""

from fastapi.testclient import TestClient

from aoep_shared.webhooks import sign_payload
from integrations.main import app

client = TestClient(app)


def test_subscription_and_emit_delivers():
    sub = client.post("/webhooks/subscriptions", json={
        "url": "https://partner.test/hook", "event_types": ["enrollment.paid"], "secret": "s1",
    }).json()
    assert sub["id"]

    out = client.post("/webhooks/emit", json={
        "event_type": "enrollment.paid", "data": {"course": "bio"}}).json()
    assert out["total"] == 1 and out["delivered"] == 1


def test_emit_skips_nonmatching():
    client.post("/webhooks/subscriptions", json={
        "url": "https://p2.test/hook", "event_types": ["refund"], "secret": "s"})
    out = client.post("/webhooks/emit", json={"event_type": "some.other.event"}).json()
    # No subscription matches this brand-new event type.
    assert out["delivered"] == 0


def test_inbound_signature_verified():
    body = b'{"type":"checkout.completed"}'
    sig = sign_payload(body, "dev-webhook-secret")
    ok = client.post("/webhooks/inbound/stripe", content=body,
                     headers={"X-AOEP-Signature": sig})
    assert ok.status_code == 200 and ok.json()["accepted"] is True

    bad = client.post("/webhooks/inbound/stripe", content=body,
                      headers={"X-AOEP-Signature": "deadbeef"})
    assert bad.status_code == 401


def test_create_api_client():
    c = client.post("/clients", json={"name": "Partner LMS", "scopes": ["catalog:read"]}).json()
    assert c["api_key"].startswith("aoep_")
    assert "catalog:read" in c["scopes"]
