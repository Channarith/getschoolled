"""Membership tier changes must be locked to internal callers
(the billing service after a verified payment, or a teacher / admin
agent) - NOT to the end user themselves.

Before the audit, an authenticated user could call
POST /membership/tier with any tier value and bypass billing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from identity.main import app


@pytest.fixture(autouse=True)
def _enable_internal_auth(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)


def _signup_and_session(client: TestClient) -> str:
    """Create a fresh account and return its session token."""
    r = client.post("/auth/signup", json={
        "email": "audit-test@example.com",
        "password": "correct-horse-battery-staple",
        "region": "us",
    })
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_tier_change_denied_without_internal_token():
    client = TestClient(app)
    token = _signup_and_session(client)
    r = client.post(
        "/membership/tier",
        json={"tier": "school"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (401, 403), (
        f"POST /membership/tier should require internal auth, got "
        f"{r.status_code}: {r.text!r}"
    )
