"""Signed-in lesson and test actions require a single-use face token."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aoep_shared.auth import sign_token
from aoep_shared.face_gate import FaceGateError
from orchestrator.main import app

client = TestClient(app)
LESSON = "intro-to-photosynthesis"
_DEV_KEY = b"dev-auth-signing-key"


def _auth(account_id: str = "face-account") -> dict:
    token = sign_token({"sub": account_id, "email": f"{account_id}@test.invalid"}, _DEV_KEY)
    return {"Authorization": f"Bearer {token}"}


def _install(monkeypatch, generation: dict | None = None):
    monkeypatch.setenv("FACE_GATE_ENABLED", "1")
    used: set[str] = set()
    current = generation if generation is not None else {"n": 1}

    def consume(token, *, account_id, student_id, purpose):
        del account_id
        if token in used:
            raise FaceGateError("face verification was already used")
        token_purpose, token_student = token.split(":")[:2]
        if token_purpose != purpose:
            raise FaceGateError("face verification is for a different action")
        if student_id and token_student != student_id:
            raise FaceGateError("face verification is for another student")
        used.add(token)
        return {"student_id": token_student, "generation": current["n"], "purpose": purpose}

    def fetch(account_id, student_id):
        del account_id, student_id
        return current["n"]

    monkeypatch.setattr("orchestrator.face_gate_client.consume_face_token", consume)
    monkeypatch.setattr("orchestrator.face_gate_client.fetch_face_generation", fetch)
    return used, current


def test_guest_session_stays_open_without_a_face_token(monkeypatch):
    _install(monkeypatch)
    response = client.post("/api/sessions", json={"lesson_id": LESSON, "class_type": "solo"})
    assert response.status_code == 200, response.text


def test_signed_in_start_and_checkpoint_reject_missing_reused_and_wrong_purpose(monkeypatch):
    _install(monkeypatch)
    headers = _auth()
    missing = client.post("/api/sessions", json={
        "lesson_id": LESSON,
        "class_type": "solo",
        "student_id": "stu-1",
    }, headers=headers)
    assert missing.status_code == 403
    assert "face verification" in missing.json()["detail"]

    wrong = client.post("/api/sessions", json={
        "lesson_id": LESSON,
        "class_type": "solo",
        "student_id": "stu-1",
        "face_token": "checkpoint:stu-1",
    }, headers=headers)
    assert wrong.status_code == 403

    started = client.post("/api/sessions", json={
        "lesson_id": LESSON,
        "class_type": "solo",
        "student_id": "stu-1",
        "face_token": "start:stu-1",
    }, headers=headers)
    assert started.status_code == 200, started.text
    session_id = started.json()["session"]["session_id"]

    no_face = client.post("/assessment/checkpoints/start", json={
        "student_id": "stu-1",
        "session_id": session_id,
        "checkpoint_id": "progress-25",
        "stage": "formative",
        "max_items": 3,
    }, headers=headers)
    assert no_face.status_code == 403

    opened = client.post("/assessment/checkpoints/start", json={
        "student_id": "stu-1",
        "session_id": session_id,
        "checkpoint_id": "progress-25",
        "stage": "formative",
        "max_items": 3,
        "face_token": "checkpoint:stu-1",
    }, headers=headers)
    assert opened.status_code == 200, opened.text
    run_id = opened.json()["run_id"]
    run = app.state.assessment_runs[run_id]
    correct = [item.answer_index for item in run["items"]]

    blocked = client.post(
        f"/assessment/checkpoints/{run_id}/submit",
        json={"chosen_indices": correct},
        headers=headers,
    )
    assert blocked.status_code == 403
    assert run_id in app.state.assessment_runs

    reused = client.post(
        f"/assessment/checkpoints/{run_id}/submit",
        json={"chosen_indices": correct, "face_token": "checkpoint:stu-1"},
        headers=headers,
    )
    assert reused.status_code == 403
    assert run_id in app.state.assessment_runs

    graded = client.post(
        f"/assessment/checkpoints/{run_id}/submit",
        json={"chosen_indices": correct, "face_token": "checkpoint:stu-1:submit"},
        headers=headers,
    )
    assert graded.status_code == 200, graded.text
    assert run_id not in app.state.assessment_runs


def test_pause_blocks_the_next_advance_until_a_fresh_resume_token(monkeypatch):
    _install(monkeypatch)
    headers = _auth("pause-account")
    started = client.post("/api/sessions", json={
        "lesson_id": LESSON,
        "class_type": "solo",
        "student_id": "stu-9",
        "face_token": "start:stu-9",
    }, headers=headers)
    assert started.status_code == 200, started.text
    session_id = started.json()["session"]["session_id"]
    slide_before = started.json()["session"]["current_slide"]
    paused = client.post(f"/api/sessions/{session_id}/face-pause", headers=headers)
    assert paused.status_code == 200, paused.text
    blocked = client.post(f"/api/sessions/{session_id}/advance", headers=headers)
    assert blocked.status_code == 403
    resumed = client.post(
        f"/api/sessions/{session_id}/advance",
        headers={**headers, "X-Face-Token": "resume:stu-9"},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["index"] >= slide_before


def test_replaced_face_blocks_advance_and_does_not_move_the_lesson(monkeypatch):
    generation = {"n": 1}
    _install(monkeypatch, generation)
    headers = _auth("replace-account")
    started = client.post("/api/sessions", json={
        "lesson_id": LESSON,
        "class_type": "solo",
        "student_id": "stu-3",
        "face_token": "start:stu-3",
    }, headers=headers)
    assert started.status_code == 200, started.text
    session_id = started.json()["session"]["session_id"]
    generation["n"] = 2
    blocked = client.post(f"/api/sessions/{session_id}/advance", headers=headers)
    assert blocked.status_code == 403
    assert "enrollment changed" in blocked.json()["detail"]
