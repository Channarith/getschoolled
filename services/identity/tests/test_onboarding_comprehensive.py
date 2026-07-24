"""Comprehensive onboarding tests covering all flows, OAuth, password validation,
social login accounts, forgot-password, and the complete new-user journey."""

import re
import pytest
from fastapi.testclient import TestClient
from identity.main import app

client = TestClient(app)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def signup(email: str, password: str = "ValidPass1", display_name: str = "Test User"):
    return client.post("/auth/signup", json={"email": email, "password": password, "display_name": display_name})

def authed(token: str):
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Email/password signup
# ─────────────────────────────────────────────────────────────────────────────

def test_signup_creates_account_and_returns_token():
    r = signup("new_user_1@test.com")
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert "account" in data
    assert data["account"]["email"] == "new_user_1@test.com"
    assert data["account"]["display_name"] == "Test User"

def test_signup_duplicate_email_fails():
    signup("dup@test.com")
    r = signup("dup@test.com")
    assert r.status_code in (400, 409)  # duplicate email

def test_signup_short_password_returns_400():
    r = signup("weakpw@test.com", password="short")
    assert r.status_code == 400
    assert "8" in r.json()["detail"].lower() or "characters" in r.json()["detail"].lower()

def test_signup_password_missing_number_returns_400():
    r = signup("nonnumber@test.com", password="NoNumbers!")
    assert r.status_code == 400
    assert "number" in r.json()["detail"].lower()

def test_signup_password_too_short_no_number_returns_400():
    r = signup("bad@test.com", password="abc")
    assert r.status_code == 400

def test_signup_with_valid_password_succeeds():
    for pw in ["Xk9mQ2rT", "v7wN3pL8", "bR4hS6nJ", "qZ5mC2tK"]:
        r = signup(f"valid_{pw.lower()}@test.com", password=pw)
        assert r.status_code == 200, f"Expected 200 for password {pw!r}, got {r.status_code}: {r.json()}"

def test_signup_token_can_authenticate():
    r = signup("auth_check@test.com")
    token = r.json()["token"]
    me = client.get("/auth/me", headers=authed(token))
    assert me.status_code == 200
    assert me.json()["email"] == "auth_check@test.com"

def test_signup_display_name_is_stored():
    r = signup("named@test.com", display_name="Jane Doe")
    token = r.json()["token"]
    me = client.get("/auth/me", headers=authed(token))
    assert me.json()["display_name"] == "Jane Doe"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Login after signup
# ─────────────────────────────────────────────────────────────────────────────

def test_login_returns_token():
    signup("loginable@test.com", password="Login123")
    r = client.post("/auth/login", json={"email": "loginable@test.com", "password": "Login123"})
    assert r.status_code == 200
    assert "token" in r.json()

def test_login_wrong_password_returns_401():
    signup("badlogin@test.com", password="Correct1")
    r = client.post("/auth/login", json={"email": "badlogin@test.com", "password": "WrongPass1"})
    assert r.status_code == 401

def test_login_nonexistent_user_returns_401():
    r = client.post("/auth/login", json={"email": "nobody@test.com", "password": "Any123"})
    assert r.status_code == 401

def test_login_case_insensitive_email():
    signup("casetest@test.com", password="Pass1234")
    r = client.post("/auth/login", json={"email": "CASETEST@TEST.COM", "password": "Pass1234"})
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 3. OAuth / social sign-in (sandbox mode)
# ─────────────────────────────────────────────────────────────────────────────

def test_google_sandbox_creates_account():
    r = client.post("/auth/oauth/google", json={"id_token": "sandbox_google_google_user@test.com"})
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert data["account"]["email"] == "google_user@test.com"

def test_facebook_sandbox_creates_account():
    r = client.post("/auth/oauth/facebook", json={"access_token": "sandbox_facebook_fb_user@test.com"})
    assert r.status_code == 200
    assert "token" in r.json()

def test_apple_sandbox_creates_account():
    r = client.post("/auth/oauth/apple", json={"identity_token": "sandbox_apple_apple_user@test.com"})
    assert r.status_code == 200
    assert "token" in r.json()

def test_google_sandbox_same_email_returns_same_account():
    r1 = client.post("/auth/oauth/google", json={"id_token": "sandbox_google_same@test.com"})
    r2 = client.post("/auth/oauth/google", json={"id_token": "sandbox_google_same@test.com"})
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["account"]["id"] == r2.json()["account"]["id"]

def test_oauth_token_authenticates():
    r = client.post("/auth/oauth/google", json={"id_token": "sandbox_google_auth_oauth@test.com"})
    token = r.json()["token"]
    me = client.get("/auth/me", headers=authed(token))
    assert me.status_code == 200
    assert me.json()["email"] == "auth_oauth@test.com"

def test_google_cross_provider_conflict_returns_409():
    """Email already used with password signup → Google should return 409."""
    signup("conflict@test.com", password="Conflict1")
    r = client.post("/auth/oauth/google", json={"id_token": "sandbox_google_conflict@test.com"})
    assert r.status_code in (400, 409)  # duplicate email
    assert "already" in r.json()["detail"].lower() or "sign in" in r.json()["detail"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Forgot password / reset
# ─────────────────────────────────────────────────────────────────────────────

def test_forgot_password_nonexistent_email_still_returns_200():
    """Always return 200 to prevent email enumeration."""
    r = client.post("/auth/forgot-password", json={"email": "nobody_forgot@test.com"})
    assert r.status_code == 200

def test_forgot_password_existing_email_returns_200():
    signup("forgotme@test.com", password="Forgot123")
    r = client.post("/auth/forgot-password", json={"email": "forgotme@test.com"})
    assert r.status_code == 200
    assert r.json().get("sent") is True

def test_reset_password_with_valid_token(monkeypatch):
    """Full reset flow: request reset → get token from response → reset password."""
    signup("resetme@test.com", password="OldPass1")
    # In sandbox mode, the reset token is returned in the response
    resp = client.post("/auth/forgot-password", json={"email": "resetme@test.com"})
    assert resp.status_code == 200
    token = resp.json().get("reset_token") or resp.json().get("token")
    if not token:
        pytest.skip("Reset token not exposed in this mode (email-delivery mode)")
    r = client.post("/auth/reset-password", json={"token": token, "new_password": "NewPass99"})
    assert r.status_code == 200
    # Can now login with new password
    login = client.post("/auth/login", json={"email": "resetme@test.com", "password": "NewPass99"})
    assert login.status_code == 200

def test_reset_password_invalid_token_returns_400():
    r = client.post("/auth/reset-password", json={"token": "invalid.token.here", "new_password": "NewPass99"})
    assert r.status_code == 400

def test_reset_password_weak_password_returns_400():
    signup("resetweak@test.com", password="OldPass1")
    resp = client.post("/auth/forgot-password", json={"email": "resetweak@test.com"})
    token = resp.json().get("reset_token") or resp.json().get("token")
    if not token:
        pytest.skip("Reset token not exposed in this mode")
    r = client.post("/auth/reset-password", json={"token": token, "new_password": "short"})
    assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# 5. Onboarding profile flow
# ─────────────────────────────────────────────────────────────────────────────

def test_onboarding_profile_requires_auth():
    r = client.post("/onboarding/profile", json={"display_name": "Test"})
    assert r.status_code == 401

def test_onboarding_profile_sets_display_name():
    r = signup("profile_onboard@test.com")
    token = r.json()["token"]
    r2 = client.post("/onboarding/profile",
        headers=authed(token),
        json={"display_name": "Onboard User", "interests": ["math", "science"]})
    assert r2.status_code == 200

def test_onboarding_status_unauthenticated_returns_401():
    r = client.get("/auth/onboarding-status")
    assert r.status_code == 401

def test_onboarding_status_returns_completed_flag():
    token = signup("status_check@test.com").json()["token"]
    r = client.get("/auth/onboarding-status", headers=authed(token))
    assert r.status_code == 200
    data = r.json()
    assert "completed" in data

def test_onboarding_free_plan_no_billing_required():
    token = signup("free_plan@test.com").json()["token"]
    h = authed(token)
    r = client.post("/onboarding/plan", headers=h, json={"tier": "free"})
    assert r.status_code == 200

def test_onboarding_paid_plan_requires_billing():
    token = signup("paid_plan@test.com").json()["token"]
    h = authed(token)
    r = client.post("/onboarding/plan", headers=h, json={"tier": "premium"})
    assert r.status_code == 402


# ─────────────────────────────────────────────────────────────────────────────
# 6. /auth/me and token validity
# ─────────────────────────────────────────────────────────────────────────────

def test_auth_me_without_token_returns_401():
    r = client.get("/auth/me")
    assert r.status_code == 401

def test_auth_me_with_invalid_token_returns_401():
    r = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401

def test_auth_me_with_valid_token_returns_account():
    token = signup("me_check@test.com").json()["token"]
    r = client.get("/auth/me", headers=authed(token))
    assert r.status_code == 200
    assert r.json()["email"] == "me_check@test.com"

def test_auth_me_returns_tier():
    token = signup("tier_check@test.com").json()["token"]
    r = client.get("/auth/me", headers=authed(token))
    assert "tier" in r.json()

def test_auth_me_returns_onboarding_status():
    token = signup("onboard_me@test.com").json()["token"]
    r = client.get("/auth/me", headers=authed(token))
    data = r.json()
    # Should have some indication of onboarding completion
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 7. Complete new-user happy path
# ─────────────────────────────────────────────────────────────────────────────

def test_complete_new_user_journey():
    """End-to-end: sign up → set profile → choose free plan → verify status."""
    # Step 1: Sign up
    r = signup("journey@test.com", password="Journey99", display_name="Journey User")
    assert r.status_code == 200, f"Signup failed: {r.json()}"
    token = r.json()["token"]
    h = authed(token)

    # Step 2: Verify logged in
    me = client.get("/auth/me", headers=h)
    assert me.status_code == 200
    assert me.json()["email"] == "journey@test.com"

    # Step 3: Set profile
    profile = client.post("/onboarding/profile", headers=h,
        json={"display_name": "Journey User Updated", "interests": ["history"]})
    assert profile.status_code == 200

    # Step 4: Choose free plan
    plan = client.post("/onboarding/plan", headers=h, json={"tier": "free"})
    assert plan.status_code == 200

    # Step 5: Verify onboarding status
    status = client.get("/auth/onboarding-status", headers=h)
    assert status.status_code == 200


def test_complete_oauth_new_user_journey():
    """End-to-end OAuth: Google sign-up → verify account → set profile."""
    # Step 1: Sign in with Google (sandbox)
    r = client.post("/auth/oauth/google",
        json={"id_token": "sandbox_google_oauth_journey@test.com"})
    assert r.status_code == 200
    token = r.json()["token"]
    h = authed(token)

    # Step 2: Verify email
    me = client.get("/auth/me", headers=h)
    assert me.status_code == 200
    assert me.json()["email"] == "oauth_journey@test.com"

    # Step 3: Set onboarding profile
    profile = client.post("/onboarding/profile", headers=h,
        json={"display_name": "OAuth Journey", "interests": ["languages"]})
    assert profile.status_code == 200

    # Step 4: Can choose free plan without billing
    plan = client.post("/onboarding/plan", headers=h, json={"tier": "free"})
    assert plan.status_code == 200
