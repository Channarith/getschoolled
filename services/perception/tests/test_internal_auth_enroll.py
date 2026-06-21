"""Biometric face enrollment must be locked to internal callers
(the teacher agent or onboarding pipeline), NOT exposed to public
clients.

Even though consent is enforced at the policy layer, the act of
enrolling a face image against a student_id should never be open
to the public web tier.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from perception.main import app


@pytest.fixture(autouse=True)
def _enable_internal_auth(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)


def test_enroll_denied_without_internal_token():
    client = TestClient(app)
    # Minimal multipart payload; the gate fires before the body is read.
    r = client.post(
        "/enroll/student_123",
        files={"file": ("face.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
    )
    assert r.status_code in (401, 403), (
        f"POST /enroll/<sid> should require internal auth, got "
        f"{r.status_code}: {r.text!r}"
    )
