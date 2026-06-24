"""Operator reseed via X-Admin-Secret (no session JWT)."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient
from identity.main import app
from identity.store import AccountStore

client = TestClient(app)


def test_ops_reseed_seeded_with_admin_secret():
    os.environ["ADMIN_SECRET"] = "test-admin-secret"
    os.environ["SEED_QA_ACCOUNTS"] = "1"
    os.environ["SEED_DEFAULT_ADMIN"] = "1"
    app.state.accounts = AccountStore()
    r = client.post(
        "/admin/ops/reseed-seeded",
        headers={"X-Admin-Secret": "test-admin-secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reseeded"] is True
    assert body["stats"]["qa_count"] == 3


def test_ops_reseed_rejects_bad_secret():
    os.environ["ADMIN_SECRET"] = "test-admin-secret"
    r = client.post("/admin/ops/reseed-seeded", headers={"X-Admin-Secret": "nope"})
    assert r.status_code == 403
