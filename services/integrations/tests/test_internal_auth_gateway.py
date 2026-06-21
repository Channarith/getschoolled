"""Integrations management endpoints (webhook subscriptions +
emit, finance payout, API-client minting) must be locked to
internal callers.

These endpoints can mint API keys, register outbound webhook
targets, push payouts, and trigger arbitrary outbound webhook
emissions - all production-sensitive actions that must not be
reachable by an anonymous web caller.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from integrations.main import app


GATED_ROUTES = [
    ("POST", "/webhooks/subscriptions",
     {"url": "https://example.com/hook"}),
    ("GET",  "/webhooks/subscriptions", None),
    ("POST", "/webhooks/emit",
     {"event_type": "test.event", "data": {}}),
    ("POST", "/finance/payout",
     {"account": "acct_x", "amount": 1.0}),
    ("POST", "/clients", {"name": "partner-a", "scopes": []}),
    ("GET",  "/clients", None),
]


@pytest.fixture(autouse=True)
def _enable_internal_auth(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)


@pytest.mark.parametrize("method,path,body", GATED_ROUTES)
def test_gated_endpoint_denied_without_internal_token(method, path, body):
    client = TestClient(app)
    r = client.get(path) if method == "GET" else client.post(path, json=body or {})
    assert r.status_code in (401, 403), (
        f"{method} {path} should require internal auth, got "
        f"{r.status_code}: {r.text!r}"
    )


def test_inbound_webhook_secret_fails_closed_in_cloud_mode(monkeypatch):
    """In cloud mode, an unset WEBHOOK_SIGNING_KEY must NOT fall
    back to the well-known 'dev-webhook-secret'. The audit found
    this fallback could let an attacker who knows the dev secret
    forge inbound webhook payloads in production."""
    monkeypatch.delenv("WEBHOOK_SIGNING_KEY", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("DEPLOY_MODE", "cloud")

    client = TestClient(app)
    # Send a payload signed with the legacy dev secret; it must NOT verify.
    import hashlib
    import hmac
    body = b'{"hello":"world"}'
    sig = hmac.new(b"dev-webhook-secret", body, hashlib.sha256).hexdigest()
    r = client.post(
        "/webhooks/inbound/stripe",
        content=body,
        headers={"X-AOEP-Signature": sig,
                 "Content-Type": "application/json"},
    )
    assert r.status_code == 401, (
        f"cloud-mode inbound webhook with dev secret should fail, "
        f"got {r.status_code}: {r.text!r}"
    )


def test_inbound_webhook_secret_allows_dev_in_local_mode(monkeypatch):
    """Local deploy mode still accepts the dev secret so the OSS
    quickstart and tests work without configuration."""
    monkeypatch.delenv("WEBHOOK_SIGNING_KEY", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("DEPLOY_MODE", "local")

    client = TestClient(app)
    import hashlib
    import hmac
    body = b'{"hello":"world"}'
    sig = hmac.new(b"dev-webhook-secret", body, hashlib.sha256).hexdigest()
    r = client.post(
        "/webhooks/inbound/stripe",
        content=body,
        headers={"X-AOEP-Signature": sig,
                 "Content-Type": "application/json"},
    )
    assert r.status_code == 200, (
        f"local-mode inbound webhook with dev secret should pass, "
        f"got {r.status_code}: {r.text!r}"
    )
