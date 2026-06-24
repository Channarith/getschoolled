"""Operator reseed via X-Admin-Secret (no session JWT)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from identity.main import app
from identity.store import AccountStore

client = TestClient(app)


def test_ops_reseed_seeded_with_admin_secret(monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "test-admin-secret")
    monkeypatch.setenv("SEED_QA_ACCOUNTS", "1")
    monkeypatch.setenv("SEED_DEFAULT_ADMIN", "1")
    app.state.accounts = AccountStore()
    r = client.post(
        "/admin/ops/reseed-seeded",
        headers={"X-Admin-Secret": "test-admin-secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reseeded"] is True
    assert body["stats"]["qa_count"] == 3
    assert body.get("login_ok", {}).get("qa-pro@salareen.com") is True
    # Running server (TestClient) must accept login after ops reseed.
    login = client.post("/auth/login", json={"email": "qa-pro@salareen.com", "password": "QaTest123"})
    assert login.status_code == 200
    assert login.json().get("token")


def test_ops_reseed_rejects_bad_secret(monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "test-admin-secret")
    r = client.post("/admin/ops/reseed-seeded", headers={"X-Admin-Secret": "nope"})
    assert r.status_code == 403
