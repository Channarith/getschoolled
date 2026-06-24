"""Learning profile onboarding on student profiles."""

from fastapi.testclient import TestClient
from identity.main import app

client = TestClient(app)


def _signup(email="learn@example.com"):
    return client.post("/auth/signup", json={
        "email": email, "password": "S3cretpass", "display_name": "Learner",
    }).json()


def _answers():
    return {
        "primary_style": "Hands-on — practice, labs, doing it yourself",
        "pace": "Moderate and steady",
        "structure": "Short bursts with frequent practice",
        "session_length": "About 20–30 minutes",
        "group_preference": "Either works for me",
        "reading_level": "Intermediate",
        "motivation": "Personal curiosity",
    }


def test_signup_creates_default_student():
    tok = _signup("auto-student@example.com")["token"]
    h = {"Authorization": f"Bearer {tok}"}
    students = client.get("/students", headers=h).json()["students"]
    assert len(students) == 1
    assert students[0]["display_name"] == "Learner"


def test_submit_learning_profile_updates_student():
    tok = _signup("profile@example.com")["token"]
    h = {"Authorization": f"Bearer {tok}"}
    sid = client.get("/students", headers=h).json()["students"][0]["id"]
    r = client.post(f"/students/{sid}/learning-profile", headers=h, json={"answers": _answers()})
    assert r.status_code == 200
    body = r.json()
    assert body["learner_category"] == "hands_on_practice"
    prof = client.get(f"/students/{sid}", headers=h).json()
    assert prof["primary_style"] == "hands_on"
    assert prof["onboarding_completed_at"] is not None
    assert prof["onboarding_answers"]["primary_style"] == _answers()["primary_style"]


def test_skip_learning_profile_persists():
    tok = _signup("skip@example.com")["token"]
    h = {"Authorization": f"Bearer {tok}"}
    sid = client.get("/students", headers=h).json()["students"][0]["id"]
    r = client.post(f"/students/{sid}/learning-profile/skip", headers=h)
    assert r.status_code == 200
    prof = client.get(f"/students/{sid}", headers=h).json()
    assert prof["onboarding_completed_at"] is not None
    assert prof["learner_category"] == "skipped"
