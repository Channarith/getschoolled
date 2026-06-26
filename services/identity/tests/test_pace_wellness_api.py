"""Course finish pace, wellness check-in, and content-access policy."""

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _signup(email="pace@example.com"):
    return client.post("/auth/signup", json={
        "email": email, "password": "S3cretpass", "display_name": "Pace",
    }).json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _student_id(tok):
    return client.get("/students", headers=_auth(tok)).json()["students"][0]["id"]


def test_course_completion_records_finish_pace():
    tok = _signup()["token"]
    h = _auth(tok)
    sid = _student_id(tok)
    client.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "course_completion",
        "payload": {
            "course_id": "intro-to-fractions",
            "minutes": 45,
            "expected_min": 25,
            "complexity": 2,
        },
    })
    adapt = client.get(f"/students/{sid}/adaptation", headers=h).json()["adaptation"]
    finishes = adapt["course_finishes"]
    assert finishes[-1]["pace_vs_expected"] == "slow"
    assert finishes[-1]["complexity"] == 2


def test_wellness_checkin_updates_profile():
    tok = _signup("well@example.com")["token"]
    h = _auth(tok)
    sid = _student_id(tok)
    out = client.post(f"/students/{sid}/wellness", headers=h, json={
        "state": "unwell", "reason": "migraine",
    }).json()
    assert out["adaptation"]["wellness_state"] == "unwell"


def test_adult_accessibility_allows_kids_content():
    tok = _signup("access@example.com")["token"]
    h = _auth(tok)
    sid = _student_id(tok)
    client.post(f"/students/{sid}/learning-profile", headers=h, json={
        "answers": {
            "primary_style": "Mixed — no single style stands out",
            "pace": "Slower with more review",
            "structure": "Step-by-step in order",
            "session_length": "About 20–30 minutes",
            "group_preference": "Either works for me",
            "reading_level": "Beginner — keep language simple",
            "motivation": "Personal curiosity",
            "needs_extra_time": True,
        },
    })
    out = client.post(f"/students/{sid}/content-access", headers=h, json={
        "maturity_rating": "kids", "level": "beginner",
    }).json()
    assert out["needs_simplified_content"] is True
    assert out["allowed"] is True
    assert out["reason"] == "adult_accessibility_child_content"


def test_adult_without_accommodation_blocked_from_kids():
    tok = _signup("noblock@example.com")["token"]
    h = _auth(tok)
    sid = _student_id(tok)
    out = client.post(f"/students/{sid}/content-access", headers=h, json={
        "maturity_rating": "kids",
    }).json()
    assert out["allowed"] is False


def test_complete_course_with_timing():
    tok = _signup("complete@example.com")["token"]
    h = _auth(tok)
    sid = _student_id(tok)
    prof = client.post(f"/students/{sid}/complete", headers=h, json={
        "course_id": "bio-101",
        "minutes": 22,
        "expected_min": 25,
        "complexity": 3,
    }).json()
    assert "bio-101" in prof["completed_course_ids"]
    assert prof["adaptation"]["course_finishes"]


def test_profile_context_includes_pace_and_learning_profile():
    tok = _signup("ctx@example.com")["token"]
    h = _auth(tok)
    sid = _student_id(tok)
    ctx = client.get(f"/students/{sid}/profile-context", headers=h).json()
    assert ctx["schema_version"] == "aoep.profile_context.v2"
    assert "learning_profile" in ctx["student"]
    assert "course_pace" in ctx
