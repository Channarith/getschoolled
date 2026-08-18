"""HARD RULE: accreditation / certification requires a registered account.

Guests may start sample (non-certifiable) courses. Certifiable courses
require a bearer token with a registered account id. Identity also refuses
to mark certifiable courses PASSED without a verified pass token — even in
local/dev where unverified passes are otherwise allowed for sample courses.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from aoep_shared.accreditation import (
    ACCREDITATION_ACCOUNT_REQUIRED,
    ACCREDITATION_ACCOUNT_REQUIRED_DETAIL,
    ACCREDITATION_VERIFIED_PASS_REQUIRED,
    is_certifiable_lesson,
    may_mark_accreditation_passed,
    may_start_for_accreditation,
    requires_registered_account,
)
from aoep_shared.auth import sign_token
from orchestrator.main import app

client = TestClient(app)

_DEV_KEY = b"dev-auth-signing-key"
SAMPLE_LESSON = "intro-to-photosynthesis"
CERT_LESSON = "osha-general-safety"


def _auth_headers(account_id: str = "acct-registered") -> dict:
    token = sign_token(
        {"sub": account_id, "email": f"{account_id}@test.invalid"},
        _DEV_KEY,
    )
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Shared helpers (unit)
# --------------------------------------------------------------------------- #

class TestAccreditationHelpers:
    def test_certifiable_lessons_detected(self):
        assert is_certifiable_lesson(CERT_LESSON) is True
        assert is_certifiable_lesson("sexual-harassment-prevention") is True
        assert is_certifiable_lesson(SAMPLE_LESSON) is False
        assert is_certifiable_lesson("intro-python") is False
        assert is_certifiable_lesson("") is False

    def test_requires_registered_account_only_for_certifiable(self):
        assert requires_registered_account(CERT_LESSON) is True
        assert requires_registered_account(SAMPLE_LESSON) is False

    def test_guest_may_start_sample_but_not_certifiable(self):
        ok, reason = may_start_for_accreditation(SAMPLE_LESSON, account_id=None)
        assert ok is True
        assert reason == "sample_or_non_certifiable"

        ok, reason = may_start_for_accreditation(CERT_LESSON, account_id=None)
        assert ok is False
        assert reason == ACCREDITATION_ACCOUNT_REQUIRED

        ok, reason = may_start_for_accreditation(CERT_LESSON, account_id="")
        assert ok is False

    def test_registered_account_may_start_certifiable(self):
        ok, reason = may_start_for_accreditation(
            CERT_LESSON, account_id="acct-123",
        )
        assert ok is True
        assert reason == "registered_account"

    def test_accreditation_passed_requires_verified_token(self):
        ok, reason = may_mark_accreditation_passed(
            CERT_LESSON, has_verified_pass_token=False,
        )
        assert ok is False
        assert reason == ACCREDITATION_VERIFIED_PASS_REQUIRED

        ok, reason = may_mark_accreditation_passed(
            CERT_LESSON, has_verified_pass_token=True,
        )
        assert ok is True

        # Sample courses are not gated by this helper.
        ok, reason = may_mark_accreditation_passed(
            SAMPLE_LESSON, has_verified_pass_token=False,
        )
        assert ok is True
        assert reason == "non_certifiable"


# --------------------------------------------------------------------------- #
# Orchestrator HTTP gate
# --------------------------------------------------------------------------- #

class TestOrchestratorAccreditationGate:
    def test_guest_can_start_sample_lesson(self):
        r = client.post(
            "/api/sessions",
            json={"lesson_id": SAMPLE_LESSON, "class_type": "solo"},
        )
        assert r.status_code == 200, r.text

    def test_guest_blocked_from_certifiable_lesson(self):
        r = client.post(
            "/api/sessions",
            json={"lesson_id": CERT_LESSON, "class_type": "solo"},
        )
        assert r.status_code == 401, r.text
        assert ACCREDITATION_ACCOUNT_REQUIRED_DETAIL in r.json()["detail"]
        assert r.headers.get("X-AOEP-Gate") == ACCREDITATION_ACCOUNT_REQUIRED

    def test_registered_account_can_start_certifiable_lesson(self):
        r = client.post(
            "/api/sessions",
            headers=_auth_headers(),
            json={"lesson_id": CERT_LESSON, "class_type": "solo"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["session"]["lesson_id"] == CERT_LESSON

    def test_accreditation_metadata_endpoint(self):
        r = client.get(f"/api/lessons/{CERT_LESSON}/accreditation")
        assert r.status_code == 200
        body = r.json()
        assert body["certifiable"] is True
        assert body["requires_registered_account"] is True
        assert body["certification_body"] == "OSHA"
        assert body["ceu_credits"] > 0

        r2 = client.get(f"/api/lessons/{SAMPLE_LESSON}/accreditation")
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["certifiable"] is False
        assert body2["requires_registered_account"] is False

    def test_other_certifiable_lessons_also_gated(self):
        for lid in (
            "cpr-first-aid-certification",
            "food-handler-safety",
            "hipaa-privacy-security",
        ):
            r = client.post(
                "/api/sessions",
                json={"lesson_id": lid, "class_type": "group"},
            )
            assert r.status_code == 401, f"{lid}: {r.text}"
