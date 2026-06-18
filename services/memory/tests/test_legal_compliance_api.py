"""Legal acceptance + region compliance endpoints (memory service)."""

from fastapi.testclient import TestClient

from memory.main import app

client = TestClient(app)


def test_legal_notices_lists_required():
    body = client.get("/legal/notices").json()
    ids = {n["id"] for n in body["notices"]}
    assert {"license", "terms", "privacy", "aup", "dpa", "security"} <= ids
    assert set(body["required"]) == {"terms", "privacy", "aup"}


def test_accept_flow_tracks_outstanding():
    before = client.get("/legal/acceptance/stud-1").json()
    assert before["all_required_accepted"] is False
    assert "terms" in before["outstanding"]

    client.post("/legal/accept", json={"user_id": "stud-1", "notice_ids": ["terms", "privacy"]})
    mid = client.get("/legal/acceptance/stud-1").json()
    assert mid["all_required_accepted"] is False
    assert mid["outstanding"] == ["aup"]

    done = client.post("/legal/accept", json={"user_id": "stud-1", "notice_ids": ["aup"]}).json()
    assert done["all_required_accepted"] is True
    assert done["outstanding"] == []


def test_compliance_summary_endpoint():
    eu = client.get("/compliance/eu").json()
    assert eu["emotion_recognition_allowed"] is False
    assert "EU AI Act" in eu["frameworks"]
    us = client.get("/compliance/us").json()
    assert us["emotion_recognition_allowed"] is True
