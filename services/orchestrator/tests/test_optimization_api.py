"""Optimization ledger API: commit/promote, champion, history, revert."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def test_commit_promote_and_revert_flow():
    s1 = client.post("/api/optimization/commit", json={
        "stage": "policy", "metrics": {"accuracy": 0.7}}).json()
    assert s1["promoted"] is True

    s2 = client.post("/api/optimization/commit", json={
        "stage": "policy", "metrics": {"accuracy": 0.85}}).json()
    assert s2["promoted"] is True
    assert client.get("/api/optimization/champion/policy").json()["champion"]["step_id"] == s2["step"]["step_id"]

    # Regression is not promoted.
    s3 = client.post("/api/optimization/commit", json={
        "stage": "policy", "metrics": {"accuracy": 0.5}}).json()
    assert s3["promoted"] is False

    # Revert to the first step.
    rev = client.post("/api/optimization/revert", json={
        "stage": "policy", "step_id": s1["step"]["step_id"]})
    assert rev.status_code == 200
    assert client.get("/api/optimization/champion/policy").json()["champion"]["step_id"] == s1["step"]["step_id"]


def test_history_and_unknown_revert():
    client.post("/api/optimization/commit", json={"stage": "bkt", "metrics": {"accuracy": 0.6}})
    hist = client.get("/api/optimization/history", params={"stage": "bkt"}).json()
    assert len(hist["steps"]) >= 1
    bad = client.post("/api/optimization/revert", json={"stage": "bkt", "step_id": "nope"})
    assert bad.status_code == 404
