from fastapi.testclient import TestClient

from perception.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["service"] == "perception"


def test_only_consented_students_are_identified():
    resp = client.post(
        "/analyze/consent-check",
        json={
            "frame_object_key": "frames/r1/000123.jpg",
            "detected_student_ids": ["alice", "bob"],
            "consented_student_ids": ["alice"],
        },
    )
    by_id = {d["student_id"]: d for d in resp.json()["decisions"]}
    assert by_id["alice"]["identify_allowed"] is True
    assert by_id["alice"]["mode"] == "identity"
    assert by_id["bob"]["identify_allowed"] is False
    assert by_id["bob"]["mode"] == "anonymous"
