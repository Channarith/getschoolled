"""Orchestrator HIL + optimization-ledger endpoints must be locked
to internal callers (teacher / training pipeline agents), NOT
exposed to student clients.

Both the human-in-the-loop review queue (which can approve or
reject AI decisions) and the optimization ledger (which commits or
reverts model promotions) carry production-grade risk if a public
caller can drive them.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from orchestrator.main import app


GATED_ROUTES = [
    ("GET",  "/api/hil/queue", None),
    ("POST", "/api/hil/some-id/decision", {"action": "approve"}),
    ("POST", "/api/optimization/commit",
     {"stage": "retrieval", "params": {}, "metrics": {}}),
    ("POST", "/api/optimization/revert",
     {"stage": "retrieval", "step_id": "x"}),
]


@pytest.fixture(autouse=True)
def _enable_internal_auth(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)


@pytest.mark.parametrize("method,path,body", GATED_ROUTES)
def test_gated_endpoint_denied_without_internal_token(method, path, body):
    client = TestClient(app)
    r = client.get(path) if method == "GET" else client.post(path, json=body or {})
    assert r.status_code in (401, 403), (
        f"{method} {path} should require internal auth, got "
        f"{r.status_code}: {r.text!r}"
    )
