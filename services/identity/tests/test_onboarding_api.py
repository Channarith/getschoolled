"""Onboarding, billing validation, and login audit."""

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _signup(email="onboard@example.com"):
    return client.post("/auth/signup", json={
        "email": email, "password": "Secret123", "display_name": "New User",
    }).json()["token"]


def test_onboarding_billing_validates_card():
    tok = _signup("bill@example.com")
    r = client.post("/onboarding/billing", headers={"Authorization": f"Bearer {tok}"}, json={
        "line1": "1 Main St", "city": "Austin", "state": "TX", "postal_code": "78701",
        "country": "US", "card_number": "4242424242424242", "exp_month": 12,
        "exp_year": 2030, "cvv": "123",
    })
    assert r.status_code == 200
    assert r.json()["card_last4"] == "4242"


def test_paid_plan_requires_billing():
    tok = _signup("plan@example.com")
    r = client.post("/onboarding/plan", headers={"Authorization": f"Bearer {tok}"}, json={
        "tier": "premium",
    })
    assert r.status_code == 402


def test_onboarding_flow_standard_and_vip():
    tok = _signup("vip@example.com")
    h = {"Authorization": f"Bearer {tok}"}
    client.post("/onboarding/billing", headers=h, json={
        "line1": "1 Main St", "city": "Austin", "state": "TX", "postal_code": "78701",
        "country": "US", "card_number": "4242424242424242", "exp_month": 12,
        "exp_year": 2030, "cvv": "123",
    })
    r = client.post("/onboarding/plan", headers=h, json={"tier": "premium"})
    assert r.status_code == 200
    assert r.json()["membership_class"] == "vip"
    assert r.json()["tier"] == "premium"
    client.post("/onboarding/complete", headers=h, json={"learner_name": "Alex"})
    status = client.get("/auth/onboarding-status", headers=h).json()
    assert status["completed"] is True
    assert status["membership_class"] == "vip"


def test_onboarding_standard_plan_pricing():
    tok = _signup("std-onboard@example.com")
    h = {"Authorization": f"Bearer {tok}"}
    client.post("/onboarding/billing", headers=h, json={
        "line1": "1 Main St", "city": "Austin", "state": "TX", "postal_code": "78701",
        "country": "US", "card_number": "4242424242424242", "exp_month": 12,
        "exp_year": 2030, "cvv": "123",
    })
    r = client.post("/onboarding/plan", headers=h, json={"tier": "basic"})
    assert r.status_code == 200
    assert r.json()["membership_class"] == "standard"
    me = client.get("/auth/me", headers=h).json()
    assert me["subscription"]["price_usd"] == 19.99


def test_login_history_recorded():
    tok = _signup("hist@example.com")
    h = {"Authorization": f"Bearer {tok}"}
    events = client.get("/auth/login-history", headers=h).json()["events"]
    assert len(events) >= 1
    assert events[0]["success"] is True
