from fastapi.testclient import TestClient

from memory.main import app
from memory.store import MemoryStore

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["service"] == "memory"


def test_consent_round_trip():
    client.post("/students", json={"student_id": "s1", "display_name": "Sam"})
    client.post(
        "/consent",
        json={"student_id": "s1", "scope": "face_recognition", "granted": True},
    )
    resp = client.get("/consent/s1/face_recognition")
    assert resp.json()["granted"] is True


def test_consent_defaults_to_false():
    resp = client.get("/consent/never-seen/recording")
    assert resp.json()["granted"] is False


def test_mastery_moves_toward_correctness():
    store = MemoryStore()
    store.upsert_student("s2", "Sky")
    first = store.update_mastery("s2", "loops", True)
    second = store.update_mastery("s2", "loops", True)
    assert 0 < first < second <= 1.0


def test_mastery_endpoint():
    body = client.post(
        "/mastery", json={"student_id": "s3", "topic": "vars", "correct": True}
    ).json()
    assert body["mastery"] > 0
