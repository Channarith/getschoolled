"""Lesson holds for absence and cheating, and spoken answers must connect."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from theodore_course_studio import learning_guard
from theodore_course_studio.main import app

client = TestClient(app)


def setup_function() -> None:
    learning_guard.reset_for_tests()


def _sid() -> str:
    return "learn-" + uuid.uuid4().hex


def _present(**extra: object) -> dict:
    signal = {
        "face_count": 1,
        "liveness_state": "live",
        "gaze_frontal": 0.9,
        "gaze_down_score": 0.1,
        "face_size_ratio": 0.36,
        "distance_from_camera_m": 0.55,
        "light_quality_score": 0.82,
        "foreground_ratio": 0.4,
        "motion_score": 0.04,
    }
    signal.update(extra)
    return signal


def _observe(session_id: str, timestamp_ms: int, signal: dict) -> dict:
    return learning_guard.observe_camera(
        session_id=session_id,
        participant_id="learner",
        timestamp_ms=timestamp_ms,
        signal=signal,
    )


def test_absence_holds_only_after_the_grace_window() -> None:
    session_id = _sid()
    first = _observe(session_id, 0, {"face_count": 0, "liveness_state": "missing"})
    assert first["hold"] is False
    brief = _observe(session_id, 1000, {"face_count": 0, "liveness_state": "missing"})
    assert brief["hold"] is False
    second = _observe(session_id, 4000, {"face_count": 0, "liveness_state": "missing"})
    assert second["hold"] is True
    assert second["reason"] == "no_learner_detected"
    assert second["absent"] is True
    assert "camera" in second["speech"].lower()


def test_second_person_and_owner_mismatch_and_phone_hold(monkeypatch) -> None:
    monkeypatch.setattr(learning_guard, "theodore_followup", lambda **_kwargs: "unused")
    crowd = _observe(
        _sid(),
        0,
        _present(face_count=2, secondary_face_count=1),
    )
    assert crowd["hold"] is True
    assert "secondary_faces_in_frame" in crowd["cheating_reasons"]

    mismatch = _observe(
        _sid(),
        0,
        _present(owner_face_enrolled=True, owner_face_match=False),
    )
    assert mismatch["hold"] is True
    assert mismatch["reason"] == "owner_face_mismatch"

    session_id = _sid()
    phone = _present(phone_visible=True, gaze_down_score=0.0)
    assert _observe(_sid(), 0, phone)["hold"] is False
    later = None
    for timestamp_ms in range(0, 6001, 1000):
        later = _observe(session_id, timestamp_ms, phone)
    assert later is not None
    assert later["hold"] is True
    assert "phone_visible" in later["cheating_reasons"]


def test_sustained_look_away_holds() -> None:
    session_id = _sid()
    looking_away = _present(gaze_frontal=0.1, gaze_down_score=0.05)
    assert _observe(session_id, 0, looking_away)["hold"] is False
    later = _observe(session_id, 46000, looking_away)
    assert later["hold"] is True
    assert "eyes_away_long" in later["cheating_reasons"]


def test_coarse_grid_can_show_someone_is_present() -> None:
    grid = [[0.62 for _ in range(16)] for _ in range(12)]
    for y in range(2, 9):
        for x in range(4, 12):
            grid[y][x] = 0.28 if (x + y) % 2 == 0 else 0.7
    result = _observe(
        _sid(),
        0,
        {
            "face_count": 0,
            "detector_source": "coarse",
            "liveness_state": "missing",
            "luminance_grid": grid,
            "light_quality_score": 0.8,
        },
    )
    assert result["hold"] is False
    assert result["state"] == "present"


def test_yawning_changes_delivery_without_pausing() -> None:
    session_id = _sid()
    tired = _present(yawn_score=0.8, expression_label="yawning")
    first = _observe(session_id, 0, tired)
    assert first["hold"] is False
    assert first["adapt"]["mode"] == "wake"
    assert first["adapt"]["flow"] == "shorten"
    assert first["adapt"]["speech"]
    assert first["delivery"]["style"] == "brisk"
    later = _observe(session_id, 2000, tired)
    assert later["hold"] is False
    assert later["adapt"] is None
    assert later["delivery"]["mode"] == "wake"


def test_attention_shift_refocuses_without_a_hold() -> None:
    class _State:
        value = "present"

    class _Person:
        state = _State()
        behavior_label = "inattentive"
        advanced_behavior = {"boredom_score": 0.2, "fatigue_score": 0.1, "observatory_label": "focused"}
        yawn_for_ms = 0
        inattentive_for_ms = 5000

    shift = learning_guard._attention_shift(_Person())
    assert shift is not None
    assert shift["mode"] == "refocus"
    assert shift["flow"] == "question"

    class _Fine:
        state = _State()
        behavior_label = "focused"
        advanced_behavior = {"boredom_score": 0.1, "fatigue_score": 0.1, "observatory_label": "focused"}
        yawn_for_ms = 0
        inattentive_for_ms = 0

    assert learning_guard._attention_shift(_Fine()) is None


def test_a_normal_desk_seat_is_not_paused() -> None:
    session_id = _sid()
    seated = _present(
        face_size_ratio=0.28,
        detector_source="face_detector",
        gaze_frontal=0.9,
        gaze_down_score=0.25,
    )
    seated.pop("distance_from_camera_m", None)
    result = None
    for timestamp_ms in range(0, 5001, 1000):
        result = _observe(session_id, timestamp_ms, seated)
        assert result["hold"] is False, result
    assert result is not None
    assert result["state"] == "present"


def test_someone_across_the_room_is_paused() -> None:
    far = _observe(_sid(), 0, _present(distance_from_camera_m=2.2, face_size_ratio=0.08))
    assert far["hold"] is True
    assert far["reason"] == "too_far_from_camera"


def test_untranslated_answer_is_not_graded_as_english(monkeypatch) -> None:
    monkeypatch.setattr(learning_guard, "theodore_followup", lambda **_kwargs: "")
    monkeypatch.setattr(learning_guard, "_translate_to_lesson", lambda *_args, **_kwargs: ("hola energía", False))
    result = learning_guard.check_spoken_learning(
        session_id=_sid(),
        lesson_text="Photosynthesis turns light into stored energy.",
        spoken="La fotosíntesis guarda energía.",
        language="en",
        spoken_language="es",
    )
    assert result["accepted"] is False
    assert "lesson language" in result["speech"].lower()


def test_spoken_answer_must_connect_to_the_page(monkeypatch) -> None:
    monkeypatch.setattr(
        learning_guard,
        "theodore_followup",
        lambda **kwargs: "Coach." if not kwargs["accepted"] else "Teach onward.",
    )
    lesson = "Photosynthesis turns light into stored energy inside a leaf."
    short = learning_guard.check_spoken_learning(
        session_id=_sid(),
        lesson_text=lesson,
        spoken="ok",
    )
    assert short["accepted"] is False
    assert short["speech"] == "Coach."

    connected = learning_guard.check_spoken_learning(
        session_id=_sid(),
        lesson_text=lesson,
        spoken="Photosynthesis stores energy from light in the leaf.",
    )
    assert connected["accepted"] is True
    assert "photosynthesis" in connected["overlap"]
    assert connected["speech"] == "Teach onward."

    unrelated = learning_guard.check_spoken_learning(
        session_id=_sid(),
        lesson_text=lesson,
        spoken="The train station opens before sunrise.",
    )
    assert unrelated["accepted"] is False


def test_learn_routes_use_the_same_decisions(monkeypatch) -> None:
    monkeypatch.setattr(learning_guard, "theodore_followup", lambda **_kwargs: "Noted.")
    status = client.get("/api/studio/learn/status")
    assert status.status_code == 200
    assert status.json()["ready"] is True
    assert "presence" in status.json()["features"]

    session_id = _sid()
    away = client.post(
        "/api/studio/learn/camera",
        json={
            "session_id": session_id,
            "participant_id": "learner",
            "timestamp_ms": 0,
            "signal": {"face_count": 0, "liveness_state": "missing"},
        },
    )
    assert away.status_code == 200
    assert away.json()["hold"] is False
    later = client.post(
        "/api/studio/learn/camera",
        json={
            "session_id": session_id,
            "participant_id": "learner",
            "timestamp_ms": 4000,
            "signal": {"face_count": 0, "liveness_state": "missing"},
        },
    )
    assert later.status_code == 200
    assert later.json()["hold"] is True

    checked = client.post(
        "/api/studio/learn/check",
        json={
            "session_id": session_id,
            "lesson_text": "Roots pull water into the plant.",
            "spoken": "Roots pull water from the soil.",
            "language": "en",
        },
    )
    assert checked.status_code == 200
    body = checked.json()
    assert body["accepted"] is True
    assert body["speech"] == "Noted."
