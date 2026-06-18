"""GET /api/disclosure endpoint (Trust layer, Phase 1)."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def test_disclosure_endpoint_returns_line():
    body = client.get("/api/disclosure").json()
    assert body["is_ai"] is True
    assert "line" in body and "AI instructor" in body["line"]
    assert "model_name" in body


def test_disclosure_endpoint_accepts_persona_and_human():
    body = client.get(
        "/api/disclosure", params={"persona": "language tutor", "human_of_record": "Prof. Kim"}
    ).json()
    assert body["persona"] == "language tutor"
    assert body["human_of_record"] == "Prof. Kim"
    assert "Prof. Kim" in body["line"]
