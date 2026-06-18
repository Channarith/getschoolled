"""Human-of-record + learner report/appeal loop (Trust layer, Phase 4)."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def test_course_has_human_of_record_field():
    course = client.post("/courses", json={
        "title": "Anatomy 101", "subject": "medical",
        "human_of_record": "Dr. Patel", "reviewed_by": "Dr. Patel",
    }).json()
    assert course["human_of_record"] == "Dr. Patel"
    got = client.get(f"/courses/{course['course_id']}").json()
    assert got["human_of_record"] == "Dr. Patel"


def test_report_creates_submitted_correction():
    r = client.post("/report", json={
        "target_kind": "claim", "target_id": "sess-1",
        "locator": "Plants breathe carbon dioxide only.",
        "issue": "This is misleading; plants also release oxygen.",
        "author": "student",
    }).json()
    assert r["status"] == "submitted"
    assert r["rationale"].startswith("This is misleading")

    # It shows up in the review queue for a human.
    listed = client.get("/corrections", params={"status": "submitted"}).json()
    assert any(c["id"] == r["id"] for c in listed)


def test_reported_issue_can_be_resolved():
    r = client.post("/report", json={
        "target_kind": "claim", "locator": "x", "issue": "wrong", "suggested": "right",
    }).json()
    client.post(f"/corrections/{r['id']}/approve")
    got = client.get(f"/corrections/{r['id']}").json()
    assert got["status"] == "approved"
