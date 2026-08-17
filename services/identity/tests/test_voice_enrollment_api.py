"""Tests for voice-name enrollment endpoints.

POST /students/{student_id}/voice-enrollment   — store audio blob
GET  /students/{student_id}/voice-enrollment   — status (no blob)
GET  /students/{student_id}/voice-enrollment/blob — raw blob

Tests do NOT need real audio: we use a minimal base64 WAV stub.
"""

from __future__ import annotations

import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)

# Minimal valid base64 payload (1 byte of audio — enough to test storage).
_FAKE_AUDIO_B64 = base64.b64encode(b"\x00\xff" * 16).decode()
_FAKE_MIME = "audio/webm"


def _auth() -> dict:
    email = f"voice-{uuid.uuid4().hex[:8]}@example.com"
    tok = client.post(
        "/auth/signup", json={"email": email, "password": "S3cretpass"}
    ).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def _default_student_id(headers: dict) -> str:
    """Return the ID of the auto-created default student profile."""
    students = client.get("/students", headers=headers).json()["students"]
    assert len(students) >= 1
    return students[0]["id"]


# ================================================================== #
# POST /students/{id}/voice-enrollment
# ================================================================== #

class TestEnrollVoice:
    def test_enroll_voice_returns_200(self):
        h = _auth()
        sid = _default_student_id(h)
        resp = client.post(
            f"/students/{sid}/voice-enrollment",
            headers=h,
            json={
                "voice_name_sample_b64": _FAKE_AUDIO_B64,
                "voice_name_sample_mime": _FAKE_MIME,
                "voice_name_text": "Alice",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["voice_enrolled"] is True
        assert data["student_id"] == sid
        assert data["voice_name_text"] == "Alice"
        assert data["voice_name_sample_mime"] == _FAKE_MIME
        assert data["voice_enrolled_at"] is not None

    def test_enroll_voice_updates_profile(self):
        h = _auth()
        sid = _default_student_id(h)
        client.post(
            f"/students/{sid}/voice-enrollment",
            headers=h,
            json={"voice_name_sample_b64": _FAKE_AUDIO_B64, "voice_name_text": "Bob"},
        )
        # Status endpoint should reflect the enrollment.
        status = client.get(f"/students/{sid}/voice-enrollment", headers=h).json()
        assert status["voice_enrolled"] is True
        assert status["voice_name_text"] == "Bob"
        assert status["has_sample"] is True

    def test_enroll_voice_can_overwrite(self):
        """Re-enrolling should overwrite the previous sample."""
        h = _auth()
        sid = _default_student_id(h)
        client.post(
            f"/students/{sid}/voice-enrollment",
            headers=h,
            json={"voice_name_sample_b64": _FAKE_AUDIO_B64, "voice_name_text": "Old Name"},
        )
        client.post(
            f"/students/{sid}/voice-enrollment",
            headers=h,
            json={"voice_name_sample_b64": _FAKE_AUDIO_B64, "voice_name_text": "New Name"},
        )
        status = client.get(f"/students/{sid}/voice-enrollment", headers=h).json()
        assert status["voice_name_text"] == "New Name"

    def test_enroll_voice_empty_b64_returns_422(self):
        h = _auth()
        sid = _default_student_id(h)
        resp = client.post(
            f"/students/{sid}/voice-enrollment",
            headers=h,
            json={"voice_name_sample_b64": "   ", "voice_name_text": "Alice"},
        )
        assert resp.status_code == 422

    def test_enroll_voice_unknown_student_returns_404(self):
        h = _auth()
        resp = client.post(
            "/students/does-not-exist/voice-enrollment",
            headers=h,
            json={"voice_name_sample_b64": _FAKE_AUDIO_B64, "voice_name_text": "Ghost"},
        )
        assert resp.status_code == 404

    def test_enroll_voice_requires_auth(self):
        # Without Authorization header the endpoint should reject.
        resp = client.post(
            "/students/any-id/voice-enrollment",
            json={"voice_name_sample_b64": _FAKE_AUDIO_B64, "voice_name_text": "X"},
        )
        assert resp.status_code in (401, 403)

    def test_enroll_voice_default_mime(self):
        """MIME defaults to audio/webm when not supplied."""
        h = _auth()
        sid = _default_student_id(h)
        resp = client.post(
            f"/students/{sid}/voice-enrollment",
            headers=h,
            json={"voice_name_sample_b64": _FAKE_AUDIO_B64, "voice_name_text": "Carol"},
        )
        assert resp.status_code == 200
        assert resp.json()["voice_name_sample_mime"] == "audio/webm"


# ================================================================== #
# GET /students/{id}/voice-enrollment
# ================================================================== #

class TestGetVoiceEnrollmentStatus:
    def test_not_enrolled_shows_false(self):
        h = _auth()
        sid = _default_student_id(h)
        resp = client.get(f"/students/{sid}/voice-enrollment", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["voice_enrolled"] is False
        assert data["has_sample"] is False
        assert data["voice_name_text"] == ""

    def test_enrolled_shows_true(self):
        h = _auth()
        sid = _default_student_id(h)
        client.post(
            f"/students/{sid}/voice-enrollment",
            headers=h,
            json={"voice_name_sample_b64": _FAKE_AUDIO_B64, "voice_name_text": "Dave"},
        )
        resp = client.get(f"/students/{sid}/voice-enrollment", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["voice_enrolled"] is True
        assert data["has_sample"] is True
        assert data["voice_name_text"] == "Dave"
        # Blob must NOT be included in this response.
        assert "voice_name_sample_b64" not in data

    def test_unknown_student_returns_404(self):
        h = _auth()
        resp = client.get("/students/nobody/voice-enrollment", headers=h)
        assert resp.status_code == 404

    def test_status_is_isolated_per_account(self):
        h1 = _auth()
        h2 = _auth()
        sid1 = _default_student_id(h1)
        sid2 = _default_student_id(h2)
        client.post(
            f"/students/{sid1}/voice-enrollment",
            headers=h1,
            json={"voice_name_sample_b64": _FAKE_AUDIO_B64, "voice_name_text": "Eve"},
        )
        # Account 2 should not see account 1's enrollment.
        resp = client.get(f"/students/{sid2}/voice-enrollment", headers=h2)
        assert resp.json()["voice_enrolled"] is False


# ================================================================== #
# GET /students/{id}/voice-enrollment/blob
# ================================================================== #

class TestGetVoiceBlob:
    def test_blob_not_found_before_enrollment(self):
        h = _auth()
        sid = _default_student_id(h)
        resp = client.get(f"/students/{sid}/voice-enrollment/blob", headers=h)
        assert resp.status_code == 404

    def test_blob_returned_after_enrollment(self):
        h = _auth()
        sid = _default_student_id(h)
        client.post(
            f"/students/{sid}/voice-enrollment",
            headers=h,
            json={
                "voice_name_sample_b64": _FAKE_AUDIO_B64,
                "voice_name_sample_mime": "audio/wav",
                "voice_name_text": "Frank",
            },
        )
        resp = client.get(f"/students/{sid}/voice-enrollment/blob", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["voice_name_sample_b64"] == _FAKE_AUDIO_B64
        assert data["voice_name_sample_mime"] == "audio/wav"
        assert data["voice_name_text"] == "Frank"
        assert data["student_id"] == sid

    def test_blob_requires_auth(self):
        resp = client.get("/students/any/voice-enrollment/blob")
        assert resp.status_code in (401, 403)


# ================================================================== #
# Store-level unit tests (no HTTP)
# ================================================================== #

class TestStoreEnrollVoice:
    def test_enroll_voice_persists_to_profile(self):
        from identity.store import AccountStore
        from aoep_shared.auth import hash_password

        store = AccountStore()  # in-memory (no Redis configured by default in tests)
        email = f"store-{uuid.uuid4().hex[:8]}@test.com"
        acct = store.create(email, hash_password("S3cret"))
        prof = store.ensure_default_student(acct.id)

        store.enroll_voice(
            acct.id,
            prof.id,
            voice_name_sample_b64=_FAKE_AUDIO_B64,
            voice_name_sample_mime="audio/webm",
            voice_name_text="Greta",
        )

        updated = store.get_student(acct.id, prof.id)
        assert updated is not None
        assert updated.voice_name_sample_b64 == _FAKE_AUDIO_B64
        assert updated.voice_name_text == "Greta"
        assert updated.voice_enrolled_at is not None
        assert updated.voice_name_sample_mime == "audio/webm"

    def test_enroll_voice_unknown_student_raises(self):
        from identity.store import AccountStore
        from aoep_shared.auth import hash_password

        store = AccountStore()
        email = f"store2-{uuid.uuid4().hex[:8]}@test.com"
        acct = store.create(email, hash_password("S3cret"))

        with pytest.raises(KeyError):
            store.enroll_voice(
                acct.id, "ghost-id",
                voice_name_sample_b64=_FAKE_AUDIO_B64,
                voice_name_sample_mime="audio/webm",
                voice_name_text="Nobody",
            )
