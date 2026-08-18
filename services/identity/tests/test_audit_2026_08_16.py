"""Regression tests for docs/audit-2026-08-16.txt identity/billing findings."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aoep_shared.auth import sign_token
from aoep_shared.language_learning import practice_xp
from identity.main import app

client = TestClient(app)


def _signup(email: str, password: str = "S3cretpass"):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": password, "display_name": "Audit"},
    ).json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_practice_xp_clamps_and_caps():
    # CRIT-26: correct cannot exceed total; XP hard-capped.
    assert practice_xp("vocabulary", 1_000_000, 0) == 0
    assert practice_xp("vocabulary", 1_000_000, 5) == practice_xp("vocabulary", 5, 5)
    assert practice_xp("pronunciation", 50, 50) <= 200


def test_language_practice_cannot_mint_gift_card_points():
    tok = _signup("xp-abuse@example.com")["token"]
    h = _auth(tok)
    r = client.post(
        "/language/practice",
        headers=h,
        json={"language": "en", "skill": "pronunciation", "correct": 1_000_000, "total": 0},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["xp"] == 0
    assert body["balance"] == 0
    r2 = client.post(
        "/language/practice",
        headers=h,
        json={"language": "en", "skill": "pronunciation", "correct": 50, "total": 50},
    )
    assert r2.status_code == 200
    assert r2.json()["xp"] <= 200
    assert r2.json()["balance"] <= 200


def test_password_reset_token_rejected_as_session():
    _signup("reset-sess@example.com")
    forgot = client.post("/auth/forgot-password", json={"email": "reset-sess@example.com"}).json()
    reset_tok = forgot["reset_token"]
    me = client.get("/auth/me", headers=_auth(reset_tok))
    assert me.status_code == 401
    enroll = client.post(
        "/enrollments",
        headers=_auth(reset_tok),
        json={"course_id": "c1", "title": "X", "status": "saved"},
    )
    assert enroll.status_code == 401


def test_profile_share_token_rejected_as_session():
    tok = _signup("share-sess@example.com")["token"]
    h = _auth(tok)
    student = client.post("/students", headers=h, json={"display_name": "Kid"}).json()
    grant = client.post(
        f"/students/{student['id']}/profile-share-grants",
        headers=h,
        json={"integration": "robot", "scopes": ["mastery"], "ttl_s": 600},
    ).json()
    share = grant["token"]
    assert client.get("/auth/me", headers=_auth(share)).status_code == 401
    assert client.get("/rewards", headers=_auth(share)).status_code == 401
    # Scoped endpoint still works.
    ctx = client.get("/profile-shares/context", headers=_auth(share))
    assert ctx.status_code == 200


def test_2fa_setup_refuses_when_already_enabled():
    tok = _signup("mfa-setup@example.com")["token"]
    h = _auth(tok)
    setup = client.post("/auth/2fa/setup", headers=h).json()
    from aoep_shared.totp import current_totp

    code = current_totp(setup["secret"])
    assert client.post("/auth/2fa/confirm", headers=h, json={"code": code}).status_code == 200
    again = client.post("/auth/2fa/setup", headers=h)
    assert again.status_code == 400
    # Login still requires 2FA.
    step1 = client.post(
        "/auth/login", json={"email": "mfa-setup@example.com", "password": "S3cretpass"}
    ).json()
    assert step1.get("requires_2fa") is True


def test_2fa_lockout_survives_relogin():
    tok = _signup("mfa-lock@example.com")["token"]
    h = _auth(tok)
    setup = client.post("/auth/2fa/setup", headers=h).json()
    from aoep_shared.totp import current_totp

    code = current_totp(setup["secret"])
    client.post("/auth/2fa/confirm", headers=h, json={"code": code})
    for i in range(5):
        step1 = client.post(
            "/auth/login", json={"email": "mfa-lock@example.com", "password": "S3cretpass"}
        ).json()
        bad = client.post(
            "/auth/2fa/verify",
            json={"mfa_token": step1["mfa_token"], "code": "000000"},
        )
        assert bad.status_code == 401
    # Fresh login must still be locked (counter is per account, not mfa_token).
    locked = client.post(
        "/auth/login", json={"email": "mfa-lock@example.com", "password": "S3cretpass"}
    )
    assert locked.status_code == 401


def test_phone_alone_does_not_validate_billing():
    tok = _signup("phone-bill@example.com")["token"]
    h = _auth(tok)
    r = client.post(
        "/onboarding/profile",
        headers=h,
        json={"display_name": "P", "phone": "555-1234"},
    )
    assert r.status_code == 200
    status = client.get("/auth/onboarding-status", headers=h).json()
    assert status["billing_validated"] is False


def test_enrollment_status_uses_token_score_not_body():
    from identity.main import _assessment_signing_key

    tok = _signup("enroll-score@example.com")["token"]
    h = _auth(tok)
    student_id = client.get("/students", headers=h).json()["students"][0]["id"]
    client.post(
        "/enrollments",
        headers=h,
        json={"course_id": "c-score", "title": "Score", "status": "enrolled"},
    )
    decision = sign_token(
        {
            "kind": "assessment_pass",
            "student_id": student_id,
            "course_id": "c-score",
            "score": 0.51,
            "level": "beginner",
            "hands_on": False,
            "attempt_ids": [],
            "ksb_codes": [],
        },
        _assessment_signing_key(),
        ttl_s=600,
    )
    before = client.get("/rewards", headers=h).json()["balance"]
    r = client.post(
        "/enrollments/c-score/status",
        headers=h,
        json={
            "status": "passed",
            "score": 1.0,
            "level": "advanced",
            "hands_on": True,
            "pass_decision_token": decision,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score"] == 0.51
    assert body["level"] == "beginner"
    assert body["hands_on"] is False
    after = body["points_balance"]
    # beginner + 0.51 score ≈ 125; advanced+hands_on would be ~500
    assert after - before < 250
