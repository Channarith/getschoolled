"""Automation test hooks: /admin/test/reset + /admin/test/seed (double-gated)."""

from aoep_shared.flags import FlagStore
from aoep_shared.survey import SurveyStore
from fastapi.testclient import TestClient
from memory.main import app

client = TestClient(app)
ADMIN = {"X-Admin-Secret": "dev-admin-secret"}


def _fresh():
    app.state.flags = FlagStore()
    app.state.surveys = SurveyStore()


def test_reset_requires_admin():
    _fresh()
    assert client.post("/admin/test/reset").status_code == 401


def test_seed_then_reset_roundtrip():
    _fresh()
    # Seed a flag + two survey responses deterministically.
    r = client.post("/admin/test/seed", headers=ADMIN, json={
        "flags": {"engagement.post_class_survey": {"enabled": True, "value": True}},
        "surveys": [
            {"course_id": "bio", "overall": 5, "class_type": "live"},
            {"course_id": "bio", "overall": 3, "class_type": "live", "suggestion": "slower please"},
        ],
    })
    assert r.json()["seeded"] == {"flags": 1, "surveys": 2}
    # Flag is on, survey data is present.
    assert client.get("/survey/post-class").json()["enabled"] is True
    assert client.get("/survey/summary/bio").json()["responses"] == 2
    # Reset wipes it back to baseline.
    assert "surveys" in client.post("/admin/test/reset", headers=ADMIN).json()["reset"]
    assert client.get("/survey/summary/bio").json()["responses"] == 0
    assert client.get("/survey/post-class").json()["enabled"] is False


def test_reset_scope_targets_one_store():
    _fresh()
    client.post("/admin/test/seed", headers=ADMIN, json={
        "surveys": [{"course_id": "x", "overall": 4}]})
    client.put("/admin/flags/ux.dark_mode", json={"enabled": False, "value": False}, headers=ADMIN)
    # Reset only surveys; the flag override must survive.
    body = client.post("/admin/test/reset", params={"scope": "surveys"}, headers=ADMIN).json()
    assert body["reset"] == ["surveys"]
    assert client.get("/survey/summary/x").json()["responses"] == 0
    assert client.get("/flags/ux.dark_mode").json()["value"] is False


def test_seed_invalid_survey_422():
    _fresh()
    r = client.post("/admin/test/seed", headers=ADMIN, json={
        "surveys": [{"course_id": "x", "overall": 99}]})
    assert r.status_code == 422


def test_disabled_in_cloud_mode(monkeypatch):
    _fresh()
    monkeypatch.setenv("ENABLE_TEST_ENDPOINTS", "false")
    assert client.post("/admin/test/reset", headers=ADMIN).status_code == 403
