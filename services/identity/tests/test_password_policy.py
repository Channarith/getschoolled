"""Signup + password change enforce the shared password policy."""

from __future__ import annotations

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_signup_rejects_weak_passwords():
    # too short
    r = client.post("/auth/signup", json={"email": "weak1@example.com", "password": "ab1"})
    assert r.status_code == 400 and "8 characters" in r.json()["detail"]
    # letters only (no number)
    r = client.post("/auth/signup", json={"email": "weak2@example.com", "password": "abcdefgh"})
    assert r.status_code == 400 and "number" in r.json()["detail"]
    # digits only (no letter) - e.g. "88888888"
    r = client.post("/auth/signup", json={"email": "weak3@example.com", "password": "88888888"})
    assert r.status_code == 400 and "letter" in r.json()["detail"]


def test_signup_accepts_strong_password():
    r = client.post("/auth/signup", json={"email": "strong@example.com", "password": "S3cretpass"})
    assert r.status_code == 200 and r.json().get("token")


def test_password_change_enforces_policy():
    tok = client.post("/auth/signup",
                      json={"email": "pcpol@example.com", "password": "S3cretpass"}).json()["token"]
    weak = client.post("/auth/password", headers=_auth(tok),
                       json={"current_password": "S3cretpass", "new_password": "weakpass"})
    assert weak.status_code == 400 and "number" in weak.json()["detail"]
    ok = client.post("/auth/password", headers=_auth(tok),
                     json={"current_password": "S3cretpass", "new_password": "newpass12"})
    assert ok.status_code == 200
