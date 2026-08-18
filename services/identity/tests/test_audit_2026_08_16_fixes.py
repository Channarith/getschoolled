"""Identity regressions for audit-2026-08-16 CRITICAL/HIGH security fixes."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ.setdefault("INTERNAL_AUTH_DISABLED", "1")
os.environ.setdefault("DEPLOY_MODE", "local")


def test_language_practice_cannot_mint_gift_card_points(tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_IDENTITY_DATA", str(tmp_path / "id.json"))
    from identity.main import app

    client = TestClient(app)
    tok = client.post(
        "/auth/signup",
        json={"email": "xp-abuse@example.com", "password": "S3cretpass", "display_name": "X"},
    ).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post(
        "/language/practice",
        headers=h,
        json={"language": "en", "skill": "pronunciation", "correct": 1_000_000, "total": 0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["xp"] == 0
    assert body["balance"] == 0


def test_password_reset_token_is_not_a_session():
    from identity.main import app

    client = TestClient(app)
    client.post(
        "/auth/signup",
        json={"email": "reset-scope@example.com", "password": "S3cretpass", "display_name": "R"},
    )
    forgot = client.post("/auth/forgot-password", json={"email": "reset-scope@example.com"}).json()
    reset_token = forgot["reset_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {reset_token}"})
    assert me.status_code == 401
    enroll = client.post(
        "/enrollments",
        headers={"Authorization": f"Bearer {reset_token}"},
        json={"course_id": "intro-python", "title": "Python"},
    )
    assert enroll.status_code == 401


def test_2fa_setup_refuses_when_already_enabled():
    from aoep_shared.totp import current_totp
    from identity.main import app

    client = TestClient(app)
    tok = client.post(
        "/auth/signup",
        json={"email": "mfa-lock@example.com", "password": "S3cretpass", "display_name": "M"},
    ).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    setup = client.post("/auth/2fa/setup", headers=h).json()
    code = current_totp(setup["secret"])
    assert client.post("/auth/2fa/confirm", headers=h, json={"code": code}).status_code == 200
    again = client.post("/auth/2fa/setup", headers=h)
    assert again.status_code == 409
    step1 = client.post(
        "/auth/login", json={"email": "mfa-lock@example.com", "password": "S3cretpass"}
    ).json()
    assert step1.get("requires_2fa") is True


def test_2fa_lockout_survives_mfa_token_rotation():
    from aoep_shared.totp import current_totp
    from identity.main import app

    client = TestClient(app)
    tok = client.post(
        "/auth/signup",
        json={"email": "mfa-brute@example.com", "password": "S3cretpass", "display_name": "B"},
    ).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    setup = client.post("/auth/2fa/setup", headers=h).json()
    code = current_totp(setup["secret"])
    client.post("/auth/2fa/confirm", headers=h, json={"code": code})

    for _ in range(5):
        step1 = client.post(
            "/auth/login", json={"email": "mfa-brute@example.com", "password": "S3cretpass"}
        ).json()
        assert step1.get("requires_2fa")
        bad = client.post(
            "/auth/2fa/verify",
            json={"mfa_token": step1["mfa_token"], "code": "000000"},
        )
        assert bad.status_code == 401

    step1 = client.post(
        "/auth/login", json={"email": "mfa-brute@example.com", "password": "S3cretpass"}
    ).json()
    locked = client.post(
        "/auth/2fa/verify",
        json={"mfa_token": step1["mfa_token"], "code": current_totp(setup["secret"])},
    )
    assert locked.status_code == 401


def test_phone_alone_does_not_validate_billing():
    from identity.main import app

    client = TestClient(app)
    tok = client.post(
        "/auth/signup",
        json={"email": "phone-bill@example.com", "password": "S3cretpass", "display_name": "P"},
    ).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post(
        "/onboarding/profile",
        headers=h,
        json={"phone": "555-1234", "display_name": "P"},
    )
    assert r.status_code == 200
    status = client.get("/auth/onboarding-status", headers=h).json()
    assert status.get("billing_validated") is False
