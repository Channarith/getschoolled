"""Regression tests for the 2026-08-16 comprehensive audit findings."""

from __future__ import annotations

from aoep_shared.password_reset import issue_reset_token
from fastapi.testclient import TestClient

from identity.main import _token_key, app

client = TestClient(app)


def _signup(email: str, password: str = "S3cretpass"):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": password, "display_name": "Audit"},
    ).json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_password_reset_token_cannot_access_account():
    tok = _signup("audit17-reset-scope@example.com")["token"]
    acct = client.get("/auth/me", headers=_auth(tok)).json()
    reset = issue_reset_token(acct["id"], acct["email"], _token_key())
    assert client.get("/auth/me", headers=_auth(reset)).status_code == 401


def test_profile_share_token_cannot_access_account():
    h = _auth(_signup("share-scope@example.com")["token"])
    student = client.post("/students", headers=h, json={"display_name": "Kid"}).json()
    grant = client.post(
        f"/students/{student['id']}/profile-share-grants",
        headers=h,
        json={"integration": "tutor", "scopes": ["profile"], "ttl_s": 600},
    ).json()
    assert client.get("/auth/me", headers=_auth(grant["token"])).status_code == 401
    assert client.get("/rewards", headers=_auth(grant["token"])).status_code == 401


def test_language_practice_rejects_inflated_correct_count():
    h = _auth(_signup("practice-cap@example.com")["token"])
    r = client.post(
        "/language/practice",
        headers=h,
        json={"language": "en", "skill": "pronunciation", "correct": 1_000_000, "total": 0},
    )
    # An inflated count is clamped rather than rejected, so an empty set pays
    # nothing instead of minting XP for a million claimed answers.
    assert r.status_code == 200, r.text
    assert r.json()["xp"] == 0
    assert r.json()["balance"] == 0


def test_language_practice_caps_points_to_total():
    h = _auth(_signup("practice-ok@example.com")["token"])
    r = client.post(
        "/language/practice",
        headers=h,
        json={"language": "en", "skill": "vocabulary", "correct": 5, "total": 5},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["xp"] == 56  # 5*8 + 16 bonus
    assert body["balance"] == 56


def test_onboarding_phone_does_not_validate_billing(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "production")
    tok = _signup("phone-only@example.com")["token"]
    h = _auth(tok)
    client.post("/onboarding/profile", headers=h, json={"phone": "555-1234"})
    status = client.get("/auth/onboarding-status", headers=h).json()
    assert status["billing_validated"] is False


def test_2fa_setup_blocked_when_already_enabled():
    h = _auth(_signup("2fa-setup@example.com")["token"])
    secret = client.post("/auth/2fa/setup", headers=h).json()["secret"]
    from aoep_shared.totp import current_totp

    code = current_totp(secret)
    client.post("/auth/2fa/confirm", headers=h, json={"code": code})
    blocked = client.post("/auth/2fa/setup", headers=h)
    assert blocked.status_code == 409, blocked.text


def test_mfa_lockout_survives_fresh_mfa_token(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "local")
    email = "audit17-mfa-lock@example.com"
    password = "S3cretpass"
    h = _auth(_signup(email, password)["token"])
    secret = client.post("/auth/2fa/setup", headers=h).json()["secret"]
    from aoep_shared.totp import current_totp

    client.post("/auth/2fa/confirm", headers=h, json={"code": current_totp(secret)})
    for _ in range(5):
        login = client.post("/auth/login", json={"email": email, "password": password}).json()
        mfa = login["mfa_token"]
        client.post("/auth/2fa/verify", json={"mfa_token": mfa, "code": "000000"})
    login = client.post("/auth/login", json={"email": email, "password": password}).json()
    mfa = login["mfa_token"]
    locked = client.post("/auth/2fa/verify", json={"mfa_token": mfa, "code": current_totp(secret)})
    # Account-scoped lockout: a fresh mfa_token does not reset the counter, and the
    # ceiling reports itself as 429 rather than a generic bad-code 401.
    assert locked.status_code == 429
    assert "too many" in locked.json()["detail"].lower()
