"""Regression: post-class survey must be shown and recorded exactly once per
(student, course) pair.  Covers the 'survey keeps popping up' bug where the
server-side 409 dedup existed but was never tested, and the frontend had no
localStorage guard.  These tests verify the server-side half."""

from aoep_shared.flags import FlagStore
from aoep_shared.survey import SurveyStore
from fastapi.testclient import TestClient
from memory.main import app

client = TestClient(app)
ADMIN = {"X-Admin-Secret": "dev-admin-secret"}


def _reset():
    app.state.flags = FlagStore()
    app.state.surveys = SurveyStore()
    # Enable the survey flag so template is returned.
    client.put(
        "/admin/flags/engagement.post_class_survey",
        json={"enabled": True, "value": True},
        headers=ADMIN,
    )


def test_first_submission_recorded():
    _reset()
    r = client.post("/survey/post-class", json={
        "course_id": "bio-101", "overall": 5, "student_id": "stu-abc",
        "class_type": "live",
    })
    assert r.status_code == 200
    assert r.json()["recorded"] is True


def test_duplicate_submission_returns_409():
    """Regression: second submit for same (student, course) must return 409,
    not silently record a duplicate that inflates analytics."""
    _reset()
    payload = {"course_id": "bio-101", "overall": 5, "student_id": "stu-dup",
               "class_type": "live"}
    first = client.post("/survey/post-class", json=payload)
    assert first.status_code == 200

    second = client.post("/survey/post-class", json=payload)
    assert second.status_code == 409, (
        "duplicate (student, course) survey submission must be rejected with 409, "
        "not accepted — the survey must show only once per account per course"
    )


def test_duplicate_different_course_allowed():
    """Same student may survey for a different course."""
    _reset()
    client.post("/survey/post-class", json={
        "course_id": "bio-101", "overall": 5, "student_id": "stu-multi",
        "class_type": "live",
    })
    r = client.post("/survey/post-class", json={
        "course_id": "math-201", "overall": 4, "student_id": "stu-multi",
        "class_type": "live",
    })
    assert r.status_code == 200, "different course should be accepted"


def test_duplicate_different_student_allowed():
    """Different students may each survey the same course."""
    _reset()
    client.post("/survey/post-class", json={
        "course_id": "shared-course", "overall": 5, "student_id": "stu-a",
        "class_type": "live",
    })
    r = client.post("/survey/post-class", json={
        "course_id": "shared-course", "overall": 3, "student_id": "stu-b",
        "class_type": "live",
    })
    assert r.status_code == 200


def test_anonymous_submission_not_deduped():
    """Anonymous learners (no student_id) are not subject to per-student dedup —
    they can re-submit.  This is the expected behaviour for guest sessions."""
    _reset()
    for _ in range(3):
        r = client.post("/survey/post-class", json={
            "course_id": "anon-course", "overall": 4, "class_type": "live",
        })
        assert r.status_code == 200


def test_survey_template_still_returned_after_submission():
    """GET /survey/post-class always returns the template when the flag is on.
    The 'already submitted' guard lives on the client (localStorage) and via the
    409 on POST; the GET endpoint does not need to know submission history."""
    _reset()
    client.post("/survey/post-class", json={
        "course_id": "bio-101", "overall": 5, "student_id": "stu-check",
        "class_type": "live",
    })
    body = client.get("/survey/post-class").json()
    assert body["enabled"] is True
    assert body["template"] is not None


def test_summary_not_inflated_by_409_rejections():
    """Analytics summary must reflect only accepted submissions."""
    _reset()
    payload = {"course_id": "stats-301", "overall": 5, "student_id": "stu-inflate",
               "class_type": "live"}
    client.post("/survey/post-class", json=payload)
    client.post("/survey/post-class", json=payload)  # 409, ignored
    summ = client.get("/survey/summary/stats-301").json()
    assert summ["responses"] == 1, (
        "duplicate rejection must not inflate response count"
    )
