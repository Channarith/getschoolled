"""Student sub-profiles (one account, multiple learners)."""

import uuid

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _auth():
    email = f"fam-{uuid.uuid4().hex[:8]}@example.com"
    tok = client.post("/auth/signup", json={"email": email, "password": "S3cretpass"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def test_create_list_and_mastery():
    h = _auth()
    a = client.post("/students", headers=h, json={"display_name": "Kid A", "age_band": "child"}).json()
    b = client.post("/students", headers=h, json={"display_name": "Adult B", "interests": ["math"]}).json()
    assert a["display_name"] == "Kid A" and a["age_band"] == "child"

    students = client.get("/students", headers=h).json()["students"]
    # Signup auto-creates one default learner profile (onboarding survey path).
    assert len(students) == 3
    names = {s["display_name"] for s in students}
    assert {"Kid A", "Adult B"}.issubset(names)

    upd = client.post(f"/students/{a['id']}/mastery", headers=h, json={"skill": "fractions", "value": 0.3}).json()
    assert upd["mastery"]["fractions"] == 0.3

    comp = client.post(f"/students/{b['id']}/complete", headers=h,
                       json={"course_id": "c_alg", "skills": ["algebra"]}).json()
    assert "c_alg" in comp["completed_course_ids"]
    assert comp["mastery"]["algebra"] >= 0.8


def test_profiles_are_isolated_per_account():
    h2 = _auth()  # a fresh, distinct account
    client.post("/students", headers=h2, json={"display_name": "Only Me"})
    students = client.get("/students", headers=h2).json()["students"]
    # Default profile from signup + the one we added.
    assert len(students) == 2
    assert any(s["display_name"] == "Only Me" for s in students)


def test_unknown_student_404():
    h = _auth()
    assert client.get("/students/ghost", headers=h).status_code == 404
    assert client.post("/students/ghost/mastery", headers=h,
                       json={"skill": "x", "value": 0.5}).status_code == 404
