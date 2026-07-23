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


def test_paid_enrollment_checkout_confirm_and_register(monkeypatch):
    monkeypatch.setattr(
        "aoep_shared.live_room_rewards.account_from_authorization",
        lambda auth: "student-ada" if auth == "Bearer ada-token" else "",
    )
    lid = _first_lesson()
    created = client.post("/api/group-classes", json={
        "title": "Instructor paid class",
        "lesson_id": lid,
        "start_time": _iso(20),
        "platform": "salareen",
        "room_size": 9,
        "capacity": 8,
        "payment_required": True,
        "attendee_code_required": True,
        "price_per_user_usd": 25.0,
        "commission_rate": 0.15,
    })
    assert created.status_code == 200, created.text
    cid = created.json()["id"]

    checkout = client.post(f"/api/group-classes/{cid}/checkout", json={
        "name": "Ada",
        "email": "ada@example.com",
    })
    assert checkout.status_code == 200, checkout.text
    session_id = checkout.json()["checkout"]["session_id"]
    assert session_id

    confirm = client.post(
        f"/api/group-classes/{cid}/confirm-payment",
        json={"checkout_session_id": session_id},
        headers={"authorization": "Bearer ada-token"},
    )
    assert confirm.status_code == 200, confirm.text
    code = confirm.json()["attendee_code"]
    assert code

    reg = client.post(f"/api/group-classes/{cid}/register", json={
        "name": "Ada",
        "email": "ada@example.com",
        "attendee_code": code,
        "checkout_session_id": session_id,
        "payment_status": "paid",
    })
    assert reg.status_code == 200, reg.text
    assert reg.json()["registered"] == 1
    assert reg.json()["payment_required"] is True


def test_group_class_review_updates_instructor_stats():
    lid = _first_lesson()
    created = client.post("/api/group-classes", json={
        "title": "Rated class",
        "lesson_id": lid,
        "start_time": _iso(30),
        "instructor_name": "Coach Kim",
        "instructor_account_id": "inst-1",
    })
    assert created.status_code == 200, created.text
    cid = created.json()["id"]

    review = client.post(f"/api/group-classes/{cid}/review", json={"rating": 5, "comment": "Excellent"})
    assert review.status_code == 200, review.text
    body = review.json()
    assert body["review"]["rating"] == 5
    assert body["class"]["review_count"] == 1
    assert body["class"]["review_avg"] == 5.0


def test_teams_class_camera_sources_are_exposed_in_bridge_plan():
    lid = _first_lesson()
    created = client.post("/api/group-classes", json={
        "title": "Cisco room class",
        "lesson_id": lid,
        "platform": "teams",
        "meeting_url": "https://teams.microsoft.com/l/meetup-join/19%3ameeting_x%40thread.v2/0",
        "start_time": _iso(25),
        "device_profile": "teams_cisco_room",
        "camera_ingest_mode": "external_preferred",
        "camera_sources": [
            {
                "source_id": "cam-room-front",
                "label": "Cisco front cam",
                "device_type": "cisco_roomkit",
                "source_kind": "camera",
            }
        ],
    })
    assert created.status_code == 200, created.text
    cid = created.json()["id"]
    started = client.post(f"/api/group-classes/{cid}/start", json={})
    assert started.status_code == 200, started.text
    plan = started.json()["bridge"]
    assert plan["platform"] == "teams"
    assert plan["supports_external_camera_ingest"] is True
    assert plan["camera_source_count"] == 1
    assert plan["camera_sources"][0]["source_id"] == "cam-room-front"


def test_upload_presentation_requires_auth():
    r = client.post(
        "/api/group-classes/upload-presentation",
        files={"file": ("deck.pdf", b"%PDF", "application/pdf")},
    )
    assert r.status_code == 401


def test_upload_presentation_imports_pdf(monkeypatch):
    import pytest

    fpdf = pytest.importorskip("fpdf")
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(190, 8, "Fractions are parts of a whole.")
    data = bytes(pdf.output())

    monkeypatch.setattr(
        "aoep_shared.live_room_rewards.account_from_authorization",
        lambda auth: "host-upload" if auth == "Bearer host-token" else "",
    )
    r = client.post(
        "/api/group-classes/upload-presentation",
        files={"file": ("math.pdf", data, "application/pdf")},
        data={"title": "Host math deck", "language": "en"},
        headers={"authorization": "Bearer host-token"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lesson_id"].startswith("host-")
    assert body["slide_count"] >= 1
    assert body["presentation_filename"] == "math.pdf"


def test_host_owned_class_start_requires_host(monkeypatch):
    lid = _first_lesson()
    monkeypatch.setattr(
        "aoep_shared.live_room_rewards.account_from_authorization",
        lambda auth: "host-a" if auth == "Bearer host-token" else "",
    )
    created = client.post(
        "/api/group-classes",
        json={"title": "Host class", "lesson_id": lid, "start_time": _iso(30)},
        headers={"authorization": "Bearer host-token"},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["id"]
    assert created.json()["instructor_account_id"] == "host-a"

    denied = client.post(f"/api/group-classes/{cid}/start", json={})
    assert denied.status_code == 403

    allowed = client.post(
        f"/api/group-classes/{cid}/start",
        json={},
        headers={"authorization": "Bearer host-token"},
    )
    assert allowed.status_code == 200, allowed.text
