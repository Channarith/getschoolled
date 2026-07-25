"""Regression tests for signup + onboarding flow (v0.45.5 / v0.45.9 fixes).

Covers:
- Auto-profile submit during home-page signup (onboarding step skip)
- Onboarding status is server-side and survives session (not localStorage-only)
- Login/signup returns valid token
- Multiple signup attempts with same email are rejected
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:8]}@example.com"


def _signup(email: str | None = None, display_name: str = "Test User") -> tuple[str, str]:
    """Signup and return (token, account_id)."""
    email = email or _unique_email()
    r = client.post("/auth/signup", json={
        "email": email,
        "password": "Secret123!",
        "display_name": display_name,
    })
    assert r.status_code == 200, f"signup failed: {r.text}"
    body = r.json()
    return body["token"], body.get("account_id", "")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Signup basics
# ---------------------------------------------------------------------------

def test_signup_returns_token():
    tok, _ = _signup()
    assert tok and len(tok) > 10


def test_signup_duplicate_email_rejected():
    email = _unique_email()
    _signup(email)
    r = client.post("/auth/signup", json={
        "email": email, "password": "Secret123!", "display_name": "Dupe"
    })
    assert r.status_code in (400, 409), (
        "duplicate signup must be rejected — "
        "accounts with the same email must not be created twice"
    )


def test_login_returns_token():
    email = _unique_email()
    pw = "LoginPass99!"
    client.post("/auth/signup", json={"email": email, "password": pw, "display_name": "Logg"})
    r = client.post("/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    assert r.json()["token"]


def test_wrong_password_rejected():
    email = _unique_email()
    client.post("/auth/signup", json={"email": email, "password": "Right1!", "display_name": "Sec"})
    r = client.post("/auth/login", json={"email": email, "password": "Wrong99!"})
    assert r.status_code in (400, 401)


def test_auth_me_returns_account():
    tok, _ = _signup()
    r = client.get("/auth/me", headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["email"]
    assert "display_name" in body


# ---------------------------------------------------------------------------
# v0.45.9 — Auto-profile submit during home-page signup
# ---------------------------------------------------------------------------

def test_profile_submit_during_signup_does_not_fail():
    """Regression v0.45.9: home page now calls submitOnboardingProfile() after
    signup to auto-advance past the 'Your info' step.  This must not fail for
    a brand-new account (display_name already set from signup)."""
    tok, _ = _signup(display_name="New Learner")
    r = client.post(
        "/onboarding/profile",
        headers=_auth(tok),
        json={"display_name": "New Learner"},
    )
    assert r.status_code == 200, (
        f"onboarding/profile must succeed immediately after signup: {r.text}"
    )


def test_onboarding_status_starts_incomplete():
    """Regression v0.45.9: fresh account must have completed=False."""
    tok, _ = _signup()
    r = client.get("/auth/onboarding-status", headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["completed"] is False, (
        "fresh account onboarding must start as incomplete"
    )


def test_onboarding_status_server_side_not_localstorage_only():
    """Regression v0.45.5: onboarding completion must be persisted server-side
    so it survives browser/device changes.  We verify this by completing
    onboarding via the API (not localStorage) and checking the status endpoint."""
    tok, _ = _signup()
    h = _auth(tok)

    # Submit billing (required before paid plan).
    client.post("/onboarding/billing", headers=h, json={
        "line1": "1 Main St", "city": "Austin", "state": "TX",
        "postal_code": "78701", "country": "US",
        "card_number": "4242424242424242", "exp_month": 12,
        "exp_year": 2030, "cvv": "123",
    })
    client.post("/onboarding/plan", headers=h, json={"tier": "basic"})
    client.post("/onboarding/complete", headers=h, json={"learner_name": "Alex"})

    # Verify server-side status (simulates "different browser / cleared localStorage").
    status = client.get("/auth/onboarding-status", headers=h).json()
    assert status["completed"] is True, (
        "onboarding completion must be stored server-side — "
        "a user on a new device or in incognito must not redo onboarding"
    )


# ---------------------------------------------------------------------------
# v0.45.5 — Cross-pod account sync (Redis)
# ---------------------------------------------------------------------------

def test_token_from_signup_works_on_auth_me():
    """Regression v0.45.2/v0.45.5: token issued during signup must be accepted
    on /auth/me (simulates same-pod scenario — cross-pod needs Redis)."""
    tok, _ = _signup()
    r = client.get("/auth/me", headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["email"]


def test_login_history_recorded_after_signup():
    """After signup, at least one login event should be in the history."""
    tok, _ = _signup()
    r = client.get("/auth/login-history", headers=_auth(tok))
    assert r.status_code == 200
    events = r.json().get("events", [])
    assert len(events) >= 1
    assert events[0]["success"] is True


# ---------------------------------------------------------------------------
# Onboarding free plan (no billing required)
# ---------------------------------------------------------------------------

def test_free_plan_onboarding_no_billing():
    """Free-tier onboarding must not require billing details."""
    tok, _ = _signup()
    h = _auth(tok)
    r = client.post("/onboarding/plan", headers=h, json={"tier": "free"})
    assert r.status_code in (200, 204), (
        f"free plan selection must not require billing: {r.text}"
    )


def test_onboarding_profile_idempotent():
    """Calling /onboarding/profile twice must not fail (idempotent)."""
    tok, _ = _signup()
    h = _auth(tok)
    client.post("/onboarding/profile", headers=h, json={"display_name": "Alice"})
    r2 = client.post("/onboarding/profile", headers=h, json={"display_name": "Alice Updated"})
    assert r2.status_code == 200, f"second profile submit must be accepted: {r2.text}"
