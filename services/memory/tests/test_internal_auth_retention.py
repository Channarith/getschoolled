"""Retention purge must be locked to internal callers.

This endpoint scans every store and deletes records past their
retention window. A public caller able to trigger it could be used
to amplify a denial-of-service attack or accelerate data loss; the
gate restricts it to the cron job / k8s CronJob.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from memory.main import app


@pytest.fixture(autouse=True)
def _enable_internal_auth(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)


def test_retention_purge_denied_without_internal_token():
    client = TestClient(app)
    r = client.post("/retention/purge", json={"default_retention_days": 365})
    assert r.status_code in (401, 403), (
        f"POST /retention/purge should require internal auth, got "
        f"{r.status_code}: {r.text!r}"
    )
