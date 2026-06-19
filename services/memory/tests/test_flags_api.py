"""Admin feature-flag endpoints (secret-gated writes, public reads)."""

from aoep_shared.flags import FlagStore
from fastapi.testclient import TestClient
from memory.main import app

client = TestClient(app)

ADMIN = {"X-Admin-Secret": "dev-admin-secret"}  # matches default in main


def _reset_store():
    app.state.flags = FlagStore()


def test_public_evaluate_excludes_admin_flags():
    _reset_store()
    body = client.get("/flags/evaluate", params={"tier": "free"}).json()
    assert "engagement.post_class_survey" in body["flags"]
    assert "ops.maintenance_mode" not in body["flags"]  # admin_only hidden


def test_get_single_flag_default():
    _reset_store()
    body = client.get("/flags/engagement.post_class_survey").json()
    assert body["value"] is False
    assert body["spec"]["category"] == "engagement"


def test_unknown_flag_404():
    _reset_store()
    assert client.get("/flags/nope.nope").status_code == 404


def test_admin_write_requires_secret():
    _reset_store()
    # No secret -> 401.
    r = client.put("/admin/flags/engagement.post_class_survey", json={"enabled": True, "value": True})
    assert r.status_code == 401
    # Wrong secret -> 401.
    r = client.put("/admin/flags/engagement.post_class_survey",
                   json={"enabled": True, "value": True}, headers={"X-Admin-Secret": "nope"})
    assert r.status_code == 401


def test_admin_can_toggle_flag():
    _reset_store()
    r = client.put("/admin/flags/engagement.post_class_survey",
                   json={"enabled": True, "value": True}, headers=ADMIN)
    assert r.status_code == 200
    assert client.get("/flags/engagement.post_class_survey").json()["value"] is True


def test_admin_list_includes_hidden_flags():
    _reset_store()
    r = client.get("/admin/flags", headers=ADMIN)
    keys = {f["key"] for f in r.json()["flags"]}
    assert "ops.maintenance_mode" in keys


def test_tier_targeting_via_api():
    _reset_store()
    client.put("/admin/flags/monetization.dynamic_pricing",
               json={"enabled": True, "value": True, "tiers": ["pro"]}, headers=ADMIN)
    assert client.get("/flags/monetization.dynamic_pricing", params={"tier": "pro"}).json()["value"] is True
    assert client.get("/flags/monetization.dynamic_pricing", params={"tier": "free"}).json()["value"] is False


def test_per_subject_override_via_api():
    _reset_store()
    client.put("/admin/flags/engagement.post_class_survey", json={"enabled": False}, headers=ADMIN)
    client.post("/admin/flags/engagement.post_class_survey/override",
                json={"subject": "vip", "value": True}, headers=ADMIN)
    assert client.get("/flags/engagement.post_class_survey", params={"subject": "vip"}).json()["value"] is True
    assert client.get("/flags/engagement.post_class_survey", params={"subject": "joe"}).json()["value"] is False


def test_invalid_multivariate_value_422():
    _reset_store()
    r = client.put("/admin/flags/access.user_levels",
                   json={"value": "superuser"}, headers=ADMIN)
    assert r.status_code == 422


def test_reset_clears_state():
    _reset_store()
    client.put("/admin/flags/engagement.post_class_survey",
               json={"enabled": True, "value": True}, headers=ADMIN)
    client.post("/admin/flags/engagement.post_class_survey/reset", headers=ADMIN)
    assert client.get("/flags/engagement.post_class_survey").json()["value"] is False
