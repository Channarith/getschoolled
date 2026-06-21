"""Corrections + catalog-export + provenance endpoints must be
locked to internal callers (training-staff / pipeline agents),
NOT exposed to the public web tier.

These endpoints can modify training data and sign content with the
server provenance key, so a public attacker could mass-approve bad
corrections or sign arbitrary content with the platform's signing
key. The internal-auth gate was added during the platform audit
pass; this regression test pins the behaviour.
"""

from __future__ import annotations

import pytest
from curriculum.main import app
from fastapi.testclient import TestClient


# (method, path, body). For GET requests, body is None.
GATED_ROUTES = [
    ("POST", "/corrections/bulk", None),  # multipart; we just need to confirm 403 before reaching body
    ("POST", "/corrections/some-id/approve", {}),
    ("POST", "/corrections/some-id/reject", {}),
    ("POST", "/corrections/some-id/apply", {}),
    ("GET",  "/catalog/export", None),
    ("POST", "/provenance/sign",
     {"artifact_id": "x", "content": "hello", "ai_generated": True}),
]


@pytest.fixture(autouse=True)
def _enable_internal_auth(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)


@pytest.mark.parametrize("method,path,body", GATED_ROUTES)
def test_gated_endpoint_denied_without_internal_token(method, path, body):
    client = TestClient(app)
    if method == "GET":
        r = client.get(path)
    else:
        # Some endpoints expect JSON, others multipart. The gate fires before
        # the body is parsed, so any reasonable POST body shape is fine.
        r = client.post(path, json=body or {})
    assert r.status_code in (401, 403), (
        f"{method} {path} should require internal auth, got "
        f"{r.status_code}: {r.text!r}"
    )
