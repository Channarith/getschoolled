"""HIL co-teaching gate + queue API (Phase 11)."""

from fastapi.testclient import TestClient

from aoep_shared.hil import AutonomyLevel
from orchestrator.main import app

client = TestClient(app)


def _start_session():
    # Pin a known on-topic lesson so the suite is order-independent (adding new
    # curricula must not change which lesson lands at index 0).
    lessons = client.get("/api/lessons").json()
    ids = [lsn["lesson_id"] for lsn in lessons]
    lid = "intro-to-fractions" if "intro-to-fractions" in ids else lessons[0]["lesson_id"]
    return client.post("/api/sessions", json={"lesson_id": lid, "class_type": "group"}).json()["session"]["session_id"]


def test_suggest_mode_holds_answer_for_review():
    app.state.autonomy = AutonomyLevel.SUGGEST
    try:
        sid = _start_session()
        ans = client.post(f"/api/sessions/{sid}/ask", json={"text": "What is a fraction?"}).json()
        assert ans["pending_review"] is True
        assert ans["review_id"]

        # The drafted answer is in the review queue.
        q = client.get("/api/hil/queue", params={"status": "pending"}).json()
        assert q["autonomy"] == "suggest"
        assert any(i["id"] == ans["review_id"] for i in q["items"])

        # A human edits it.
        decided = client.post(
            f"/api/hil/{ans['review_id']}/decision",
            json={"action": "edit", "edited_payload": {"text": "Teacher-approved answer."}},
        ).json()
        assert decided["status"] == "edited"
        assert decided["final_payload"]["text"] == "Teacher-approved answer."
    finally:
        app.state.autonomy = AutonomyLevel.AUTONOMOUS


def test_autonomous_low_risk_not_held():
    app.state.autonomy = AutonomyLevel.AUTONOMOUS
    sid = _start_session()
    # On-topic question -> grounded, low risk -> delivered without review.
    ans = client.post(f"/api/sessions/{sid}/ask", json={"text": "What is a fraction?"}).json()
    assert ans["pending_review"] is False


def test_student_request_for_human_escalates():
    app.state.autonomy = AutonomyLevel.AUTONOMOUS
    sid = _start_session()
    ans = client.post(
        f"/api/sessions/{sid}/ask", json={"text": "Can I talk to a human teacher please?"}
    ).json()
    assert ans["pending_review"] is True


def test_decision_unknown_item_404():
    r = client.post("/api/hil/nope/decision", json={"action": "approve"})
    assert r.status_code == 404
