"""HARD RULE: certifiable courses cannot be marked PASSED without a verified token.

Even in local/dev (where sample courses still allow unverified pass for demos),
accreditation / certification courses always require a pass_decision_token.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from aoep_shared.accreditation import ACCREDITATION_VERIFIED_PASS_DETAIL
from identity.main import app

client = TestClient(app)

CERT_COURSE = "osha-general-safety"
SAMPLE_COURSE = "intro-to-photosynthesis"


def _signup(email: str, password: str = "S3cretpass"):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": password, "display_name": "Cert"},
    ).json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_certifiable_passed_without_token_denied_even_in_local(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "local")
    monkeypatch.delenv("ALLOW_UNVERIFIED_PASS", raising=False)
    tok = _signup("cert-local@example.com")["token"]
    h = _auth(tok)
    client.post(
        "/enrollments",
        headers=h,
        json={"course_id": CERT_COURSE, "title": "OSHA General Safety"},
    )
    r = client.post(
        f"/enrollments/{CERT_COURSE}/status",
        headers=h,
        json={"status": "passed"},
    )
    assert r.status_code == 403, r.text
    assert ACCREDITATION_VERIFIED_PASS_DETAIL in r.json()["detail"]
    assert r.headers.get("X-AOEP-Gate") == "accreditation_verified_pass_required"


def test_sample_passed_without_token_still_ok_in_local(monkeypatch):
    """Non-certifiable sample courses keep the local/dev unverified-pass path."""
    monkeypatch.setenv("DEPLOY_MODE", "local")
    tok = _signup("sample-local@example.com")["token"]
    h = _auth(tok)
    client.post(
        "/enrollments",
        headers=h,
        json={"course_id": SAMPLE_COURSE, "title": "Photosynthesis"},
    )
    r = client.post(
        f"/enrollments/{SAMPLE_COURSE}/status",
        headers=h,
        json={"status": "passed"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "passed"


def test_guest_cannot_enroll_or_pass_at_all():
    """Enrollment endpoints require auth — guests never get accreditation credit."""
    r = client.post(
        "/enrollments",
        json={"course_id": CERT_COURSE, "title": "OSHA"},
    )
    assert r.status_code in (401, 403)
    r2 = client.post(
        f"/enrollments/{CERT_COURSE}/status",
        json={"status": "passed"},
    )
    assert r2.status_code in (401, 403)
