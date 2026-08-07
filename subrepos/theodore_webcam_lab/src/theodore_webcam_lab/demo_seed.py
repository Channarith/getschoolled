"""Shared demo-session frame payloads for the live monitor.

Used by ``scripts/seed_demo_session.py`` and the in-page demo buttons.

Two scenarios:
  * ``solo``  — one learner (matches a single physical webcam). Default for the
    primary "Load solo demo" button.
  * ``group`` — three simulated students (healthy / cheating / silhouette) so the
    group dashboard can show those windows. This is synthetic roster data, not
    three webcams on your machine.
"""

from __future__ import annotations

from typing import Any, Literal

DEFAULT_SESSION_ID = "demo-session"
DEMO_PARTICIPANTS = ("student-a", "student-b", "student-c")
SOLO_PARTICIPANT_ID = "learner"
DemoScenario = Literal["solo", "group"]

# 10 s of simulated time per frame so the default long gaze-away grace can trip
# in the group cheating demo without waiting through dozens of one-second ticks.
DEMO_MS_PER_FRAME = 10_000


def build_demo_payload(
    *,
    session_id: str,
    step: int,
    degraded: bool = False,
    scenario: DemoScenario = "group",
) -> dict[str, Any]:
    if scenario == "solo":
        return _build_solo_payload(session_id=session_id, step=step, degraded=degraded)
    return _build_group_payload(session_id=session_id, step=step, degraded=degraded)


def _build_solo_payload(
    *, session_id: str, step: int, degraded: bool
) -> dict[str, Any]:
    """One student — same shape as a real solo webcam session."""
    timestamp_ms = 10_000 + step * DEMO_MS_PER_FRAME
    mic_present = step % 3 != 0
    if degraded:
        signal = {
            "participant_id": SOLO_PARTICIPANT_ID,
            "timestamp_ms": timestamp_ms,
            "face_count": 1,
            "liveness_state": "live",
            "foreground_ratio": 0.40,
            "motion_score": 0.2,
            "face_size_ratio": 0.085,
            "light_quality_score": 0.18,
            "mean_luminance": 0.12,
            "image_detection_confidence": 0.52,
            "sharpness_score": 0.14,
            "edge_density": 0.010,
            "expression_label": "neutral",
            "gaze_frontal": 0.75,
            "gaze_down_score": 0.12,
            "microphone_input_level_score": 0.28 if mic_present else None,
            "noise_filter_effectiveness_score": 0.30 if mic_present else None,
            "audio_noise_level_db": 66.0 if mic_present else None,
            "audio_snr_db": 6.0 if mic_present else None,
        }
    else:
        signal = {
            "participant_id": SOLO_PARTICIPANT_ID,
            "timestamp_ms": timestamp_ms,
            "face_count": 1,
            "liveness_state": "live",
            "foreground_ratio": 0.42,
            "motion_score": 0.2,
            "face_size_ratio": 0.19,
            "light_quality_score": round(0.72 + ((step % 6) - 2) * 0.02, 3),
            "image_detection_confidence": 0.91,
            "expression_label": "happy" if step % 2 == 0 else "neutral",
            "gaze_frontal": 0.82,
            "gaze_down_score": 0.10,
            "microphone_input_level_score": 0.84 if mic_present else None,
            "noise_filter_effectiveness_score": 0.80 if mic_present else None,
            "audio_noise_level_db": 35.0 if mic_present else None,
            "audio_snr_db": 24.0 if mic_present else None,
        }
    return {
        "session_id": session_id,
        "mode": "solo",
        "scenario": "solo",
        "expected_participant_ids": [SOLO_PARTICIPANT_ID],
        "signals": [signal],
    }


def _build_group_payload(
    *, session_id: str, step: int, degraded: bool
) -> dict[str, Any]:
    timestamp_ms = 10_000 + step * DEMO_MS_PER_FRAME
    # Drop student-a's audio every 3rd frame so mic charts show real gaps.
    mic_present = step % 3 != 0
    if degraded:
        return {
            "session_id": session_id,
            "mode": "group",
            "scenario": "group",
            "expected_participant_ids": list(DEMO_PARTICIPANTS),
            "signals": [
                {
                    "participant_id": "student-a",
                    "timestamp_ms": timestamp_ms,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.40,
                    "motion_score": 0.2,
                    "face_size_ratio": 0.085,
                    "light_quality_score": 0.18,
                    "mean_luminance": 0.12,
                    "image_detection_confidence": 0.52,
                    "sharpness_score": 0.14,
                    "edge_density": 0.010,
                    "expression_label": "neutral",
                    "microphone_input_level_score": 0.28,
                    "noise_filter_effectiveness_score": 0.30,
                    "audio_noise_level_db": 66.0,
                    "audio_snr_db": 6.0,
                },
                {
                    "participant_id": "student-b",
                    "timestamp_ms": timestamp_ms,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.35,
                    "motion_score": 0.28,
                    "face_size_ratio": 0.30,
                    "light_quality_score": 0.90,
                    "mean_luminance": 0.88,
                    "image_detection_confidence": 0.80,
                    "sharpness_score": 0.55,
                    "edge_density": 0.12,
                    "expression_label": "neutral",
                    "microphone_input_level_score": 0.70,
                    "noise_filter_effectiveness_score": 0.62,
                    "audio_noise_level_db": 44.0,
                    "audio_snr_db": 18.0,
                },
                _silhouette_signal(timestamp_ms),
            ],
        }

    student_b_mic = round(0.45 + (step % 5) * 0.05, 3)
    return {
        "session_id": session_id,
        "mode": "group",
        "scenario": "group",
        "expected_participant_ids": list(DEMO_PARTICIPANTS),
        "signals": [
            {
                "participant_id": "student-a",
                "timestamp_ms": timestamp_ms,
                "face_count": 1,
                "liveness_state": "live",
                "foreground_ratio": 0.42,
                "motion_score": 0.2,
                "face_size_ratio": 0.19,
                "light_quality_score": round(0.72 + ((step % 6) - 2) * 0.02, 3),
                "image_detection_confidence": 0.91,
                "expression_label": "happy" if step % 2 == 0 else "neutral",
                "gaze_frontal": 0.82,
                "gaze_down_score": 0.10,
                "microphone_input_level_score": 0.84 if mic_present else None,
                "noise_filter_effectiveness_score": 0.80 if mic_present else None,
                "audio_noise_level_db": 35.0 if mic_present else None,
                "audio_snr_db": 24.0 if mic_present else None,
            },
            {
                "participant_id": "student-b",
                "timestamp_ms": timestamp_ms,
                "face_count": 1,
                "liveness_state": "live",
                "foreground_ratio": 0.35,
                "motion_score": 0.28,
                "face_size_ratio": 0.12,
                "light_quality_score": round(0.40 + ((step % 4) - 1) * 0.02, 3),
                "mean_luminance": 0.38,
                "sharpness_score": 0.35,
                "edge_density": 0.04,
                "image_detection_confidence": 0.74,
                "expression_label": "neutral",
                "gaze_frontal": 0.22,
                "gaze_down_score": 0.86,
                "phone_visible": True,
                "typing_activity_score": 0.78,
                "keyboard_typing_audio_score": 0.80,
                "microphone_input_level_score": student_b_mic,
                "noise_filter_effectiveness_score": round(0.50 + (step % 4) * 0.04, 3),
                "audio_noise_level_db": 49.0,
                "audio_snr_db": 12.0,
            },
            _silhouette_signal(timestamp_ms),
        ],
    }


def _silhouette_signal(timestamp_ms: int) -> dict[str, Any]:
    """No face, nearly full foreground, low motion — trips silhouette detection."""
    return {
        "participant_id": "student-c",
        "timestamp_ms": timestamp_ms,
        "face_count": 0,
        "liveness_state": "unknown",
        "foreground_ratio": 0.97,
        "motion_score": 0.02,
        "light_quality_score": 0.40,
        "image_detection_confidence": 0.35,
        "expression_label": "unknown",
    }
