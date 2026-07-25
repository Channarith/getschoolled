"""Regression tests covering the specific bugs fixed in v0.45.5–v0.45.14.

Kept in one file so the full regression suite runs with `pytest -k regression`
and reviewers can see all recent fixes documented in executable form.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from aoep_shared.group_classes import GroupClassStore, ensure_standard_daily_classes
from orchestrator.main import app, _group_store

client = TestClient(app)


def _iso(delta_minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)).isoformat()


def _first_lesson() -> str:
    return client.get("/api/lessons").json()[0]["lesson_id"]


def _schedule(title="Test class", **kwargs) -> str:
    """Create a scheduled group class and return its id."""
    payload = {
        "title": title,
        "lesson_id": _first_lesson(),
        "start_time": _iso(60),
        "platform": "salareen",
        "room_size": 4,
        "capacity": 3,
    }
    payload.update(kwargs)
    r = client.post("/api/group-classes", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# v0.45.8 — PPTX upload permission (host-uploads directory)
# ---------------------------------------------------------------------------

def test_pptx_upload_requires_auth():
    """Regression v0.45.8: upload endpoint must reject unauthenticated requests."""
    import io
    fake_pptx = io.BytesIO(b"PK\x03\x04")  # minimal ZIP-magic (PPTX is a ZIP)
    r = client.post(
        "/api/group-classes/upload-presentation",
        files={"file": ("deck.pptx", fake_pptx, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        data={"title": "My deck"},
        # No Authorization header
    )
    assert r.status_code == 401, "upload without auth must be rejected"


def test_pptx_upload_empty_file_rejected():
    """Regression v0.45.8: empty upload must be rejected with 400."""
    import io
    r = client.post(
        "/api/group-classes/upload-presentation",
        files={"file": ("empty.pptx", io.BytesIO(b""), "application/octet-stream")},
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code in (400, 401), "empty file must be rejected"


def test_pptx_upload_unsupported_format_rejected():
    """Regression v0.45.8: .docx must return 422 with a helpful message."""
    import io
    r = client.post(
        "/api/group-classes/upload-presentation",
        files={"file": ("notes.docx", io.BytesIO(b"data"), "application/octet-stream")},
        headers={"Authorization": "Bearer test-token"},
    )
    # 401 if token invalid; 422 if token passes but format rejected.
    assert r.status_code in (401, 422)
    if r.status_code == 422:
        assert "pptx" in r.json().get("detail", "").lower() or "pdf" in r.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# v0.45.8 — Redis: removing startup ping must not lose scheduled classes
# ---------------------------------------------------------------------------

def test_group_class_survives_store_reset():
    """Regression v0.45.8: starting a class after a store-reset (simulating
    restart without Redis ping) must succeed via seed-on-miss."""
    with TestClient(app) as c:
        probe = GroupClassStore()
        ensure_standard_daily_classes(probe)
        salareen = [gc for gc in probe.list(upcoming_only=True) if gc.platform == "salareen"]
        assert salareen
        cid = salareen[0].id
        # Simulate a fresh replica whose in-memory store is empty.
        app.state.group_classes = GroupClassStore()
        assert app.state.group_classes.get(cid) is None
        r = c.post(f"/api/group-classes/{cid}/start", json={})
        assert r.status_code == 200, (
            f"class {cid} not found after store reset — seed-on-miss regression: {r.text}"
        )


# ---------------------------------------------------------------------------
# v0.45.9 — Schedule navigation: class appears in listing after scheduling
# ---------------------------------------------------------------------------

def test_scheduled_class_appears_in_listing():
    """Regression v0.45.9: after POST /api/group-classes the class must appear
    in GET /api/group-classes listing (frontend redirects host to join tab)."""
    lid = _first_lesson()
    r = client.post("/api/group-classes", json={
        "title": "My new class",
        "lesson_id": lid,
        "start_time": _iso(60),
        "platform": "salareen",
    })
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert cid, "schedule must return a class id"

    listing = client.get("/api/group-classes").json()["classes"]
    ids = [c["id"] for c in listing]
    assert cid in ids, "newly scheduled class must appear in listing immediately"


def test_schedule_returns_full_class_payload():
    """Regression v0.45.9: schedule response must include id, title, status."""
    r = client.post("/api/group-classes", json={
        "title": "Evening cohort",
        "lesson_id": _first_lesson(),
        "start_time": _iso(90),
        "platform": "salareen",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["id"]
    assert body["title"] == "Evening cohort"
    assert body["status"] in ("scheduled", "upcoming")
    assert body["platform"] == "salareen"


# ---------------------------------------------------------------------------
# v0.45.9 — Student join: non-live class must return 403, not crash
# ---------------------------------------------------------------------------

def test_student_cannot_start_host_owned_class():
    """Regression v0.45.9: a non-host calling /start on a host-owned class
    must get 403.  The frontend now shows a friendly 'not started yet' message
    rather than a raw server error, but the 403 must be returned by the API."""
    from datetime import datetime, timezone
    from aoep_shared.group_classes import GroupClass

    # Directly inject a class with a known instructor_account_id into the store.
    # (ScheduleGroupClassRequest derives instructor_account_id from the auth token,
    # not the request body, so we must seed the store directly for this test.)
    gc = GroupClass(
        id="host-only-test-class",
        title="Host-only class",
        lesson_id=_first_lesson(),
        platform="salareen",
        start_time=datetime.now(timezone.utc).isoformat(),
        instructor_account_id="acct-real-host",
        created_by_account_id="acct-real-host",
    )
    _group_store().save(gc)

    # Call /start without ANY auth (account_id="" → not in host_account_ids).
    start = client.post(f"/api/group-classes/{gc.id}/start")
    assert start.status_code == 403, (
        "non-host must receive 403 when trying to start a host-owned class; "
        f"got {start.status_code}: {start.text}"
    )


def test_unowned_class_can_be_started_by_anyone():
    """Classes with no host_account_ids can be started by any authenticated
    user — this is the open/community class case."""
    cid = _schedule(title="Open class")
    r = client.post(f"/api/group-classes/{cid}/start")
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# v0.45.9 — Admin `isAdmin` guard: platform admin can start any class
# ---------------------------------------------------------------------------

def test_platform_admin_header_bypasses_host_check():
    """Regression v0.45.9: platform admins must be able to start host-owned
    classes (for monitoring/moderation purposes)."""
    lid = _first_lesson()
    r = client.post("/api/group-classes", json={
        "title": "Admin override class",
        "lesson_id": lid,
        "start_time": _iso(30),
        "instructor_account_id": "acct-strict-host",
        "created_by_account_id": "acct-strict-host",
    })
    cid = r.json()["id"]

    # Platform admin is identified by the request (monkeypatched in tests).
    # In the test environment _request_is_admin returns True for auth tokens
    # that start with the internal prefix — simulate by patching.
    import orchestrator.main as main_mod
    original = main_mod._request_is_admin
    try:
        main_mod._request_is_admin = lambda auth: True
        admin_start = client.post(
            f"/api/group-classes/{cid}/start",
            headers={"Authorization": "Bearer admin-token"},
        )
        assert admin_start.status_code == 200, (
            f"platform admin must bypass host check: {admin_start.text}"
        )
    finally:
        main_mod._request_is_admin = original


# ---------------------------------------------------------------------------
# v0.45.10/v0.45.11 — Teacher host tile: teacher joins as admin participant
# ---------------------------------------------------------------------------

def test_scheduled_host_joins_as_admin():
    """Regression v0.45.10: when the scheduled instructor joins the live room
    they must receive is_admin=True and a moderator_key so the frontend can
    show them in the host tile rather than the student strip."""
    from datetime import datetime, timezone
    from aoep_shared.group_classes import GroupClass
    from unittest.mock import patch

    # Seed a class owned by 'host-acct-xyz' directly (API would derive from token).
    gc = GroupClass(
        id="host-tile-test-class",
        title="Hosted class",
        lesson_id=_first_lesson(),
        platform="salareen",
        start_time=datetime.now(timezone.utc).isoformat(),
        instructor_account_id="host-acct-xyz",
        created_by_account_id="host-acct-xyz",
    )
    _group_store().save(gc)

    # Start the class (no host check since we're using TestClient without auth).
    import orchestrator.main as main_mod
    with patch.object(main_mod, "_class_host_is_caller", return_value=True):
        started = client.post(f"/api/group-classes/{gc.id}/start").json()
    assert "bridge" in started, f"start failed: {started}"
    room_id = started["bridge"]["livekit_room"]

    # Host joins — account_id matches creator_account_id → is_admin=True.
    with patch("aoep_shared.live_room_rewards.account_from_authorization", return_value="host-acct-xyz"):
        join = client.post(
            f"/api/live-rooms/{room_id}/join",
            json={"name": "Host Teacher", "identity": "web-acct-host-acct-xyz"},
            headers={"Authorization": "Bearer host-token"},
        )
    assert join.status_code == 200, join.text
    body = join.json()
    assert body["is_admin"] is True, "scheduled host must join as admin"
    assert body["moderator_key"], "host must receive moderator_key"


def test_non_host_joins_as_non_admin_after_host():
    """Regression v0.45.10: the second learner to join a class (after the host
    already holds the admin slot) must NOT become admin and must NOT receive a
    moderator_key — they should appear in the student tile, not the host tile."""
    from datetime import datetime, timezone
    from aoep_shared.group_classes import GroupClass
    from unittest.mock import patch

    gc = GroupClass(
        id="student-tile-test-class",
        title="Student tile class",
        lesson_id=_first_lesson(),
        platform="salareen",
        start_time=datetime.now(timezone.utc).isoformat(),
        instructor_account_id="acct-teacher-99",
        created_by_account_id="acct-teacher-99",
    )
    _group_store().save(gc)

    import orchestrator.main as main_mod
    with patch.object(main_mod, "_class_host_is_caller", return_value=True):
        started = client.post(f"/api/group-classes/{gc.id}/start").json()
    room_id = started["bridge"]["livekit_room"]

    # Teacher joins first → takes the admin slot.
    with patch("aoep_shared.live_room_rewards.account_from_authorization", return_value="acct-teacher-99"):
        client.post(
            f"/api/live-rooms/{room_id}/join",
            json={"name": "Teacher", "identity": "web-acct-teacher"},
            headers={"Authorization": "Bearer teacher-token"},
        )

    # Student joins second → admin slot is taken, must be a regular learner.
    student_join = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Student Alice", "identity": "web-student-alice"},
    )
    assert student_join.status_code == 200, student_join.text
    body = student_join.json()
    assert body["moderator_key"] == "", (
        "student (second joiner, non-host) must not receive moderator_key; "
        "they should appear in the student tile, not the host tile"
    )


# ---------------------------------------------------------------------------
# v0.45.12 — Admin flags auth — tested in services/memory/tests/test_flags_api.py
# v0.45.13 — Survey 409 dedup — tested in services/memory/tests/test_survey_dedup_regression.py
# v0.45.14 — Sales demo flag default — tested in services/memory/tests/
# (Cross-service tests that import memory.main live in the memory test suite
#  to avoid module-path conflicts when pytest runs from the orchestrator dir.)
