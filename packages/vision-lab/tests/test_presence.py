from __future__ import annotations

import pytest

from aoep_shared.live_room import (
    PRESENCE_ABSENT,
    PRESENCE_LIVE,
    PRESENCE_SPOOF,
    PRESENCE_UNKNOWN,
)
from vision_lab.group_loop import run_group_recognition_lab
from vision_lab.presence import (
    SilhouetteObservation,
    WebcamObservation,
    WebcamPresenceAnalyzer,
)
from vision_lab.solo_loop import SoloWebcamTeachingLoop


def test_face_and_attention_become_verified_live_payload():
    decision = WebcamPresenceAnalyzer().analyze(
        WebcamObservation(
            participant_id="p1",
            face_count=1,
            attention_score=0.8,
            gaze_frontal=0.7,
            observed_at="2026-08-04T17:00:00+00:00",
        )
    )

    assert decision.verified_live is True
    assert decision.liveness_state == PRESENCE_LIVE
    assert decision.reason == "verified"
    assert decision.to_presence_payload() == {
        "participant_id": "p1",
        "present": True,
        "face_count": 1,
        "liveness_state": "live",
        "liveness_score": pytest.approx(0.755),
        "reason": "verified",
        "source": "vision-lab",
        "observed_at": "2026-08-04T17:00:00+00:00",
    }


def test_silhouette_without_face_is_present_but_not_liveness_verified():
    decision = WebcamPresenceAnalyzer().analyze(
        WebcamObservation(
            participant_id="p2",
            face_count=0,
            silhouette=SilhouetteObservation(
                confidence=0.9,
                area_ratio=0.22,
                motion_score=0.4,
                centeredness=0.8,
            ),
        )
    )

    assert decision.present is True
    assert decision.face_count == 0
    assert decision.liveness_state == PRESENCE_UNKNOWN
    assert decision.reason == "silhouette_without_face"
    assert decision.silhouette_state == "person_without_face"


def test_no_face_or_silhouette_marks_absent():
    decision = WebcamPresenceAnalyzer().analyze(
        WebcamObservation(participant_id="p3")
    )

    assert decision.present is False
    assert decision.liveness_state == PRESENCE_ABSENT
    assert decision.reason == "no_person"


def test_too_many_faces_flags_spoof_for_group_class():
    decision = WebcamPresenceAnalyzer(max_faces_allowed=1).analyze(
        WebcamObservation(participant_id="p4", face_count=2)
    )

    assert decision.present is True
    assert decision.verified_live is False
    assert decision.liveness_state == PRESENCE_SPOOF
    assert decision.reason == "too_many_faces"


def test_group_lab_builds_presence_reports_and_video_events():
    result = run_group_recognition_lab(
        room_id="class-abc",
        observations=[
            WebcamObservation(
                participant_id="student-1",
                face_count=1,
                attention_score=0.9,
                gaze_frontal=0.9,
            ),
            WebcamObservation(participant_id="student-2"),
        ],
    )

    assert result.summary() == {
        "room_id": "class-abc",
        "ticks": 2,
        "verified_live": 1,
        "silhouette_only": 0,
        "absent": 1,
    }
    assert result.reports[0].endpoint_path() == (
        "/api/live-rooms/class-abc/presence-report"
    )
    assert result.video_events()[1].attention == 0.0
    assert result.video_events()[1].looking_away is True


def test_solo_loop_uses_safe_fallback_when_xai_is_not_configured():
    turn = SoloWebcamTeachingLoop().handle_observation(
        WebcamObservation(
            participant_id="solo-1",
            silhouette=SilhouetteObservation(confidence=0.8, area_ratio=0.2),
        ),
        learner_name="Theo",
    )

    assert turn.decision.reason == "silhouette_without_face"
    assert "cannot see your face" in turn.speakable_chunks[0]
    assert "Learner: Theo" in turn.messages[1]["content"]
