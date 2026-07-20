"""Verified pass decisions and durable 0/7/30/90-day retention checks."""

from aoep_shared.auth import sign_token
from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)
KEY = b"dev-assessment-signing-key"


def _learner(email: str):
    signup = client.post("/auth/signup", json={
        "email": email,
        "password": "S3cretpass",
        "display_name": "Assessment Learner",
    }).json()
    headers = {"Authorization": f"Bearer {signup['token']}"}
    student_id = client.get("/students", headers=headers).json()["students"][0]["id"]
    return headers, student_id


def test_signed_pass_schedules_retention_and_updates_enrollment():
    headers, student_id = _learner("assessment-pass@example.com")
    token = sign_token({
        "kind": "assessment_pass",
        "student_id": student_id,
        "course_id": "course-1",
        "score": 0.8,
        "attempt_ids": ["attempt-final"],
        "ksb_codes": ["K1", "S1", "B1"],
    }, KEY)
    response = client.post(
        f"/students/{student_id}/assessment-pass",
        headers=headers,
        json={"decision_token": token},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["passed"] is True
    assert [row["interval_days"] for row in body["retention_checks"]] == [1, 7, 30, 90]
    enrollment = app.state.accounts.by_email("assessment-pass@example.com").enrollments["course-1"]
    assert enrollment.assessment_verified is True
    assert enrollment.assessment_attempt_id == "attempt-final"

    due = client.get(
        f"/students/{student_id}/retention/due",
        headers=headers,
    ).json()["checks"]
    # First check is due in 1 day, not immediately — no check should be due right now.
    assert len(due) == 0

    history = client.get(
        f"/students/{student_id}/assessment-history",
        headers=headers,
    ).json()
    assert history["attempts"][0]["ksb_codes"] == ["K1", "S1", "B1"]


def test_retention_result_is_verified_and_removed_from_due_queue():
    headers, student_id = _learner("retention-result@example.com")
    pass_token = sign_token({
        "kind": "assessment_pass",
        "student_id": student_id,
        "course_id": "course-2",
        "score": 1.0,
        "attempt_ids": ["attempt-pass"],
        "ksb_codes": [],
    }, KEY)
    passed = client.post(
        f"/students/{student_id}/assessment-pass",
        headers=headers,
        json={"decision_token": pass_token},
    ).json()
    check_id = passed["retention_checks"][0]["check_id"]
    result_token = sign_token({
        "kind": "retention_result",
        "student_id": student_id,
        "course_id": "course-2",
        "check_id": check_id,
        "attempt_id": "attempt-retain",
        "score": 0.75,
        "passed": True,
    }, KEY)
    recorded = client.post(
        f"/students/{student_id}/retention/{check_id}/result",
        headers=headers,
        json={"result_token": result_token},
    )
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()["check"]["status"] == "completed"
    due = client.get(
        f"/students/{student_id}/retention/due",
        headers=headers,
    ).json()["checks"]
    assert due == []


def test_unsigned_pass_is_rejected():
    headers, student_id = _learner("assessment-forged@example.com")
    response = client.post(
        f"/students/{student_id}/assessment-pass",
        headers=headers,
        json={"decision_token": "not-signed"},
    )
    assert response.status_code == 422


def test_signed_formative_attempt_is_durable_and_idempotent():
    headers, student_id = _learner("assessment-formative@example.com")
    token = sign_token({
        "kind": "assessment_attempt",
        "student_id": student_id,
        "course_id": "course-3",
        "checkpoint_id": "progress-25",
        "stage": "formative",
        "attempt_id": "attempt-formative",
        "score": 2 / 3,
        "passed": True,
        "presentation_format": "audio",
        "ksb_codes": ["K1"],
    }, KEY)
    first = client.post(
        f"/students/{student_id}/assessment-attempt",
        headers=headers,
        json={"attempt_token": token},
    )
    second = client.post(
        f"/students/{student_id}/assessment-attempt",
        headers=headers,
        json={"attempt_token": token},
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["attempt_count"] == second.json()["attempt_count"] == 1
    history = client.get(
        f"/students/{student_id}/assessment-history",
        headers=headers,
    ).json()
    assert history["attempts"][0]["presentation_format"] == "audio"
