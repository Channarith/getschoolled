"""Passkeys fail closed in cloud unless PASSKEY_SANDBOX=1."""

from __future__ import annotations

import json

import pytest

from aoep_shared.passkeys import verify_login, verify_registration, PasskeyCredential


def _client_data(challenge: str, typ: str = "webauthn.create") -> str:
    return json.dumps({"type": typ, "challenge": challenge, "origin": "https://example.com"})


def test_registration_ok_in_local(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "local")
    monkeypatch.delenv("PASSKEY_SANDBOX", raising=False)
    chal = "chal-local-1"
    cred = verify_registration(
        challenge=chal,
        client_data_json=_client_data(chal),
        credential_id="cred-1",
    )
    assert cred.credential_id == "cred-1"


def test_registration_rejected_in_cloud(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.delenv("PASSKEY_SANDBOX", raising=False)
    chal = "chal-cloud-1"
    with pytest.raises(ValueError, match="WebAuthn verifier"):
        verify_registration(
            challenge=chal,
            client_data_json=_client_data(chal),
            credential_id="cred-2",
        )


def test_registration_sandbox_override_in_cloud(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.setenv("PASSKEY_SANDBOX", "1")
    chal = "chal-sandbox-1"
    cred = verify_registration(
        challenge=chal,
        client_data_json=_client_data(chal),
        credential_id="cred-3",
    )
    assert cred.credential_id == "cred-3"


def test_login_fails_closed_in_cloud(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.delenv("PASSKEY_SANDBOX", raising=False)
    chal = "chal-login-1"
    stored = PasskeyCredential(credential_id="cred-login", public_key="x")
    ok = verify_login(
        challenge=chal,
        credential_id="cred-login",
        client_data_json=_client_data(chal, typ="webauthn.get"),
        stored=stored,
    )
    assert ok is False


def test_rejects_unbound_client_data(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "local")
    with pytest.raises(ValueError, match="challenge"):
        verify_registration(
            challenge="expected",
            client_data_json=_client_data("other"),
            credential_id="cred-x",
        )
