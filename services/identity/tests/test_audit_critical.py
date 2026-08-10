"""Audit: paid self-subscribe + PASSED without token blocked in cloud."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _signup(email: str, password: str = "S3cretpass"):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": password, "display_name": "Audit"},
    ).json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_subscribe_paid_denied_in_cloud(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.delenv("ALLOW_SANDBOX_SUBSCRIBE", raising=False)
    monkeypatch.delenv("PAYMENT_MODE", raising=False)
    tok = _signup("cloud-sub@example.com")["token"]
    r = client.post("/membership/subscribe", headers=_auth(tok), json={"tier": "premium"})
    assert r.status_code == 402, r.text
    me = client.get("/auth/me", headers=_auth(tok)).json()
    assert me["tier"] == "free"


def test_subscribe_free_still_ok_in_cloud(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    tok = _signup("cloud-free@example.com")["token"]
    r = client.post("/membership/subscribe", headers=_auth(tok), json={"tier": "free"})
    assert r.status_code == 200, r.text
    assert r.json()["tier"] == "free"


def test_onboarding_plan_paid_denied_in_cloud(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.delenv("ALLOW_SANDBOX_SUBSCRIBE", raising=False)
    tok = _signup("cloud-onboard@example.com")["token"]
    # Even with billing validated, cloud must not self-activate paid tiers.
    client.post(
        "/onboarding/billing",
        headers=_auth(tok),
        json={
            "line1": "1 Main",
            "city": "SF",
            "postal_code": "94105",
            "country": "US",
            "state": "CA",
            "card_number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "123",
        },
    )
    r = client.post("/onboarding/plan", headers=_auth(tok), json={"tier": "basic"})
    assert r.status_code == 402, r.text


def test_internal_membership_tier_sync(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("INTERNAL_TOKEN", "audit-internal-secret")
    tok = _signup("tier-sync@example.com")["token"]
    acct_id = client.get("/auth/me", headers=_auth(tok)).json()["id"]
    r = client.post(
        "/internal/membership/tier",
        headers={"X-Internal-Token": "audit-internal-secret"},
        json={"account_id": acct_id, "tier": "premium"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tier"] == "premium"
    assert body["membership_class"] == "vip"
    me = client.get("/auth/me", headers=_auth(tok)).json()
    assert me["tier"] == "premium"


def test_internal_membership_tier_requires_token(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)
    tok = _signup("tier-deny@example.com")["token"]
    acct_id = client.get("/auth/me", headers=_auth(tok)).json()["id"]
    r = client.post(
        "/internal/membership/tier",
        json={"account_id": acct_id, "tier": "premium"},
    )
    assert r.status_code == 403, r.text


def test_passed_without_token_denied_in_cloud(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.delenv("ALLOW_UNVERIFIED_PASS", raising=False)
    tok = _signup("pass-cloud@example.com")["token"]
    h = _auth(tok)
    client.post("/enrollments", headers=h, json={"course_id": "c-audit", "title": "Audit"})
    r = client.post("/enrollments/c-audit/status", headers=h, json={"status": "passed"})
    assert r.status_code == 403, r.text
    assert "pass_decision_token" in r.json()["detail"]


def test_passed_without_token_ok_in_local(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "local")
    tok = _signup("pass-local@example.com")["token"]
    h = _auth(tok)
    client.post("/enrollments", headers=h, json={"course_id": "c-local", "title": "Local"})
    r = client.post("/enrollments/c-local/status", headers=h, json={"status": "passed"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "passed"
