"""LMS/SIS gateway endpoints (Phase 18)."""

from fastapi.testclient import TestClient

from integrations.main import app

client = TestClient(app)
_LTI = "https://purl.imsglobal.org/spec/lti/claim"


def test_lti_launch_endpoint():
    body = client.post("/lms/lti/launch", json={
        f"{_LTI}/message_type": "LtiResourceLinkRequest",
        f"{_LTI}/version": "1.3.0", "sub": "u-1",
        f"{_LTI}/context": {"id": "c-1"}, f"{_LTI}/roles": ["Learner"],
    }).json()
    assert body["user_id"] == "u-1" and body["context_id"] == "c-1"


def test_lti_launch_rejects_bad():
    r = client.post("/lms/lti/launch", json={"sub": "x"})
    assert r.status_code == 400


def test_roster_import():
    body = client.post("/lms/roster", json={
        "context_id": "c-1",
        "payload": {"users": [{"sourcedId": "u1", "role": "student", "givenName": "A", "familyName": "B"}]},
    }).json()
    assert body["count"] == 1 and body["members"][0]["user_id"] == "u1"


def test_grade_passback_pushes_and_xapi():
    body = client.post("/lms/grade-passback", json={
        "user_id": "u1", "score": 9.0, "maximum": 10.0, "line_item": "hw-1", "export_xapi": True,
    }).json()
    assert body["pushed"]["scoreGiven"] == 9.0
    assert body["result"]["accepted"] is True
    assert body["xapi"]["result"]["score"]["scaled"] == 0.9
