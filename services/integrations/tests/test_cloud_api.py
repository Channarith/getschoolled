"""Cloud/collab gateway endpoints (Phase 19)."""

import time

from fastapi.testclient import TestClient

from integrations.main import app

client = TestClient(app)


def test_notify_endpoint():
    out = client.post("/notify", json={"channel": "#class", "text": "Starting now"}).json()
    assert out["ok"] is True and out["channel"] == "#class"


def test_calendar_schedule_endpoint():
    out = client.post("/calendar/schedule", json={
        "title": "Algebra", "start": "2026-07-01T15:00:00+00:00", "duration_min": 60,
        "attendees": ["a@x.com"],
    }).json()
    assert out["id"].startswith("evt-")
    assert out["end"].startswith("2026-07-01T16:00")


def test_sso_oidc_valid_and_invalid():
    ok = client.post("/sso/oidc", json={
        "claims": {"iss": "https://idp", "aud": "aoep", "sub": "u1", "exp": time.time() + 600},
        "audience": "aoep",
    }).json()
    assert ok["subject"] == "u1"

    bad = client.post("/sso/oidc", json={
        "claims": {"iss": "https://idp", "aud": "wrong", "sub": "u1"}, "audience": "aoep"})
    assert bad.status_code == 401
