"""HIL co-grading: grades routed to review + override back-prop (Phase 12)."""

from fastapi.testclient import TestClient

from aoep_shared.hil import AutonomyLevel
from curriculum.main import app

client = TestClient(app)

ASSIGNMENT = {
    "title": "HW", "subject": "general",
    "questions": [{"type": "short", "prompt": "Explain", "answer_key": ""}],
}


def test_suggest_mode_routes_grade_to_review_and_override_backprops():
    app.state.autonomy = AutonomyLevel.SUGGEST
    try:
        body = client.post("/homework/grade", json={
            "assignment": ASSIGNMENT, "answers": ["some answer"], "subject": "general",
        }).json()
        assert body["pending_review"] is True
        rid = body["review_id"]

        q = client.get("/homework/grade-reviews", params={"status": "pending"}).json()
        assert q["autonomy"] == "suggest"
        assert any(i["id"] == rid for i in q["items"])

        before = len(client.get("/corrections").json())
        decided = client.post(f"/homework/grade-reviews/{rid}/decision", json={
            "action": "edit", "edited_payload": {"score": 1, "corrected": "Correct: plants release oxygen."},
        }).json()
        assert decided["status"] == "edited"

        # Override back-propagates as a correction.
        after = client.get("/corrections").json()
        assert len(after) == before + 1
        assert any("oxygen" in c["corrected"] for c in after)
    finally:
        app.state.autonomy = AutonomyLevel.AUTONOMOUS


def test_flagged_grade_escalates_in_autonomous():
    app.state.autonomy = AutonomyLevel.AUTONOMOUS
    # Medical subject restricts corroboration to trusted domains; an uncorroborated
    # answer (mock search is filtered out) scores low -> escalates for human review.
    med = {"title": "Med HW", "subject": "medical",
           "questions": [{"type": "short", "prompt": "What treats infection?", "answer_key": ""}]}
    body = client.post("/homework/grade", json={
        "assignment": med, "answers": ["zzz unrelated gibberish"], "subject": "medical",
    }).json()
    assert body["pending_review"] is True


def test_grade_review_unknown_404():
    r = client.post("/homework/grade-reviews/nope/decision", json={"action": "approve"})
    assert r.status_code == 404
