"""Live room HTTP endpoints (/api/live-rooms)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def _iso(delta_minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)).isoformat()


def _first_lesson() -> str:
    return client.get("/api/lessons").json()[0]["lesson_id"]


def _start_salareen_class(room_size: int = 6) -> dict:
    lid = _first_lesson()
    cid = client.post(
        "/api/group-classes",
        json={
            "title": "Salareen live",
            "lesson_id": lid,
            "start_time": _iso(5),
            "platform": "salareen",
            "room_size": room_size,
            "capacity": room_size - 1,
        },
    ).json()["id"]
    started = client.post(f"/api/group-classes/{cid}/start").json()
    room_id = started["bridge"]["livekit_room"]
    return {"class_id": cid, "room_id": room_id, "started": started}


def test_start_salareen_opens_live_room():
    info = _start_salareen_class(6)
    room = client.get(f"/api/live-rooms/{info['room_id']}")
    assert room.status_code == 200, room.text
    body = room.json()
    assert body["room_size"] == 6
    assert body["host"]["name"].startswith("Theodore")
    assert body["slide"]["title"]


def _schedule_salareen_class(room_size: int = 6) -> str:
    """Schedule a Salareen class WITHOUT starting it (no live room yet)."""
    return client.post(
        "/api/group-classes",
        json={
            "title": "Unstarted Salareen",
            "lesson_id": _first_lesson(),
            "start_time": _iso(5),
            "platform": "salareen",
            "room_size": room_size,
            "capacity": room_size - 1,
        },
    ).json()["id"]


def test_get_room_lazy_opens_for_unstarted_class():
    # Selecting a scheduled-but-not-started Salareen class used to 404.
    cid = _schedule_salareen_class(6)
    room = client.get(f"/api/live-rooms/class-{cid}")
    assert room.status_code == 200, room.text
    body = room.json()
    assert body["room_size"] == 6
    assert body["slide"]["title"]  # session was started on demand


def test_join_lazy_opens_and_issues_livekit_token():
    cid = _schedule_salareen_class(4)
    joined = client.post(
        f"/api/live-rooms/class-{cid}/join",
        json={"name": "Ada", "identity": "ada-web"},
    )
    assert joined.status_code == 200, joined.text
    body = joined.json()
    # Real videochat: a LiveKit join token + url are issued for the participant.
    assert body["media"]["token"].count(".") == 2  # JWT header.payload.signature
    assert body["media"]["room"] == f"class-{cid}"
    assert body["media"]["url"]


def test_join_lazy_opens_legacy_short_class_room_id():
    cid = _schedule_salareen_class(6)
    legacy_room_id = f"class-{cid[:8]}"
    joined = client.post(
        f"/api/live-rooms/{legacy_room_id}/join",
        json={"name": "Ada", "identity": "ada-mobile"},
    )
    assert joined.status_code == 200, joined.text
    body = joined.json()
    assert body["room"]["class_id"] == cid
    assert body["room"]["room_id"] == legacy_room_id
    assert body["media"]["room"] == legacy_room_id

    full_id_join = client.post(
        f"/api/live-rooms/class-{cid}/join",
        json={"name": "Grace", "identity": "grace-mobile"},
    )
    assert full_id_join.status_code == 200, full_id_join.text
    assert full_id_join.json()["media"]["room"] == legacy_room_id


def test_unknown_room_still_404s():
    r = client.get("/api/live-rooms/class-does-not-exist")
    assert r.status_code == 404
    r2 = client.get("/api/live-rooms/random-room-xyz")
    assert r2.status_code == 404


def _standard_salareen_class_id() -> str:
    """A deterministic-id standard Salareen class (seeded on list)."""
    classes = client.get("/api/group-classes?upcoming=true").json()["classes"]
    salareen = [c for c in classes if c["platform"] == "salareen"]
    assert salareen, "expected seeded standard Salareen classes"
    return salareen[0]["id"]


def _wipe_group_class_store() -> None:
    from orchestrator.main import app as _app

    backend = _app.state.group_classes._backend
    for cid in list(backend.list_ids()):
        backend.delete(cid)


def test_join_lazy_opens_after_class_evicted_from_store():
    # A fresh replica / post-restart / evicted-entry store no longer holds the
    # standard class the client is joining. Because standard-class ids are
    # deterministic, lazy-open must SEED-ON-MISS and reopen the room instead of
    # 404ing (the recurring "Still with 404 errors" report).
    cid = _standard_salareen_class_id()
    _wipe_group_class_store()

    got = client.get(f"/api/live-rooms/class-{cid}")
    assert got.status_code == 200, got.text

    _wipe_group_class_store()
    joined = client.post(
        f"/api/live-rooms/class-{cid}/join",
        json={"name": "Krisna", "identity": "mobile-krisna"},
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["media"]["token"].count(".") == 2  # real LiveKit JWT


def test_join_chat_and_queue_flow():
    info = _start_salareen_class(4)
    joined = client.post(
        f"/api/live-rooms/{info['room_id']}/join",
        json={"name": "Ada", "identity": "ada-web"},
    )
    assert joined.status_code == 200, joined.text
    pid = joined.json()["participant"]["id"]
    assert joined.json()["media"]["token"]

    hand = client.post(
        f"/api/live-rooms/{info['room_id']}/queue/join",
        json={"participant_id": pid, "question": "Can you explain?"},
    )
    assert hand.status_code == 200, hand.text
    assert hand.json()["entry"]["position"] == 1

    mod = info["started"]["bridge"]["moderator_key"]
    called = client.post(
        f"/api/live-rooms/{info['room_id']}/queue/call-next",
        json={"moderator_key": mod},
    )
    assert called.status_code == 200, called.text
    assert called.json()["speaker"]["id"] == pid


def test_join_full_room_returns_409():
    info = _start_salareen_class(4)
    room_id = info["room_id"]
    for i in range(3):
        res = client.post(
            f"/api/live-rooms/{room_id}/join",
            json={"name": f"Learner {i}", "identity": f"id-{i}"},
        )
        assert res.status_code == 200, res.text
    full = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "One too many", "identity": "overflow"},
    )
    assert full.status_code == 409


def test_ask_queues_when_someone_else_speaking():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    a = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Ada", "identity": "a1"},
    ).json()["participant"]["id"]
    b = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Grace", "identity": "b1"},
    ).json()["participant"]["id"]
    client.post(f"/api/live-rooms/{room_id}/queue/join", json={"participant_id": a, "question": "Q1"})
    client.post(f"/api/live-rooms/{room_id}/queue/call-next", json={"moderator_key": mod})
    queued = client.post(
        f"/api/live-rooms/{room_id}/ask",
        json={"participant_id": b, "question": "My turn?"},
    )
    assert queued.status_code == 200, queued.text
    assert queued.json()["queued"] is True
    assert queued.json()["queue_position"] == 1


def test_call_on_specific_participant_holds_the_mutex():
    # Host/AI can pick a SPECIFIC learner (not just FIFO), and only one person
    # holds the floor at a time (single-speaker mutex).
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    a = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Ada", "identity": "a1"}).json()["participant"]["id"]
    b = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Bob", "identity": "b1"}).json()["participant"]["id"]

    # Call on B directly (no queue needed) — B gets the floor.
    r1 = client.post(f"/api/live-rooms/{room_id}/queue/call-on", json={"participant_id": b, "moderator_key": mod})
    assert r1.status_code == 200, r1.text
    room = r1.json()["room"]
    assert room["floor_participant_id"] == b
    # Exactly one floor holder.
    assert r1.json()["speaker"]["id"] == b

    # Call on A while B is speaking — preempts B, A now holds the floor (mutex).
    r2 = client.post(f"/api/live-rooms/{room_id}/queue/call-on", json={"participant_id": a, "moderator_key": mod})
    assert r2.status_code == 200, r2.text
    assert r2.json()["room"]["floor_participant_id"] == a


def test_media_token_reflects_publish_right():
    # Hard mutex: a learner joins WITHOUT publish rights; a fresh media token
    # only permits publishing once they hold the floor.
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    pid = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Ada", "identity": "a1"}).json()["participant"]["id"]

    before = client.post(f"/api/live-rooms/{room_id}/media-token", json={"participant_id": pid})
    assert before.status_code == 200, before.text
    assert before.json()["can_publish"] is False  # can't talk until called on

    client.post(f"/api/live-rooms/{room_id}/queue/call-on", json={"participant_id": pid, "moderator_key": mod})
    after = client.post(f"/api/live-rooms/{room_id}/media-token", json={"participant_id": pid})
    assert after.json()["can_publish"] is True     # floor holder may publish
    assert after.json()["media"]["token"].count(".") == 2


def test_advance_auto_calls_next_raised_hand():
    # AI auto-Q&A: advancing a slide with a waiting hand and no current speaker
    # gives the floor to the next learner.
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    pid = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Ada", "identity": "a1"}).json()["participant"]["id"]
    client.post(f"/api/live-rooms/{room_id}/queue/join", json={"participant_id": pid, "question": "Why?"})

    adv = client.post(f"/api/live-rooms/{room_id}/advance", json={"moderator_key": mod})
    assert adv.status_code == 200, adv.text
    assert adv.json()["auto_called_on"] and adv.json()["auto_called_on"]["id"] == pid
    assert adv.json()["room"]["floor_participant_id"] == pid


def test_first_joiner_is_admin_and_gets_moderator_key():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    first = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Ada", "identity": "a1"}).json()
    second = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Bob", "identity": "b1"}).json()
    assert first["is_admin"] is True and first["moderator_key"]      # admin gets the key
    assert first["participant"]["is_admin"] is True
    assert second["is_admin"] is False and second["moderator_key"] == ""


def test_advance_and_start_require_admin():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    first = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Ada", "identity": "a1"}).json()
    admin_id = first["participant"]["id"]
    second_id = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Bob", "identity": "b1"}).json()["participant"]["id"]

    # non-admin cannot start or advance (LiveRoomError -> 400)
    assert client.post(f"/api/live-rooms/{room_id}/start-presentation", json={"participant_id": second_id}).status_code == 400
    assert client.post(f"/api/live-rooms/{room_id}/advance", json={"participant_id": second_id}).status_code == 400
    # admin can
    started = client.post(f"/api/live-rooms/{room_id}/start-presentation", json={"participant_id": admin_id})
    assert started.status_code == 200 and started.json()["presenting"] is True


def test_tick_auto_starts_when_full_then_auto_advances():
    from orchestrator.main import app as _app

    info = _start_salareen_class(4)  # room_size 4 -> 3 learner seats
    room_id = info["room_id"]
    for i in range(3):  # fill every seat
        client.post(f"/api/live-rooms/{room_id}/join", json={"name": f"L{i}", "identity": f"id-{i}"})
    room = _app.state.live_rooms.require(room_id)
    assert "artificial-intelligence" in room.welcome_message
    assert client.post(f"/api/live-rooms/{room_id}/tick").json()["auto_started"] is False
    room.welcome_started_at = "2000-01-01T00:00:00+00:00"
    _app.state.live_rooms._backend.save(room)

    # Full room starts only after Theodore's transparent-AI welcome.
    t1 = client.post(f"/api/live-rooms/{room_id}/tick")
    assert t1.status_code == 200, t1.text
    assert t1.json()["auto_started"] is True
    assert t1.json()["room"]["presenting"] is True

    # Force the slide dwell into the past -> next tick auto-advances.
    room = _app.state.live_rooms.require(room_id)
    room.slide_started_at = "2000-01-01T00:00:00+00:00"
    _app.state.live_rooms._backend.save(room)
    t2 = client.post(f"/api/live-rooms/{room_id}/tick")
    assert t2.json()["auto_advanced"] is not None


def test_advance_and_ask_in_room():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    pid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Student", "identity": "student-1"},
    ).json()["participant"]["id"]

    advanced = client.post(f"/api/live-rooms/{room_id}/advance", json={"moderator_key": mod})
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["slide"]["title"]

    asked = client.post(
        f"/api/live-rooms/{room_id}/ask",
        json={"participant_id": pid, "question": "What is this lesson about?"},
    )
    assert asked.status_code == 200, asked.text
    assert asked.json()["queued"] is False
    assert asked.json()["answer"]["text"]
    assert asked.json()["host_message"]["from_name"].startswith("Theodore")


def test_join_stores_learner_language_and_ask_defaults_to_it():
    info = _start_salareen_class(4)
    room_id = info["room_id"]
    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Ana", "identity": "ana-es", "language": "es-419"},
    )
    assert joined.status_code == 200, joined.text
    pid = joined.json()["participant"]["id"]
    # The learner's language is normalized and stored so the AI knows it.
    assert joined.json()["participant"]["language"] == "es"

    # Asking WITHOUT a language falls back to the learner's stored language.
    asked = client.post(
        f"/api/live-rooms/{room_id}/ask",
        json={"participant_id": pid, "question": "What is this about?"},
    )
    assert asked.status_code == 200, asked.text
    assert asked.json()["answer"]["text"]


def test_start_solo_room_is_two_seat_and_uses_room_ui():
    # Solo 1:1 reuses the group classroom, just sized for the AI host + one
    # learner (room_size 2 -> exactly one learner seat).
    lid = _first_lesson()
    res = client.post("/api/live-rooms/solo", json={"lesson_id": lid})
    assert res.status_code == 200, res.text
    body = res.json()
    room_id = body["room_id"]
    assert room_id.startswith("solo-")
    assert body["room"]["room_size"] == 2
    assert body["room"]["learner_capacity"] == 1
    assert body["room"]["host"]["name"].startswith("Theodore")
    assert body["room"]["slide"]["title"]  # backed by a real teaching session

    # The same live-room GET/join endpoints serve it.
    got = client.get(f"/api/live-rooms/{room_id}")
    assert got.status_code == 200, got.text
    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Ada", "identity": "ada-solo"},
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["media"]["token"].count(".") == 2  # real LiveKit JWT
    assert joined.json()["is_admin"] is True  # the sole learner is the admin


def test_solo_room_uses_profile_duration_and_stable_student_id():
    from orchestrator.main import get_sessions

    lid = _first_lesson()
    res = client.post("/api/live-rooms/solo", json={
        "lesson_id": lid,
        "student_id": "person-a",
        "profile_score": "15115510",
    })
    assert res.status_code == 200, res.text
    session_id = res.json()["room"]["session_id"]
    session = get_sessions().get_session(session_id)
    assert session.student_id == "person-a"
    assert session.session_budget_min == 10
    assert session.slide_indices


def test_join_with_readiness_refreshes_audience_profile():
    lid = _first_lesson()
    room_id = client.post("/api/live-rooms/solo", json={"lesson_id": lid}).json()["room_id"]
    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={
            "name": "Profile Learner",
            "identity": "profile-1",
            "student_id": "stu-profile",
            "readiness_score": 72,
            "readiness_band": "developing",
            "primary_style": "visual",
        },
    )
    assert joined.status_code == 200, joined.text
    aud = client.get(f"/api/live-rooms/{room_id}/audience-profile").json()["audience_profile"]
    assert aud["learner_count"] == 1
    assert aud["mean_readiness"] == 72
    assert "visual" in aud.get("dominant_styles", [])


def test_readiness_score_is_visible_only_to_moderators_and_platform_admins(monkeypatch):
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={
            "name": "Profile Learner",
            "identity": "profile-private-1",
            "student_id": "stu-private",
            "readiness_score": 72,
            "readiness_band": "developing",
            "primary_style": "visual",
        },
    )
    assert joined.status_code == 200, joined.text
    pid = joined.json()["participant"]["id"]

    public_participant = next(
        p for p in client.get(f"/api/live-rooms/{room_id}").json()["participants"]
        if p["id"] == pid
    )
    assert "readiness_score" not in public_participant
    assert "primary_style" not in public_participant
    assert "student_id" not in public_participant

    moderator_participant = next(
        p for p in client.get(
            f"/api/live-rooms/{room_id}",
            params={"moderator_key": mod},
        ).json()["participants"]
        if p["id"] == pid
    )
    assert moderator_participant["readiness_score"] == 72
    assert moderator_participant["readiness_band"] == "developing"
    assert moderator_participant["primary_style"] == "visual"

    moderator_tick = client.post(
        f"/api/live-rooms/{room_id}/tick",
        params={"pid": pid, "moderator_key": mod},
    )
    assert moderator_tick.status_code == 200, moderator_tick.text
    tick_participant = next(
        p for p in moderator_tick.json()["room"]["participants"] if p["id"] == pid
    )
    assert tick_participant["readiness_score"] == 72

    import orchestrator.main as m

    monkeypatch.setattr(m, "_request_is_admin", lambda auth: auth == "Bearer admin-token")
    platform_admin = client.get(
        f"/api/live-rooms/{room_id}",
        headers={"authorization": "Bearer admin-token"},
    )
    assert platform_admin.status_code == 200, platform_admin.text
    admin_participant = next(
        p for p in platform_admin.json()["participants"] if p["id"] == pid
    )
    assert admin_participant["readiness_score"] == 72


def test_solo_room_full_on_join_auto_starts_and_advances():
    from orchestrator.main import app as _app

    lid = _first_lesson()
    room_id = client.post("/api/live-rooms/solo", json={"lesson_id": lid}).json()["room_id"]
    # The single seat fills on join, so the room is full and the class
    # auto-starts on the first tick (mirrors the full-group auto-start).
    client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Ada", "identity": "ada-solo2"})
    room = _app.state.live_rooms.require(room_id)
    room.welcome_started_at = "2000-01-01T00:00:00+00:00"
    _app.state.live_rooms._backend.save(room)
    t1 = client.post(f"/api/live-rooms/{room_id}/tick")
    assert t1.status_code == 200, t1.text
    assert t1.json()["auto_started"] is True
    assert t1.json()["room"]["presenting"] is True

    room = _app.state.live_rooms.require(room_id)
    room.slide_started_at = "2000-01-01T00:00:00+00:00"
    _app.state.live_rooms._backend.save(room)
    t2 = client.post(f"/api/live-rooms/{room_id}/tick")
    assert t2.json()["auto_advanced"] is not None


def test_auto_advance_uses_a_content_proportional_dwell():
    import datetime

    from aoep_shared.live_room import LiveRoomStore
    from orchestrator.main import app as _app

    info = _start_salareen_class(4)  # 3 learner seats
    room_id = info["room_id"]
    for i in range(3):
        client.post(f"/api/live-rooms/{room_id}/join", json={"name": f"L{i}", "identity": f"adv-{i}"})
    room = _app.state.live_rooms.require(room_id)
    room.welcome_started_at = "2000-01-01T00:00:00+00:00"
    _app.state.live_rooms._backend.save(room)
    assert client.post(f"/api/live-rooms/{room_id}/tick").json()["auto_started"] is True

    room = _app.state.live_rooms.require(room_id)
    # The dwell scales with how long the slide takes to speak (>= the 5s floor),
    # so narration finishes before advancing and the class isn't over in seconds.
    dwell = LiveRoomStore.slide_dwell_seconds(room)
    assert dwell >= room.auto_advance_seconds

    now = datetime.datetime.now(datetime.timezone.utc)
    # A slide that just started must NOT advance yet (don't blow through slides).
    room.slide_started_at = now.isoformat()
    _app.state.live_rooms._backend.save(room)
    assert client.post(f"/api/live-rooms/{room_id}/tick").json()["auto_advanced"] is None

    # Once the dwell has elapsed, the next tick advances and updates the slide.
    room = _app.state.live_rooms.require(room_id)
    room.slide_started_at = (now - datetime.timedelta(seconds=dwell + 2)).isoformat()
    _app.state.live_rooms._backend.save(room)
    advanced = client.post(f"/api/live-rooms/{room_id}/tick").json()
    assert advanced["auto_advanced"] is not None
    assert advanced["room"]["slide"]["title"]


def test_tick_auto_ends_when_allotted_time_expires():
    from orchestrator.main import app as _app

    info = _start_salareen_class(4)  # default duration 60 min -> 3600s
    room_id = info["room_id"]
    for i in range(3):  # fill every learner seat so the class auto-starts
        client.post(f"/api/live-rooms/{room_id}/join", json={"name": f"L{i}", "identity": f"end-{i}"})
    room = _app.state.live_rooms.require(room_id)
    room.welcome_started_at = "2000-01-01T00:00:00+00:00"
    _app.state.live_rooms._backend.save(room)
    assert client.post(f"/api/live-rooms/{room_id}/tick").json()["auto_started"] is True

    room = _app.state.live_rooms.require(room_id)
    assert room.duration_seconds == 3600  # carried from the group class duration
    # The class has now been presenting longer than its allotted time.
    room.presentation_started_at = "2000-01-01T00:00:00+00:00"
    _app.state.live_rooms._backend.save(room)

    ended = client.post(f"/api/live-rooms/{room_id}/tick")
    assert ended.status_code == 200, ended.text
    assert ended.json()["auto_ended"] is True
    body = ended.json()["room"]
    assert body["status"] == "ended"
    assert body["ended_at"]
    assert body["presenting"] is False
    assert any("Thank you" in m["text"] for m in body["chat"])  # courteous farewell

    # Idempotent: a second tick from another client must not error or re-end.
    again = client.post(f"/api/live-rooms/{room_id}/tick")
    assert again.status_code == 200
    assert again.json()["auto_ended"] is False
    assert again.json()["room"]["status"] == "ended"


def test_tick_prunes_a_participant_who_left_without_leaving():
    from orchestrator.main import app as _app

    info = _start_salareen_class(6)
    room_id = info["room_id"]
    a = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Ada", "identity": "ada-ghost"}).json()["participant"]["id"]
    b = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Bo", "identity": "bo-live"}).json()["participant"]["id"]

    # Ada closed her browser (no leave call): backdate her presence heartbeat.
    room = _app.state.live_rooms.require(room_id)
    room.participants[a].last_seen = "2000-01-01T00:00:00+00:00"
    _app.state.live_rooms._backend.save(room)

    # Bo's tick (carrying his id) refreshes Bo and prunes the stale Ada.
    t = client.post(f"/api/live-rooms/{room_id}/tick?pid={b}")
    assert t.status_code == 200, t.text
    assert "Ada" in t.json()["pruned"]
    ids = [p["id"] for p in t.json()["room"]["participants"]]
    assert a not in ids and b in ids


def test_get_and_tick_close_an_expired_abandoned_room():
    from orchestrator.main import app as _app

    info = _start_salareen_class(4)
    room_id = info["room_id"]
    # Simulate a scheduled class whose whole allotted window lapsed with nobody
    # ticking (abandoned): it must NOT still read as "live".
    room = _app.state.live_rooms.require(room_id)
    room.duration_seconds = 3600
    room.scheduled_start = "2000-01-01T00:00:00+00:00"
    room.presentation_started_at = ""
    _app.state.live_rooms._backend.save(room)

    got = client.get(f"/api/live-rooms/{room_id}")
    assert got.status_code == 200, got.text
    assert got.json()["status"] == "ended"  # lazily closed on read, no client tick needed


def test_solo_room_is_open_ended_and_never_auto_ends():
    lid = _first_lesson()
    room_id = client.post("/api/live-rooms/solo", json={"lesson_id": lid}).json()["room_id"]
    client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Ada", "identity": "ada-open"})
    client.post(f"/api/live-rooms/{room_id}/tick")  # full on join -> auto-starts

    from orchestrator.main import app as _app

    room = _app.state.live_rooms.require(room_id)
    assert room.duration_seconds == 0  # open-ended (no scheduled allotment)
    room.presentation_started_at = "2000-01-01T00:00:00+00:00"
    _app.state.live_rooms._backend.save(room)
    t = client.post(f"/api/live-rooms/{room_id}/tick")
    assert t.json()["auto_ended"] is False
    assert t.json()["room"]["status"] == "live"


def test_solo_room_requires_valid_lesson():
    missing = client.post("/api/live-rooms/solo", json={"lesson_id": "no-such-lesson"})
    assert missing.status_code == 404, missing.text
    blank = client.post("/api/live-rooms/solo", json={"lesson_id": "  "})
    assert blank.status_code == 400, blank.text


def test_room_actions_reopen_on_a_replica_that_lacks_the_room(monkeypatch):
    # Reproduces the deployed multi-replica bug: a room opened on one replica is
    # absent on the replica serving the next POST, so tick / start-presentation /
    # media-token 404'd and the class "could not start". They must now REOPEN the
    # room (seed-on-miss) on any replica instead of 404ing.
    import orchestrator.main as m

    monkeypatch.setattr(m, "_request_is_admin", lambda auth: auth == "Bearer admin-token")
    cid = _standard_salareen_class_id()
    room_id = f"class-{cid}"
    client.get(f"/api/live-rooms/{room_id}")  # open the room on "this" replica

    # Evict it — as if the next request is routed to a replica that never saw it.
    m.app.state.live_rooms._backend.delete(room_id)
    assert m.app.state.live_rooms.get(room_id) is None
    # tick used to 404; now it reopens the room -> 200.
    assert client.post(f"/api/live-rooms/{room_id}/tick").status_code == 200

    m.app.state.live_rooms._backend.delete(room_id)
    # admin start-presentation used to 404; now reopens + starts -> 200.
    st = client.post(
        f"/api/live-rooms/{room_id}/start-presentation",
        json={},
        headers={"authorization": "Bearer admin-token"},
    )
    assert st.status_code == 200, st.text
    assert st.json()["presenting"] is True


def test_platform_admin_moderates_any_room_without_moderator_key(monkeypatch):
    # admin@salareen.com can start / mute / close / delete ANY room by Bearer
    # token, even though they never joined it and hold no moderator key.
    import orchestrator.main as m

    monkeypatch.setattr(m, "_request_is_admin", lambda auth: auth == "Bearer admin-token")
    admin = {"authorization": "Bearer admin-token"}

    info = _start_salareen_class(6)
    room_id = info["room_id"]
    learner = client.post(
        f"/api/live-rooms/{room_id}/join", json={"name": "Ada", "identity": "ada-adm"}
    ).json()["participant"]["id"]

    # A NON-admin with no key cannot start the class.
    assert client.post(f"/api/live-rooms/{room_id}/start-presentation", json={}).status_code == 400

    # The platform admin can start it (no moderator_key, just the admin token).
    started = client.post(f"/api/live-rooms/{room_id}/start-presentation", json={}, headers=admin)
    assert started.status_code == 200 and started.json()["presenting"] is True

    # Admin can mute a learner (acts as host).
    muted = client.post(
        f"/api/live-rooms/{room_id}/mute",
        json={"participant_id": learner, "muted": True},
        headers=admin,
    )
    assert muted.status_code == 200, muted.text
    assert muted.json()["participant"]["muted"] is True

    # Admin can close the session.
    ended = client.post(f"/api/live-rooms/{room_id}/end", json={}, headers=admin)
    assert ended.status_code == 200 and ended.json()["status"] == "ended"


def test_platform_admin_can_delete_a_room_others_cannot(monkeypatch):
    import orchestrator.main as m

    monkeypatch.setattr(m, "_request_is_admin", lambda auth: auth == "Bearer admin-token")
    # Use a solo room: group-class rooms deliberately re-seed on miss, so "delete"
    # only permanently removes non-class (solo/instant/user) rooms; class rooms are
    # cleaned up by closing (end). This asserts a true delete of a non-class room.
    lid = _first_lesson()
    room_id = client.post("/api/live-rooms/solo", json={"lesson_id": lid}).json()["room_id"]

    # A non-admin cannot delete.
    assert client.delete(f"/api/live-rooms/{room_id}").status_code == 403

    # The platform admin deletes it; a later GET 404s (genuinely gone).
    deleted = client.delete(f"/api/live-rooms/{room_id}", headers={"authorization": "Bearer admin-token"})
    assert deleted.status_code == 200 and deleted.json()["deleted"] is True
    assert client.get(f"/api/live-rooms/{room_id}").status_code == 404


def test_recording_endpoints():
    info = _start_salareen_class()
    room_id = info["room_id"]
    start = client.post(f"/api/live-rooms/{room_id}/record/start")
    assert start.status_code == 200, start.text
    assert start.json()["recording"]["status"] == "recording"
    stop = client.post(f"/api/live-rooms/{room_id}/record/stop")
    assert stop.status_code == 200, stop.text
    assert stop.json()["recording"]["status"] == "stopped"


def test_ban_and_unban_flow():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    assert mod

    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Spammer", "identity": "spam-1"},
    )
    assert joined.status_code == 200, joined.text
    pid = joined.json()["participant"]["id"]

    banned = client.post(
        f"/api/live-rooms/{room_id}/ban",
        json={"participant_id": pid, "moderator_key": mod, "reason": "Spam"},
    )
    assert banned.status_code == 200, banned.text
    assert banned.json()["banned"]["identity"] == "spam-1"

    blocked = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Spammer", "identity": "spam-1"},
    )
    assert blocked.status_code == 403

    unbanned = client.post(
        f"/api/live-rooms/{room_id}/unban",
        json={"identity": "spam-1", "moderator_key": mod},
    )
    assert unbanned.status_code == 200, unbanned.text

    rejoin = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Spammer", "identity": "spam-1"},
    )
    assert rejoin.status_code == 200, rejoin.text


def test_report_and_moderator_review():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    reporter = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Ada", "identity": "reporter-1"},
    ).json()["participant"]
    target = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Bob", "identity": "target-1"},
    ).json()["participant"]
    reported = client.post(
        f"/api/live-rooms/{room_id}/report",
        json={
            "reporter_participant_id": reporter["id"],
            "reported_participant_id": target["id"],
            "reason": "Harassing messages",
            "category": "harassment",
        },
    )
    assert reported.status_code == 200, reported.text

    mod_view = client.get(
        f"/api/live-rooms/{room_id}",
        params={"moderator_key": mod},
    )
    assert mod_view.status_code == 200, mod_view.text
    reports = mod_view.json().get("reports") or []
    assert len(reports) == 1
    assert reports[0]["reported_name"] == "Bob"

    dismissed = client.post(
        f"/api/live-rooms/{room_id}/reports/dismiss",
        json={"report_id": reports[0]["id"], "moderator_key": mod},
    )
    assert dismissed.status_code == 200, dismissed.text
    assert dismissed.json()["room"].get("reports") == []


def test_gift_catalog_and_send():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Gifter", "identity": "gift-1"},
    )
    assert joined.status_code == 200, joined.text
    pid = joined.json()["participant"]["id"]
    assert joined.json()["gift_balance"] >= 10

    catalog = client.get("/api/live-rooms/gifts/catalog")
    assert catalog.status_code == 200
    gifts = catalog.json()["gifts"]
    assert any(g["id"] == "rose" for g in gifts)

    sent = client.post(
        f"/api/live-rooms/{room_id}/gifts/send",
        json={"participant_id": pid, "gift_id": "rose"},
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["gift"]["emoji"] == "🌹"
    assert body["sender_balance"] == joined.json()["gift_balance"] - 10
    assert any("🌹" in m["text"] for m in body["room"]["chat"])


def test_reaction_endpoint():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    pid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Fan", "identity": "fan-1"},
    ).json()["participant"]["id"]
    reacted = client.post(
        f"/api/live-rooms/{room_id}/reactions",
        json={"participant_id": pid, "emoji": "❤️"},
    )
    assert reacted.status_code == 200, reacted.text
    assert reacted.json()["reaction"]["emoji"] == "❤️"


def test_follow_host_endpoint():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    follow = client.post(
        f"/api/live-rooms/{room_id}/follow",
        json={"identity": "follower-1"},
    )
    assert follow.status_code == 200, follow.text
    assert follow.json()["following"] is True
    assert follow.json()["follower_count"] == 1
    status = client.get(
        f"/api/live-rooms/{room_id}/follow",
        params={"identity": "follower-1"},
    )
    assert status.status_code == 200
    assert status.json()["following"] is True


def test_live_room_websocket_snapshot():
    info = _start_salareen_class(4)
    room_id = info["room_id"]
    with client.websocket_connect(f"/api/live-rooms/{room_id}/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "room"
        assert msg["payload"]["room"]["room_id"] == room_id


def test_list_live_rooms_after_start():
    info = _start_salareen_class(6)
    listed = client.get("/api/live-rooms")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] >= 1
    ids = {r["room_id"] for r in body["rooms"]}
    assert info["room_id"] in ids
    assert body.get("groups")


def test_create_user_live_room_with_geo():
    created = client.post(
        "/api/live-rooms",
        json={
            "title": "Study hall SF",
            "creator_name": "Ada",
            "room_size": 6,
            "location": {
                "country": "United States",
                "state": "California",
                "city": "San Francisco",
                "latitude": 37.77,
                "longitude": -122.42,
            },
        },
    )
    assert created.status_code == 200, created.text
    room_id = created.json()["listing"]["room_id"]
    assert created.json()["listing"]["city"] == "San Francisco"

    nearby = client.get("/api/live-rooms", params={"lat": 37.78, "lng": -122.41, "radius_km": 50})
    assert nearby.status_code == 200
    ids = {r["room_id"] for r in nearby.json()["rooms"]}
    assert room_id in ids

    joined = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Bob", "identity": "bob-1"},
    )
    assert joined.status_code == 200, joined.text


def test_chat_flood_returns_429():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    pid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Spammer", "identity": "spam-1"},
    ).json()["participant"]["id"]
    # 5 messages allowed in the window, the 6th is rate-limited (429).
    for i in range(5):
        r = client.post(f"/api/live-rooms/{room_id}/chat", json={"participant_id": pid, "text": f"m{i}"})
        assert r.status_code == 200, r.text
    blocked = client.post(f"/api/live-rooms/{room_id}/chat", json={"participant_id": pid, "text": "flood"})
    assert blocked.status_code == 429, blocked.text
    assert "too fast" in blocked.json()["detail"].lower()


def test_chat_rejects_overlong_message():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    pid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Verbose", "identity": "verbose-1"},
    ).json()["participant"]["id"]
    r = client.post(
        f"/api/live-rooms/{room_id}/chat",
        json={"participant_id": pid, "text": "x" * 5000},
    )
    assert r.status_code == 400
    assert "too long" in r.json()["detail"].lower()


def test_ask_flood_returns_429():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    pid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Asker", "identity": "asker-1"},
    ).json()["participant"]["id"]
    for i in range(3):
        r = client.post(f"/api/live-rooms/{room_id}/ask", json={"participant_id": pid, "question": f"q{i}?"})
        assert r.status_code == 200, r.text
    blocked = client.post(f"/api/live-rooms/{room_id}/ask", json={"participant_id": pid, "question": "spam?"})
    assert blocked.status_code == 429, blocked.text


def test_tick_ai_answers_queued_question():
    # A learner joins the Q&A queue with a typed question while the class is
    # presenting; a tick should have the AI host pause and answer it in chat,
    # then clear it from the queue (no human moderator needed).
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    client.post(f"/api/live-rooms/{room_id}/start-presentation", json={"moderator_key": mod})
    pid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Curious", "identity": "curious-1"},
    ).json()["participant"]["id"]
    # Raise hand WITH a question -> goes to the waiting queue.
    client.post(f"/api/live-rooms/{room_id}/queue/join", json={"participant_id": pid, "question": "What is a fraction?"})
    before = client.get(f"/api/live-rooms/{room_id}").json()
    assert any(e["status"] == "waiting" for e in before["speaking_queue"])
    # Tick as the learner -> AI addresses the queue.
    r = client.post(f"/api/live-rooms/{room_id}/tick", params={"pid": pid})
    assert r.status_code == 200, r.text
    assert r.json()["addressed_queue"] is not None
    room = client.get(f"/api/live-rooms/{room_id}").json()
    # The question is no longer waiting, and Theodore replied in chat.
    assert not any(e["status"] == "waiting" for e in room["speaking_queue"])
    host_msgs = [m for m in room["chat"] if "Theodore" in m["from_name"]]
    assert any("Curious" in m["text"] for m in host_msgs)


def test_self_mute_and_unmute_without_actor_id():
    # Regression: the web client sends no actor_id; the endpoint must treat that
    # as a self-mute (not default the actor to the AI host, which 400'd with
    # "learners can only mute themselves").
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    pid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Lena", "identity": "lena-1"},
    ).json()["participant"]["id"]
    muted = client.post(
        f"/api/live-rooms/{room_id}/mute",
        json={"participant_id": pid, "muted": True},
    )
    assert muted.status_code == 200, muted.text
    assert muted.json()["participant"]["muted"] is True
    unmuted = client.post(
        f"/api/live-rooms/{room_id}/mute",
        json={"participant_id": pid, "muted": False},
    )
    assert unmuted.status_code == 200, unmuted.text
    assert unmuted.json()["participant"]["muted"] is False


def test_learner_cannot_mute_another_learner():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    a = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Aa", "identity": "aa"}).json()["participant"]["id"]
    b = client.post(f"/api/live-rooms/{room_id}/join", json={"name": "Bb", "identity": "bb"}).json()["participant"]["id"]
    # A (actor) tries to mute B (target) with no moderator rights -> rejected.
    r = client.post(
        f"/api/live-rooms/{room_id}/mute",
        json={"participant_id": b, "muted": True, "actor_id": a},
    )
    assert r.status_code == 400
    assert "themselves" in r.json()["detail"].lower()


def test_livekit_status_route_resolves_and_reports_config():
    # Static /livekit-status route must not be swallowed by /{room_id}.
    resp = client.get("/api/live-rooms/livekit-status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in (
        "url",
        "url_is_cloud",
        "api_key",
        "api_key_configured",
        "api_secret_configured",
        "using_dev_defaults",
        "likely_misconfigured",
        "hint",
    ):
        assert key in body, f"missing {key}"
    # The raw secret is never leaked; the key is masked (or empty).
    assert "…" in body["api_key"] or body["api_key"] == ""
    assert "probe" not in body  # no live probe unless ?probe=1


def test_livekit_status_probe_returns_verdict():
    resp = client.get("/api/live-rooms/livekit-status", params={"probe": 1})
    assert resp.status_code == 200, resp.text
    probe = resp.json()["probe"]
    # In the test env LiveKit Cloud is unreachable; the verdict is structured.
    assert probe["status"] in {"verified", "rejected", "unreachable", "error"}


def test_livekit_health_flags_cloud_with_dev_secret():
    from orchestrator.main import _livekit_health

    class _Cfg:
        livekit_url = "wss://demo.livekit.cloud"
        livekit_api_key = "APIrealkey123"
        livekit_api_secret = "devsecret"

    health = _livekit_health(_Cfg())
    assert health["url_is_cloud"] is True
    assert health["likely_misconfigured"] is True
    assert health["api_secret_configured"] is False


def _parse_sse(body: str) -> list[dict]:
    import json

    events: list[dict] = []
    for frame in body.split("\n\n"):
        for line in frame.splitlines():
            if line.startswith("data:"):
                try:
                    events.append(json.loads(line[len("data:"):].strip()))
                except json.JSONDecodeError:
                    pass
    return events


def test_ask_stream_streams_host_answer_and_posts_chat():
    # The group-class AI host (Theodore) answers via the streaming endpoint: SSE
    # emits delta(s) then a done event carrying the finalized host chat message.
    # Offline (no model server) it falls back to the grounded blocking answer, so
    # this still produces real content in CI.
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    client.post(f"/api/live-rooms/{room_id}/start-presentation", json={})
    pid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={"name": "Ada", "identity": "ada-stream"},
    ).json()["participant"]["id"]

    resp = client.post(
        f"/api/live-rooms/{room_id}/ask-stream",
        json={"participant_id": pid, "question": "What is this lesson about?"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(resp.text)
    types = [e.get("type") for e in events]
    assert "done" in types, events
    done = next(e for e in events if e.get("type") == "done")
    assert done["text"].strip()
    assert done["host_message"]["text"].startswith("@Ada")
    # The finalized answer is also posted into the room chat for late joiners.
    chat = [m["text"] for m in done["room"]["chat"]]
    assert any(t.startswith("@Ada") for t in chat)


def test_ask_stream_queues_when_floor_taken():
    # Mirrors the blocking /ask queue behavior: if someone else holds the floor,
    # the streaming endpoint emits a single queued event instead of an answer.
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    a = client.post(
        f"/api/live-rooms/{room_id}/join", json={"name": "Ada", "identity": "a1"}
    ).json()["participant"]["id"]
    b = client.post(
        f"/api/live-rooms/{room_id}/join", json={"name": "Grace", "identity": "b1"}
    ).json()["participant"]["id"]
    client.post(f"/api/live-rooms/{room_id}/queue/join", json={"participant_id": a, "question": "Q1"})
    client.post(f"/api/live-rooms/{room_id}/queue/call-next", json={"moderator_key": mod})

    resp = client.post(
        f"/api/live-rooms/{room_id}/ask-stream",
        json={"participant_id": b, "question": "My turn?"},
    )
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    assert events and events[0]["type"] == "queued"
    assert events[0]["queue_position"] == 1


def test_xr_lab_enable_and_complete_pass_needs_work():
    info = _start_salareen_class(6)
    room_id = info["room_id"]
    mod = info["started"]["bridge"]["moderator_key"]
    pid = client.post(
        f"/api/live-rooms/{room_id}/join",
        json={
            "name": "XR Learner",
            "identity": "xr1",
            "student_id": "stu-xr",
            "readiness_score": 70,
            "readiness_band": "developing",
        },
    ).json()["participant"]["id"]

    enabled = client.post(
        f"/api/live-rooms/{room_id}/xr/enable",
        json={"moderator_key": mod, "enabled": True, "title": "Demo lab"},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["lab"]["lab_id"]
    lab = client.get(f"/api/live-rooms/{room_id}/xr/lab").json()
    assert lab["enabled"] is True

    pass_body = {
        "participant_id": pid,
        "student_id": "stu-xr",
        "client_kind": "webxr",
        "observations": [
            {"seq": 1, "action": "approach", "target_id": "station", "confidence": 0.95},
            {"seq": 2, "action": "grab", "target_id": "tool", "confidence": 0.9, "hold_ms": 600},
            {"seq": 3, "action": "confirm", "target_id": "finish", "confidence": 0.92},
        ],
    }
    ok = client.post(f"/api/live-rooms/{room_id}/xr/complete", json=pass_body)
    assert ok.status_code == 200, ok.text
    assert ok.json()["result"]["outcome"] == "pass"

    unity_same = client.post(
        f"/api/live-rooms/{room_id}/xr/complete",
        json={**pass_body, "client_kind": "unity_openxr"},
    )
    assert unity_same.json()["result"]["outcome"] == "pass"
    assert unity_same.json()["result"]["score"] == ok.json()["result"]["score"]

    weak = client.post(
        f"/api/live-rooms/{room_id}/xr/complete",
        json={
            "participant_id": pid,
            "client_kind": "webxr",
            "observations": [
                {"seq": 1, "action": "approach", "target_id": "station", "confidence": 0.8},
            ],
        },
    )
    assert weak.json()["result"]["outcome"] == "needs_work"

    aud = client.get(f"/api/live-rooms/{room_id}/audience-profile?refresh=true").json()
    assert "audience_profile" in aud
    assert "student_id" not in aud["audience_profile"]
