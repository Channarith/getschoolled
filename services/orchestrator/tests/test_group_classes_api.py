"""Scheduled group-class endpoints (/api/group-classes)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from aoep_shared.group_classes import GroupClassStore, ensure_standard_daily_classes
from orchestrator.main import app

client = TestClient(app)


def test_start_group_class_seeds_on_miss():
    """Regression: starting a standard class whose id isn't yet in this worker's
    store (multi-replica / post-restart) must seed-on-miss and succeed, not 404.
    """
    with TestClient(app) as c:
        # A deterministic standard-class id, as another replica's /list produced.
        probe = GroupClassStore()
        ensure_standard_daily_classes(probe)
        salareen = [gc for gc in probe.list(upcoming_only=True) if gc.platform == "salareen"]
        assert salareen, "expected seeded salareen classes"
        cid = salareen[0].id
        # Simulate a replica that has not materialized this class yet.
        app.state.group_classes = GroupClassStore()
        assert app.state.group_classes.get(cid) is None
        r = c.post(f"/api/group-classes/{cid}/start", json={})
        assert r.status_code == 200, r.text
        assert r.json()["class"]["id"] == cid


def _iso(delta_minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)).isoformat()


def _first_lesson() -> str:
    return client.get("/api/lessons").json()[0]["lesson_id"]


def test_schedule_list_register_flow():
    lid = _first_lesson()
    created = client.post(
        "/api/group-classes",
        json={"title": "Evening cohort", "lesson_id": lid, "start_time": _iso(60),
              "capacity": 3},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["id"]
    assert created.json()["seats_left"] == 3
    assert created.json()["platform"] == "salareen"

    listing = client.get("/api/group-classes").json()["classes"]
    assert any(c["id"] == cid for c in listing)

    reg = client.post(f"/api/group-classes/{cid}/register",
                      json={"name": "Ada", "email": "ada@example.com"})
    assert reg.status_code == 200, reg.text
    assert reg.json()["seats_left"] == 2
    assert reg.json()["registered"] == 1


def test_schedule_zoom_requires_meeting_url():
    lid = _first_lesson()
    bad = client.post("/api/group-classes", json={
        "title": "Zoom class", "lesson_id": lid, "platform": "zoom",
        "start_time": _iso(30)})
    assert bad.status_code == 400

    ok = client.post("/api/group-classes", json={
        "title": "Zoom class", "lesson_id": lid, "platform": "zoom",
        "meeting_url": "https://zoom.us/j/123456789", "start_time": _iso(30)})
    assert ok.status_code == 200, ok.text
    assert ok.json()["needs_bridge"] is True


def test_register_full_class_returns_409():
    lid = _first_lesson()
    cid = client.post("/api/group-classes", json={
        "title": "Tiny", "lesson_id": lid, "start_time": _iso(30), "capacity": 1,
    }).json()["id"]
    client.post(f"/api/group-classes/{cid}/register", json={"name": "Ada"})
    full = client.post(f"/api/group-classes/{cid}/register", json={"name": "Grace"})
    assert full.status_code == 409


def test_start_salareen_class_returns_session_and_plan():
    lid = _first_lesson()
    cid = client.post("/api/group-classes", json={
        "title": "Go live", "lesson_id": lid, "start_time": _iso(5),
    }).json()["id"]

    started = client.post(f"/api/group-classes/{cid}/start")
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["class"]["status"] == "live"
    assert body["session"]["session"]["session_id"]
    assert body["bridge"]["needs_bridge"] is False
    assert body["bridge"]["livekit"]["room"].startswith("class-")


def test_start_group_class_accepts_legacy_short_id():
    lid = _first_lesson()
    cid = client.post("/api/group-classes", json={
        "title": "Legacy short start", "lesson_id": lid, "start_time": _iso(5),
    }).json()["id"]

    started = client.post(f"/api/group-classes/{cid[:8]}/start")
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["class"]["id"] == cid
    assert body["bridge"]["livekit"]["room"] == f"class-{cid}"


def test_start_external_class_returns_bridge_plan():
    lid = _first_lesson()
    cid = client.post("/api/group-classes", json={
        "title": "Teams live", "lesson_id": lid, "platform": "meet",
        "meeting_url": "https://meet.google.com/abc-defg-hij", "start_time": _iso(5),
    }).json()["id"]

    body = client.post(f"/api/group-classes/{cid}/start").json()
    assert body["bridge"]["needs_bridge"] is True
    assert body["bridge"]["platform"] == "meet"
    assert body["bridge"]["meeting_ref"] == "https://meet.google.com/abc-defg-hij"
    assert body["bridge"]["connect_endpoint"] == "/bridges/meet/connect"


def test_unknown_class_404():
    assert client.get("/api/group-classes/nope").status_code == 404
    assert client.post("/api/group-classes/nope/start").status_code == 404
    assert client.post("/api/group-classes/nope/register",
                       json={"name": "Ada"}).status_code == 404
