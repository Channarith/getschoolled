"""Preferred language persists on the account and rides along with /auth/me."""

from __future__ import annotations

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _signup(email: str) -> str:
    return client.post(
        "/auth/signup", json={"email": email, "password": "S3cretpass"}
    ).json()["token"]


def test_set_and_read_preferred_language():
    tok = _signup("lang1@example.com")
    # Defaults to blank (infer from device) until the learner picks one.
    assert client.get("/auth/me", headers=_auth(tok)).json()["preferred_language"] == ""

    set_es = client.post("/account/language", headers=_auth(tok), json={"language": "es"})
    assert set_es.status_code == 200, set_es.text
    assert set_es.json()["preferred_language"] == "es"
    # It rides along with the account so any device adopts it.
    assert client.get("/auth/me", headers=_auth(tok)).json()["preferred_language"] == "es"


def test_language_accepts_locale_and_normalizes():
    tok = _signup("lang2@example.com")
    r = client.post("/account/language", headers=_auth(tok), json={"language": "PT-BR"})
    assert r.status_code == 200, r.text
    assert r.json()["preferred_language"] == "pt"  # normalized to the base code


def test_language_rejects_unsupported_and_clears_on_blank():
    tok = _signup("lang3@example.com")
    bad = client.post("/account/language", headers=_auth(tok), json={"language": "zz"})
    assert bad.status_code == 400
    client.post("/account/language", headers=_auth(tok), json={"language": "fr"})
    cleared = client.post("/account/language", headers=_auth(tok), json={"language": ""})
    assert cleared.status_code == 200 and cleared.json()["preferred_language"] == ""


def test_language_requires_auth():
    assert client.post("/account/language", json={"language": "es"}).status_code == 401
