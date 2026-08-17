"""Regression tests for the 2026-08-17 audit (orchestrator assessments).

- HIGH-46 Formative checkpoints kept required_domains=[KNOWLEDGE] while items
          cycled across knowledge/skill/behaviour — students who met the score
          threshold failed on an invisible, mismatched domain requirement.
- MED-47  A malformed submit (wrong answer count) destroyed the in-progress
          assessment run — the 422 path never put the run back.
"""

from fastapi.testclient import TestClient

from aoep_shared.auth import sign_token
from orchestrator.main import app

client = TestClient(app)

_DEV_KEY = b"dev-auth-signing-key"


def _auth_headers(account_id: str = "audit-account") -> dict:
    token = sign_token({"sub": account_id, "email": f"{account_id}@test.invalid"}, _DEV_KEY)
    return {"Authorization": f"Bearer {token}"}


def _session(lesson: str = "ai-fluency-essentials") -> dict:
    response = client.post("/api/sessions", json={
        "lesson_id": lesson,
        "class_type": "solo",
        "student_id": "audit-student",
    })
    assert response.status_code == 200, response.text
    return response.json()


# HIGH-46 ------------------------------------------------------------------ #

def test_formative_required_domains_match_actual_item_mix():
    started = _session()
    auth = _auth_headers()
    resp = client.post("/assessment/checkpoints/start", json={
        "student_id": "audit-student",
        "session_id": started["session"]["session_id"],
        "checkpoint_id": "progress-25",
        "stage": "formative",
        "max_items": 6,
    }, headers=auth)
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]
    run = app.state.assessment_runs[run_id]

    item_domains = {d.value for d in run["domain_by_item"].values()}
    required = {d.value for d in run["policy"].required_domains}
    # The course ships a ksb.json spanning all three domains; the requirement
    # must reflect the items, not the [KNOWLEDGE] class default.
    assert item_domains == {"knowledge", "skill", "behaviour"}
    assert required == item_domains


def test_formative_pass_with_threshold_and_full_domain_coverage():
    started = _session()
    auth = _auth_headers()
    resp = client.post("/assessment/checkpoints/start", json={
        "student_id": "audit-student",
        "session_id": started["session"]["session_id"],
        "checkpoint_id": "progress-25",
        "stage": "formative",
        "max_items": 6,
    }, headers=auth)
    run_id = resp.json()["run_id"]
    run = app.state.assessment_runs[run_id]
    correct = [item.answer_index for item in run["items"]]
    submitted = client.post(
        f"/assessment/checkpoints/{run_id}/submit",
        json={"chosen_indices": correct},
        headers=auth,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["attempt"]["passed"] is True


# MED-47 ------------------------------------------------------------------- #

def test_malformed_submit_does_not_destroy_the_run():
    started = _session()
    auth = _auth_headers()
    resp = client.post("/assessment/checkpoints/start", json={
        "student_id": "audit-student",
        "session_id": started["session"]["session_id"],
        "checkpoint_id": "progress-25",
        "stage": "formative",
        "max_items": 3,
    }, headers=auth)
    run_id = resp.json()["run_id"]

    bad = client.post(
        f"/assessment/checkpoints/{run_id}/submit",
        json={"chosen_indices": [0, 1]},  # one answer short
        headers=auth,
    )
    assert bad.status_code == 422
    assert run_id in app.state.assessment_runs, "422 submit consumed the run"

    run = app.state.assessment_runs[run_id]
    correct = [item.answer_index for item in run["items"]]
    good = client.post(
        f"/assessment/checkpoints/{run_id}/submit",
        json={"chosen_indices": correct},
        headers=auth,
    )
    assert good.status_code == 200, good.text
