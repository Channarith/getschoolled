"""Catalog HTTP API + adaptive program plan tests."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def test_course_and_program_crud_api():
    c1 = client.post("/courses", json={"title": "Basics", "subject": "math"}).json()
    c2 = client.post("/courses", json={"title": "Advanced", "subject": "math"}).json()
    assert client.get(f"/courses/{c1['course_id']}").status_code == 200

    prog = client.post("/programs", json={
        "title": "Math Track", "audience": "g9",
        "course_ids": [c1["course_id"], c2["course_id"]],
        "adaptive_rules": {"prereq_mastery": {c2["course_id"]: 0.7}},
    }).json()
    assert client.get(f"/programs/{prog['program_id']}").status_code == 200

    tree = client.get("/catalog").json()
    assert any(c["course_id"] == c1["course_id"] for c in tree["courses"])
    assert any(p["program_id"] == prog["program_id"] for p in tree["programs"])


def test_program_plan_gates_by_mastery():
    c1 = client.post("/courses", json={"title": "Intro"}).json()
    c2 = client.post("/courses", json={"title": "Next"}).json()
    prog = client.post("/programs", json={
        "title": "Seq", "course_ids": [c1["course_id"], c2["course_id"]],
        "adaptive_rules": {"prereq_mastery": {c2["course_id"]: 0.7}},
    }).json()
    pid = prog["program_id"]

    # No mastery -> c2 locked, next is c1.
    low = client.post(f"/programs/{pid}/plan", json={"mastery": {}}).json()
    by = {p["course_id"]: p for p in low["plan"]}
    assert by[c1["course_id"]]["unlocked"] is True
    assert by[c2["course_id"]]["unlocked"] is False
    assert low["next_course"] == c1["course_id"]

    # c1 mastered -> c2 unlocks.
    hi = client.post(f"/programs/{pid}/plan",
                     json={"mastery": {c1["course_id"]: 0.8}}).json()
    by2 = {p["course_id"]: p for p in hi["plan"]}
    assert by2[c2["course_id"]]["unlocked"] is True


def test_unknown_404s():
    assert client.get("/courses/nope").status_code == 404
    assert client.get("/programs/nope").status_code == 404
    assert client.post("/programs/nope/plan", json={"mastery": {}}).status_code == 404
