"""A class a person teaches must have no Theodore in it.

When a user schedules and teaches a class ("Teach a class"), they are the
presenter: they hold the host slot, no AI host is placed in the room, and none of
Theodore's automation (auto-start, auto narration, auto Q&A) runs.
"""

from __future__ import annotations

import pytest
from aoep_shared.live_room import AI_HOST_ID, HUMAN_HOST_ID, LiveRoomStore

TEACHER = "acct-teacher"
STUDENT = "acct-student"


def _open(store: LiveRoomStore, *, human: bool, room_id: str = "class-1") -> None:
    extra = (
        {
            "human_taught": True,
            "human_host_account_id": TEACHER,
            "human_host_name": "Ms. Rivera",
        }
        if human
        else {}
    )
    store.open_room(
        room_id=room_id,
        class_id="c1",
        session_id="s1",
        lesson_id="l1",
        title="my solo 1:1",
        creator_account_id=TEACHER,
        **extra,
    )


def test_ai_taught_room_is_unchanged():
    store = LiveRoomStore()
    _open(store, human=False)
    room = store.require("class-1")
    assert AI_HOST_ID in room.participants
    assert room.host().id == AI_HOST_ID
    assert room.human_taught is False
    assert "Theodore" in room.chat[0].from_name


def test_human_taught_room_has_no_theodore():
    store = LiveRoomStore()
    _open(store, human=True)
    room = store.require("class-1")
    assert AI_HOST_ID not in room.participants
    assert room.human_taught is True
    # A host slot still exists so the room renders before the teacher arrives.
    assert room.host().id == HUMAN_HOST_ID
    assert room.host().name == "Ms. Rivera"
    assert all("Theodore" not in m.from_name for m in room.chat)
    assert "Ms. Rivera is teaching this class live" in room.welcome_message


def test_instructor_takes_the_host_slot_on_join():
    store = LiveRoomStore()
    _open(store, human=True)
    teacher = store.join("class-1", "Ms. Rivera", identity="t1", account_id=TEACHER)
    room = store.require("class-1")

    assert teacher.role == "host"
    assert room.host().id == teacher.id
    assert HUMAN_HOST_ID not in room.participants
    # The presenter must be able to publish video immediately.
    assert teacher.can_publish is True
    assert teacher.is_admin is True


def test_students_stay_learners_and_do_not_take_the_host_slot():
    store = LiveRoomStore()
    _open(store, human=True)
    teacher = store.join("class-1", "Ms. Rivera", identity="t1", account_id=TEACHER)
    student = store.join("class-1", "Sam", identity="s1", account_id=STUDENT)
    room = store.require("class-1")

    assert student.role == "learner"
    assert student.can_publish is False
    assert room.host().id == teacher.id


def test_student_joining_first_does_not_become_the_presenter():
    store = LiveRoomStore()
    _open(store, human=True)
    student = store.join("class-1", "Sam", identity="s1", account_id=STUDENT)
    room = store.require("class-1")
    assert student.role == "learner"
    assert room.host().id == HUMAN_HOST_ID

    teacher = store.join("class-1", "Ms. Rivera", identity="t1", account_id=TEACHER)
    room = store.require("class-1")
    assert room.host().id == teacher.id


def test_host_slot_is_restored_when_the_instructor_leaves():
    store = LiveRoomStore()
    _open(store, human=True)
    teacher = store.join("class-1", "Ms. Rivera", identity="t1", account_id=TEACHER)

    store.leave("class-1", teacher.id)
    room = store.require("class-1")
    assert room.host().id == HUMAN_HOST_ID
    assert room.host().name == "Ms. Rivera"

    back = store.join("class-1", "Ms. Rivera", identity="t1", account_id=TEACHER)
    assert store.require("class-1").host().id == back.id


def test_the_ai_host_still_cannot_leave_an_ai_taught_room():
    from aoep_shared.live_room import LiveRoomError

    store = LiveRoomStore()
    _open(store, human=False)
    with pytest.raises(LiveRoomError):
        store.leave("class-1", AI_HOST_ID)


def test_human_taught_class_never_auto_starts():
    store = LiveRoomStore()
    _open(store, human=True)
    store.join("class-1", "Ms. Rivera", identity="t1", account_id=TEACHER)
    store.join("class-1", "Sam", identity="s1", account_id=STUDENT)
    # Even with the room populated, only the instructor may begin the class.
    assert store.should_auto_start("class-1") is False


def test_automated_notices_come_from_the_instructor_not_theodore():
    store = LiveRoomStore()
    _open(store, human=True)
    store.join("class-1", "Ms. Rivera", identity="t1", account_id=TEACHER)

    msg = store.post_host_message("class-1", "Slide 2: Your turn to apply it")
    assert msg.from_name == "Ms. Rivera"
    assert "Theodore" not in msg.from_name


def test_serialized_room_tells_the_client_it_is_human_taught():
    store = LiveRoomStore()
    _open(store, human=True)
    teacher = store.join("class-1", "Ms. Rivera", identity="t1", account_id=TEACHER)

    payload = store.require("class-1").to_dict()
    assert payload["human_taught"] is True
    assert payload["human_host_name"] == "Ms. Rivera"
    assert payload["host"]["id"] == teacher.id
    assert payload["host"]["name"] == "Ms. Rivera"
    assert not any("Theodore" in m["from_name"] for m in payload["chat"])


# --------------------------------------------------------------- API contract
def test_started_instructor_class_opens_a_room_with_no_theodore(monkeypatch):
    """End-to-end: scheduling as an instructor then starting yields a human room."""
    from datetime import datetime, timedelta, timezone

    from fastapi.testclient import TestClient
    from orchestrator.main import app

    client = TestClient(app)
    monkeypatch.setattr(
        "aoep_shared.live_room_rewards.account_from_authorization",
        lambda auth: "teacher-1" if auth == "Bearer teacher-token" else "",
    )
    lesson_id = client.get("/api/lessons").json()[0]["lesson_id"]
    start_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    created = client.post(
        "/api/group-classes",
        json={"title": "my solo 1:1", "lesson_id": lesson_id, "start_time": start_at},
        headers={"authorization": "Bearer teacher-token"},
    )
    assert created.status_code == 200, created.text
    gc = created.json()
    assert gc["instructor_account_id"] == "teacher-1"

    # Only the creator may start it.
    assert client.post(f"/api/group-classes/{gc['id']}/start", json={}).status_code == 403

    started = client.post(
        f"/api/group-classes/{gc['id']}/start",
        json={},
        headers={"authorization": "Bearer teacher-token"},
    )
    assert started.status_code == 200, started.text

    room = client.get(f"/api/live-rooms/class-{gc['id']}").json()
    assert room["human_taught"] is True
    assert "Theodore" not in room["host"]["name"]
    assert not any("Theodore" in m["from_name"] for m in room["chat"])


def test_student_study_group_still_gets_theodore(monkeypatch):
    """A student-created study group has no instructor, so Theodore still teaches."""
    from datetime import datetime, timedelta, timezone

    from fastapi.testclient import TestClient
    from orchestrator.main import app

    client = TestClient(app)
    monkeypatch.setattr(
        "aoep_shared.live_room_rewards.account_from_authorization",
        lambda auth: "student-9" if auth == "Bearer student-token" else "",
    )
    lesson_id = client.get("/api/lessons").json()[0]["lesson_id"]
    start_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    created = client.post(
        "/api/group-classes",
        json={
            "title": "study group",
            "lesson_id": lesson_id,
            "start_time": start_at,
            "is_student_session": True,
        },
        headers={"authorization": "Bearer student-token"},
    )
    assert created.status_code == 200, created.text
    gc = created.json()
    # instructor_account_id defaults to the creator, so it cannot distinguish a
    # study group from a taught class; the explicit flag is what matters.
    assert gc.get("human_taught") is False

    started = client.post(
        f"/api/group-classes/{gc['id']}/start",
        json={},
        headers={"authorization": "Bearer student-token"},
    )
    assert started.status_code == 200, started.text

    room = client.get(f"/api/live-rooms/class-{gc['id']}").json()
    assert room.get("human_taught") is False
    assert room["host"]["name"] == "Theodore (AI Host)"
