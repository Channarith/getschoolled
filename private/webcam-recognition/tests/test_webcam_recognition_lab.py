from __future__ import annotations

from datetime import datetime, timedelta, timezone

from webcam_recognition_lab import (
    AbsenceTracker,
    FaceObservation,
    SilhouetteObservation,
    VoiceAgentEvent,
    WebcamFrameObservation,
    XaiVoiceAgent,
    evaluate_presence,
)


def test_verified_face_emits_live_room_presence_payload() -> None:
    frame = WebcamFrameObservation(
        participant_id="learner-1",
        faces=(FaceObservation("face-1", attention=0.82, gaze_frontal=0.9),),
        observed_at=datetime(2026, 8, 4, 17, 0, tzinfo=timezone.utc),
    )

    decision = evaluate_presence(frame, mode="solo_ai_teaching")

    assert decision.teacher_action == "continue"
    assert decision.to_presence_report() == {
        "participant_id": "learner-1",
        "present": True,
        "face_count": 1,
        "liveness_state": "live",
        "liveness_score": 0.868,
        "reason": "verified_face",
        "source": "webcam-recognition-lab",
        "observed_at": "2026-08-04T17:00:00+00:00",
    }


def test_silhouette_only_asks_for_camera_adjustment_without_claiming_live() -> None:
    frame = WebcamFrameObservation(
        participant_id="learner-1",
        silhouettes=(
            SilhouetteObservation(
                "body-1",
                bbox=(240, 70, 190, 430),
                frame_size=(640, 480),
                confidence=0.88,
                motion_score=0.4,
            ),
        ),
    )

    decision = evaluate_presence(frame, mode="group_class")

    assert decision.present is True
    assert decision.liveness_state == "unknown"
    assert decision.reason == "silhouette_only"
    assert decision.teacher_action == "ask_camera_adjustment"
    assert decision.should_pause is True


def test_too_many_faces_pauses_theodore_for_one_learning_seat() -> None:
    frame = WebcamFrameObservation(
        participant_id="learner-1",
        faces=(FaceObservation("face-1"), FaceObservation("face-2")),
    )

    decision = evaluate_presence(frame, mode="solo_ai_teaching")

    assert decision.present is False
    assert decision.liveness_state == "spoof"
    assert decision.reason == "too_many_faces"
    assert decision.teacher_action == "pause_until_return"


def test_absence_tracker_holds_after_mode_grace_window() -> None:
    tracker = AbsenceTracker(mode="solo_ai_teaching")
    start = datetime(2026, 8, 4, 17, 0, tzinfo=timezone.utc)
    frame = WebcamFrameObservation(participant_id="learner-1", observed_at=start)

    _, first_state = tracker.update(frame)
    assert first_state.hold_active is False

    late_frame = WebcamFrameObservation(
        participant_id="learner-1",
        observed_at=start + timedelta(seconds=91),
    )
    decision, late_state = tracker.update(late_frame)

    assert decision.reason == "absent"
    assert late_state.hold_active is True
    assert tracker.should_hold("learner-1") is True


def test_self_teaching_uses_nudge_instead_of_enforced_absence_hold() -> None:
    tracker = AbsenceTracker(mode="solo_self_teaching")
    start = datetime(2026, 8, 4, 17, 0, tzinfo=timezone.utc)

    tracker.update(WebcamFrameObservation(participant_id="learner-1", observed_at=start))
    decision, state = tracker.update(
        WebcamFrameObservation(
            participant_id="learner-1",
            observed_at=start + timedelta(seconds=240),
        )
    )

    assert decision.teacher_action == "reengage"
    assert state.hold_active is False


def test_xai_voice_agent_falls_back_without_api_key() -> None:
    decision = evaluate_presence(WebcamFrameObservation(participant_id="learner-1"), mode="group_class")
    agent = XaiVoiceAgent(api_key="")

    response = agent.respond(VoiceAgentEvent("Ada", "group class", decision))

    assert response.used_network is False
    assert response.model == "offline-theodore"
    assert "pause" in response.text.lower()


def test_xai_voice_agent_shapes_openai_compatible_payload() -> None:
    calls: list[tuple[str, dict, dict, float]] = []

    def transport(url: str, headers: dict, payload: dict, timeout: float) -> dict:
        calls.append((url, headers, payload, timeout))
        return {"choices": [{"message": {"content": "Welcome back. Let's continue."}}]}

    decision = evaluate_presence(
        WebcamFrameObservation(
            participant_id="learner-1",
            faces=(FaceObservation("face-1", attention=0.2),),
        ),
        mode="solo_ai_teaching",
    )
    agent = XaiVoiceAgent(api_key="test-key", model="grok-test", transport=transport)

    response = agent.respond(VoiceAgentEvent("Ada", "solo Theodore", decision, ("Fractions",)))

    assert response.text == "Welcome back. Let's continue."
    assert response.used_network is True
    url, headers, payload, timeout = calls[0]
    assert url == "https://api.x.ai/v1/chat/completions"
    assert headers["Authorization"] == "Bearer test-key"
    assert payload["model"] == "grok-test"
    assert payload["messages"][1]["role"] == "user"
    assert "low_attention" in payload["messages"][1]["content"]
    assert timeout == 20.0
