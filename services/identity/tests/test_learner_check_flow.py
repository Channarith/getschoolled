"""Learner Check from Get started to Continue, through real identity and perception.

Identity's calls to perception go to perception's own app in this process,
so consent, the five-face pose gate, the face gallery, the encrypted voice
gallery, and the setup-assistant state all run as they do in the stack. Only
the speaker model is replaced, by a fixed vector, so no model download is
needed.
"""

from __future__ import annotations

import base64
import math
import os
import random
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("cryptography")

_PERCEPTION_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "perception", "src")
)
if _PERCEPTION_SRC not in sys.path:
    sys.path.insert(0, _PERCEPTION_SRC)

import identity.main as identity_main  # noqa: E402
import perception.main as perception_main  # noqa: E402

client = TestClient(identity_main.app)
perception = TestClient(perception_main.app)
TOKEN = "learner-check-flow-token"


def _vector(rng: random.Random) -> list[float]:
    return [rng.uniform(-0.5, 0.5) for _ in range(128)]


def _pose_embeddings() -> list[list[float]]:
    rng = random.Random(7)
    base = _vector(rng)
    return [
        [b + 0.25 * o for b, o in zip(base, _vector(rng))]
        for _ in range(5)
    ]


class _FakeSpeaker:
    def embedding(self, audio: bytes) -> list[float]:
        if len(audio) < 1_000:
            raise ValueError("voice sample must be between 8 and 15 seconds")
        vector = [math.sin(i + 1) for i in range(192)]
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector]


@pytest.fixture()
def stack(monkeypatch, tmp_path):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("INTERNAL_TOKEN", TOKEN)
    monkeypatch.setenv("VOICEPRINT_GALLERY_PATH", str(tmp_path / "voiceprints.enc"))
    monkeypatch.setenv("BIOMETRIC_ENCRYPTION_SECRET", "learner-check-flow-secret")
    monkeypatch.setattr(perception_main, "SherpaSpeakerProvider", _FakeSpeaker)

    def to_perception(path: str, payload: dict) -> dict:
        response = perception.post(path, json=payload, headers={"X-Internal-Token": TOKEN})
        if response.status_code >= 300:
            raise identity_main.HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()

    def delete_in_perception(student_id: str) -> None:
        response = perception.delete(f"/biometrics/{student_id}", headers={"X-Internal-Token": TOKEN})
        assert response.status_code == 200, response.text

    monkeypatch.setattr(identity_main, "_perception_json", to_perception)
    monkeypatch.setattr(identity_main, "_perception_delete", delete_in_perception)

    email = f"learner-check-{uuid.uuid4().hex[:8]}@example.com"
    token = client.post("/auth/signup", json={"email": email, "password": "S3cretpass"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    student_id = client.get("/students", headers=headers).json()["students"][0]["id"]
    return headers, student_id


def _start(headers: dict, student_id: str) -> None:
    consent = client.put(
        f"/students/{student_id}/biometric-consent",
        headers=headers,
        json={"granted": True, "guardian_granted": False, "retention_days": 365},
    )
    assert consent.status_code == 200, consent.text
    step = client.patch(
        f"/students/{student_id}/setup-assistant",
        headers=headers,
        json={"current_step": "biometrics"},
    )
    assert step.status_code == 200, step.text


def _save_face(headers: dict, student_id: str, embeddings: list[list[float]]):
    return client.post(
        f"/students/{student_id}/biometric-face",
        headers=headers,
        json={"embeddings": embeddings, "pose_sequence": ["up", "left", "down", "right"]},
    )


def _save_voice(headers: dict, student_id: str):
    audio = base64.b64encode(b"\x1aE\xdf\xa3" + os.urandom(40_000)).decode()
    return client.post(
        f"/students/{student_id}/voiceprint",
        headers=headers,
        json={"audio_b64": audio},
    )


def test_learner_check_runs_from_get_started_to_continue(stack):
    headers, student_id = stack
    _start(headers, student_id)

    face = _save_face(headers, student_id, _pose_embeddings())
    assert face.status_code == 200, face.text
    assert face.json() == {"student_id": student_id, "verified": True, "enrollments": 5}

    voice = _save_voice(headers, student_id)
    assert voice.status_code == 200, voice.text

    done = client.patch(
        f"/students/{student_id}/setup-assistant",
        headers=headers,
        json={"current_step": "complete", "complete": True},
    )
    assert done.status_code == 200, done.text
    state = client.get(f"/students/{student_id}/setup-assistant", headers=headers).json()
    assert state["current_step"] == "complete"
    assert state["completed_at"]
    assert state["portrait"]["status"] == "verified"
    assert state["pose"]["status"] == "verified"
    assert state["voice"]["status"] == "verified"

    gallery = perception.get("/gallery", headers={"X-Internal-Token": TOKEN}).json()
    assert any(student_id in str(entry) for entry in gallery.values())


def test_voice_saves_even_when_the_face_is_rejected(stack):
    headers, student_id = stack
    _start(headers, student_id)
    rng = random.Random(3)
    stranger = [_vector(rng) for _ in range(5)]

    face = _save_face(headers, student_id, stranger)
    assert face.status_code == 422
    assert face.json()["detail"].startswith("pose challenge face does not match portrait")

    voice = _save_voice(headers, student_id)
    assert voice.status_code == 200, voice.text

    retry = _save_face(headers, student_id, _pose_embeddings())
    assert retry.status_code == 200, retry.text
    state = client.get(f"/students/{student_id}/setup-assistant", headers=headers).json()
    assert state["portrait"]["status"] == "verified"
    assert state["voice"]["status"] == "verified"


def test_remove_saved_check_clears_both_galleries(stack):
    headers, student_id = stack
    _start(headers, student_id)
    assert _save_face(headers, student_id, _pose_embeddings()).status_code == 200
    assert _save_voice(headers, student_id).status_code == 200

    removed = client.delete(f"/students/{student_id}/biometrics", headers=headers)
    assert removed.status_code == 200, removed.text
    state = client.get(f"/students/{student_id}/setup-assistant", headers=headers).json()
    assert state["portrait"]["status"] == "revoked"
    assert state["voice"]["status"] == "revoked"


def test_perception_refuses_identity_without_the_shared_token(stack):
    response = perception.post("/enroll-embedding/someone", json={"embedding": [0.1, 0.2]})
    assert response.status_code == 403
