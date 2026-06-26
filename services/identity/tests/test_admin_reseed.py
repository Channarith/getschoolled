"""Admin reseed endpoint persists QA personas for all identity replicas."""

from __future__ import annotations

from fastapi.testclient import TestClient
from identity.main import app
from identity.store import AccountStore

client = TestClient(app)


def test_admin_reseed_seeded_endpoint(monkeypatch):
    monkeypatch.setenv("SEED_DEFAULT_ADMIN", "1")
    monkeypatch.setenv("SEED_QA_ACCOUNTS", "1")
    app.state.accounts = AccountStore()
    app.state.accounts.seed_admin("admin@salareen.com", "88888888", username="admin")
    login = client.post("/auth/login", json={"email": "admin@salareen.com", "password": "88888888"})
    assert login.status_code == 200
    tok = login.json()["token"]
    r = client.post("/admin/accounts/reseed-seeded", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["reseeded"] is True
    assert body["stats"]["qa_count"] == 3
    assert app.state.accounts.authenticate("qa-pro@salareen.com", "QaTest123") is not None
