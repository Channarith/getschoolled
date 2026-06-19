"""Post-class survey endpoints (flag-gated template, submit, admin insights)."""

from aoep_shared.flags import FlagStore
from aoep_shared.survey import SurveyStore
from fastapi.testclient import TestClient
from memory.main import app

client = TestClient(app)

ADMIN = {"X-Admin-Secret": "dev-admin-secret"}


def _reset():
    app.state.flags = FlagStore()
    app.state.surveys = SurveyStore()


def test_template_hidden_until_flag_enabled():
    _reset()
    body = client.get("/survey/post-class").json()
    assert body["enabled"] is False and body["template"] is None
    # Admin turns the flag on.
    client.put("/admin/flags/engagement.post_class_survey",
               json={"enabled": True, "value": True}, headers=ADMIN)
    body = client.get("/survey/post-class").json()
    assert body["enabled"] is True
    assert any(q["id"] == "overall" for q in body["template"]["questions"])


def test_submit_and_course_summary():
    _reset()
    for o in (5, 4, 2):
        r = client.post("/survey/post-class", json={
            "course_id": "bio", "overall": o, "class_type": "live",
            "would_recommend": o >= 4, "suggestion": "more examples"})
        assert r.json()["recorded"] is True
    summ = client.get("/survey/summary/bio").json()
    assert summ["responses"] == 3
    assert summ["avg_overall"] == round((5 + 4 + 2) / 3, 2)
    assert any(t["term"] == "examples" for t in summ["top_suggestions"])


def test_submit_rejects_bad_rating():
    _reset()
    r = client.post("/survey/post-class", json={"course_id": "x", "overall": 9})
    assert r.status_code == 422


def test_insights_requires_admin_and_is_multidimensional():
    _reset()
    assert client.get("/admin/survey/insights").status_code == 401
    client.post("/survey/post-class", json={"course_id": "bio", "overall": 5, "class_type": "live"})
    client.post("/survey/post-class", json={"course_id": "math", "overall": 3, "class_type": "self_paced"})
    body = client.get("/admin/survey/insights", headers=ADMIN).json()
    assert body["datamart"]["total_responses"] == 2
    assert "bio" in body["datamart"]["dimensions"]["course"]
    assert "data_mining_enabled" in body
