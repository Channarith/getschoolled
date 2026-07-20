"""Server-held answer keys, checkpoints, adaptive formats, and pass decisions."""

from fastapi.testclient import TestClient

from aoep_shared.auth import sign_token
from orchestrator.main import app

client = TestClient(app)
LESSON = "intro-to-photosynthesis"

_DEV_KEY = b"dev-auth-signing-key"


def _auth_headers(account_id: str = "test-account") -> dict:
    token = sign_token({"sub": account_id, "email": f"{account_id}@test.invalid"}, _DEV_KEY)
    return {"Authorization": f"Bearer {token}"}


def _session():
    response = client.post("/api/sessions", json={
        "lesson_id": LESSON,
        "class_type": "solo",
        "student_id": "assessment-student",
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_policy_places_formative_checks_and_summative_at_end():
    started = _session()
    policy = client.get(
        f"/assessment/policy/{started['session']['session_id']}",
    )
    assert policy.status_code == 200
    body = policy.json()
    assert [row["checkpoint_id"] for row in body["checkpoints"]] == [
        "progress-25", "progress-50", "progress-75", "course-final",
    ]
    assert body["checkpoints"][0]["kind"] == "pop_quiz"
    assert body["checkpoints"][-1]["kind"] == "final_exam"
    assert body["retention_intervals_days"] == [1, 7, 30, 90]


def test_corporate_policy_uses_mid_pop_quiz_and_final_exam():
    """Professional/corporate courses: one mid-course pop quiz + end exam."""
    response = client.post("/api/sessions", json={
        "lesson_id": "ai-fluency-essentials",
        "class_type": "solo",
        "student_id": "corp-assessment-student",
    })
    assert response.status_code == 200, response.text
    started = response.json()
    session_id = started["session"]["session_id"]
    policy = client.get(f"/assessment/policy/{session_id}").json()
    assert policy["professional"] is True
    ids = [row["checkpoint_id"] for row in policy["checkpoints"]]
    assert ids == ["progress-mid", "course-final"]
    assert policy["checkpoints"][0]["title"] == "Mid-course pop quiz"
    assert policy["checkpoints"][1]["kind"] == "final_exam"


def test_unauthenticated_checkpoint_start_rejected():
    started = _session()
    response = client.post("/assessment/checkpoints/start", json={
        "student_id": "assessment-student",
        "session_id": started["session"]["session_id"],
        "checkpoint_id": "progress-25",
        "stage": "formative",
        "max_items": 3,
    })
    assert response.status_code == 401


def test_profile_selects_game_but_answer_key_stays_server_side():
    started = _session()
    response = client.post("/assessment/checkpoints/start", json={
        "student_id": "assessment-student",
        "session_id": started["session"]["session_id"],
        "checkpoint_id": "progress-25",
        "stage": "formative",
        "profile_score": "75115510",
        "max_items": 3,
    }, headers=_auth_headers())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["presentation_format"] == "game"
    assert body["answer_key_exposed"] is False
    assert all("answer_index" not in item for item in body["items"])
    assert all(item["game"]["timed"] is False for item in body["items"])


def test_course_pass_requires_end_of_course_summative_and_issues_token():
    started = _session()
    session_id = started["session"]["session_id"]
    auth = _auth_headers()
    early = client.post("/assessment/checkpoints/start", json={
        "student_id": "assessment-student",
        "session_id": session_id,
        "checkpoint_id": "course-final",
        "stage": "summative",
        "profile_score": "35115510",
    }, headers=auth)
    assert early.status_code == 409

    for _ in range(len(started["lesson"]["slides"]) + 1):
        client.post(f"/api/sessions/{session_id}/advance")
    final = client.post("/assessment/checkpoints/start", json={
        "student_id": "assessment-student",
        "session_id": session_id,
        "checkpoint_id": "course-final",
        "stage": "summative",
        "profile_score": "35115510",
        "max_items": 5,
    }, headers=auth)
    assert final.status_code == 200, final.text
    run_id = final.json()["run_id"]
    run = app.state.assessment_runs[run_id]
    correct = [item.answer_index for item in run["items"]]
    submitted = client.post(
        f"/assessment/checkpoints/{run_id}/submit",
        json={"chosen_indices": correct},
        headers=auth,
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["attempt"]["passed"] is True
    assert result["attempt_result_token"]
    assert result["course_decision"]["passed"] is True
    assert result["pass_decision_token"]
    assert run_id not in app.state.assessment_runs


def test_cross_account_submit_rejected():
    """A different account cannot submit an assessment run it did not start."""
    started = _session()
    session_id = started["session"]["session_id"]
    owner_auth = _auth_headers("account-owner")
    thief_auth = _auth_headers("account-thief")
    run_resp = client.post("/assessment/checkpoints/start", json={
        "student_id": "assessment-student",
        "session_id": session_id,
        "checkpoint_id": "progress-25",
        "stage": "formative",
        "max_items": 3,
    }, headers=owner_auth)
    assert run_resp.status_code == 200, run_resp.text
    run_id = run_resp.json()["run_id"]
    run = app.state.assessment_runs[run_id]
    correct = [item.answer_index for item in run["items"]]
    stolen = client.post(
        f"/assessment/checkpoints/{run_id}/submit",
        json={"chosen_indices": correct},
        headers=thief_auth,
    )
    assert stolen.status_code == 403
    assert run_id in app.state.assessment_runs
