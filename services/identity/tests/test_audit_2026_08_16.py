"""Regression tests for the 2026-08-16 identity/billing audit findings."""

from __future__ import annotations

from aoep_shared.auth import sign_token
from aoep_shared.totp import current_totp
from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)
ASSESS_KEY = b"dev-assessment-signing-key"


def _signup(email: str, password: str = "S3cretpass"):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": password, "display_name": "Audit16"},
    ).json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_language_practice_clamps_self_reported_xp():
    """CRIT-26: unbounded correct/total must not mint gift-card-redeemable points."""
    tok = _signup("audit16-xp@example.com")["token"]
    h = _auth(tok)
    before = client.get("/rewards", headers=h).json()["balance"]
    huge = client.post(
        "/language/practice",
        headers=h,
        json={"language": "en", "skill": "pronunciation", "correct": 1_000_000, "total": 0},
    )
    assert huge.status_code == 200, huge.text
    assert huge.json()["xp"] == 0
    assert huge.json()["balance"] == before

    capped = client.post(
        "/language/practice",
        headers=h,
        json={"language": "en", "skill": "pronunciation", "correct": 1_000_000, "total": 1_000_000},
    )
    assert capped.status_code == 200, capped.text
    assert 0 < capped.json()["xp"] <= 500
    rewards = client.get("/rewards", headers=h).json()
    assert rewards["balance"] == capped.json()["balance"]
    assert rewards["balance"] <= 500
    redeem = client.post(
        "/rewards/redeem", headers=h, json={"prize_id": "gift_amazon_25"}
    )
    assert redeem.status_code in (400, 402, 409, 422)


def test_password_reset_token_is_not_a_session():
    """HIGH-27a: reset tokens must not authenticate /auth/me or mutating routes."""
    tok = _signup("audit16-reset@example.com")["token"]
    forgot = client.post(
        "/auth/forgot-password", json={"email": "audit16-reset@example.com"}
    ).json()
    reset_token = forgot["reset_token"]
    me = client.get("/auth/me", headers=_auth(reset_token))
    assert me.status_code == 401
    enroll = client.post(
        "/enrollments",
        headers=_auth(reset_token),
        json={"course_id": "c-reset", "title": "Nope"},
    )
    assert enroll.status_code == 401
    # Original session still works.
    assert client.get("/auth/me", headers=_auth(tok)).status_code == 200


def test_profile_share_token_cannot_spend_or_mint_grants():
    """HIGH-27b: share tokens are scoped; they are not full sessions."""
    tok = _signup("audit16-share@example.com")["token"]
    h = _auth(tok)
    sid = client.get("/students", headers=h).json()["students"][0]["id"]
    grant = client.post(
        f"/students/{sid}/profile-share-grants",
        headers=h,
        json={"integration": "audit", "scopes": ["mastery"], "ttl_s": 600},
    ).json()
    share = _auth(grant["token"])
    assert client.get("/auth/me", headers=share).status_code == 401
    assert client.get("/rewards", headers=share).status_code == 401
    steal = client.post(
        f"/students/{sid}/profile-share-grants",
        headers=share,
        json={"integration": "audit", "scopes": ["mastery"], "ttl_s": 86400},
    )
    assert steal.status_code == 401
    ctx = client.get("/profile-shares/context", headers=share)
    assert ctx.status_code == 200, ctx.text


def test_assessment_pass_token_is_not_a_session():
    tok = _signup("audit16-passtok@example.com")["token"]
    h = _auth(tok)
    sid = client.get("/students", headers=h).json()["students"][0]["id"]
    pass_tok = sign_token(
        {"kind": "assessment_pass", "student_id": sid, "course_id": "c1", "score": 1.0},
        ASSESS_KEY,
    )
    assert client.get("/auth/me", headers=_auth(pass_tok)).status_code == 401


def test_2fa_setup_refuses_when_already_enabled():
    """HIGH-28: setup must not silently disable active 2FA."""
    tok = _signup("audit16-2fa@example.com")["token"]
    h = _auth(tok)
    setup = client.post("/auth/2fa/setup", headers=h)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    confirm = client.post(
        "/auth/2fa/confirm", headers=h, json={"code": current_totp(secret)}
    )
    assert confirm.status_code == 200, confirm.text
    again = client.post("/auth/2fa/setup", headers=h)
    assert again.status_code == 409
    login = client.post(
        "/auth/login",
        json={"email": "audit16-2fa@example.com", "password": "S3cretpass"},
    )
    assert login.status_code == 200
    assert login.json().get("requires_2fa") is True


def test_mfa_lockout_is_account_scoped():
    """HIGH-29: re-login must not reset the 2FA brute-force counter."""
    tok = _signup("audit16-mfalock@example.com")["token"]
    h = _auth(tok)
    setup = client.post("/auth/2fa/setup", headers=h).json()
    client.post(
        "/auth/2fa/confirm", headers=h, json={"code": current_totp(setup["secret"])}
    )
    for _ in range(5):
        step1 = client.post(
            "/auth/login",
            json={"email": "audit16-mfalock@example.com", "password": "S3cretpass"},
        ).json()
        bad = client.post(
            "/auth/2fa/verify",
            json={"mfa_token": step1["mfa_token"], "code": "000000"},
        )
        assert bad.status_code == 401
    # The counter is account-scoped, so rotating in a fresh mfa_token buys nothing:
    # the sixth attempt is locked out even when the code is CORRECT.
    step1 = client.post(
        "/auth/login",
        json={"email": "audit16-mfalock@example.com", "password": "S3cretpass"},
    ).json()
    locked = client.post(
        "/auth/2fa/verify",
        json={"mfa_token": step1["mfa_token"], "code": current_totp(setup["secret"])},
    )
    assert locked.status_code == 429


def test_phone_only_onboarding_does_not_validate_billing():
    """MED-30: a phone number is not a payment method."""
    tok = _signup("audit16-phone@example.com")["token"]
    h = _auth(tok)
    r = client.post(
        "/onboarding/profile",
        headers=h,
        json={"display_name": "Pat", "phone": "555-1234"},
    )
    assert r.status_code == 200, r.text
    status = client.get("/auth/onboarding-status", headers=h).json()
    assert status["billing_validated"] is False


def test_enrollment_pass_uses_token_score_not_body():
    """MED-31: signed pass token score wins over the client body."""
    tok = _signup("audit16-score@example.com")["token"]
    h = _auth(tok)
    sid = client.get("/students", headers=h).json()["students"][0]["id"]
    client.post(
        "/enrollments",
        headers=h,
        json={"course_id": "c-score", "title": "Score Course"},
    )
    pass_tok = sign_token(
        {
            "kind": "assessment_pass",
            "student_id": sid,
            "course_id": "c-score",
            "score": 0.51,
        },
        ASSESS_KEY,
    )
    r = client.post(
        "/enrollments/c-score/status",
        headers=h,
        json={
            "status": "passed",
            "score": 1.0,
            "level": "advanced",
            "hands_on": True,
            "pass_decision_token": pass_tok,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["score"] == 0.51


def test_saved_enrollment_status_is_accepted():
    tok = _signup("audit16-saved@example.com")["token"]
    r = client.post(
        "/enrollments",
        headers=_auth(tok),
        json={"course_id": "audio-saved", "title": "Saved", "status": "saved"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "saved"
