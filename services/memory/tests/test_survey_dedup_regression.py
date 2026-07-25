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


# ---------------------------------------------------------------------------
# v0.45.12 — Admin flags: X-Admin-Secret auth enforced
# ---------------------------------------------------------------------------

def test_admin_flags_wrong_secret_rejected():
    """Regression v0.45.12: incorrect X-Admin-Secret must return 401."""
    r = client.get("/admin/flags", headers={"X-Admin-Secret": "wrong-secret"})
    assert r.status_code == 401, (
        "incorrect admin secret must be rejected with 401 — "
        "any non-empty string must NOT bypass the gate"
    )


def test_admin_flags_correct_secret_accepted():
    """Regression v0.45.12: correct X-Admin-Secret returns the flag catalog."""
    r = client.get("/admin/flags", headers={"X-Admin-Secret": "dev-admin-secret"})
    assert r.status_code == 200
    assert "flags" in r.json()


def test_admin_flags_no_secret_returns_401():
    """Regression v0.45.12: missing X-Admin-Secret header must return 401."""
    r = client.get("/admin/flags")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# v0.45.14 — Sales demo flag default false + featured_courses is JSON
# ---------------------------------------------------------------------------

def test_sales_demo_enabled_default_false():
    """Regression v0.45.14: sales_demo.enabled must default to False so the
    floating Sales Demo button is hidden for all users unless explicitly enabled."""
    from aoep_shared.flags import FlagStore
    app.state.flags = FlagStore()  # fresh store — nothing set
    r = client.get("/flags/evaluate")
    if r.status_code == 200:
        val = r.json().get("flags", {}).get("sales_demo.enabled", {})
        if isinstance(val, dict):
            assert val.get("enabled", False) is False, (
                "sales_demo.enabled must default to False"
            )


def test_sales_demo_featured_courses_is_json_list():
    """Regression v0.45.16: sales_demo.featured_courses is now a JSON array
    of course IDs, not a bool — the 5 built-in compliance courses are the default."""
    from aoep_shared.flags import FlagStore, FLAG_CATALOG, FlagType
    spec = next((f for f in FLAG_CATALOG if f.key == "sales_demo.featured_courses"), None)
    assert spec is not None, "sales_demo.featured_courses must be in FLAG_CATALOG"
    assert spec.type == FlagType.JSON, (
        "sales_demo.featured_courses must be FlagType.JSON, not BOOL — "
        "it stores a list of course IDs that admins can edit via the course picker"
    )
    assert isinstance(spec.default, list) and len(spec.default) == 5, (
        "default must be a list of the 5 built-in compliance course IDs"
    )
