"""Distance × gaze × residual attention formula."""

from __future__ import annotations

from theodore_webcam_lab.analysis import WebcamSessionAnalyzer
from theodore_webcam_lab.attention_formula import (
    DEFAULT_ATTENTION_FORMULA,
    evaluate_attention_formula,
    residual_floor_for_distance,
)
from theodore_webcam_lab.types import ClassMode, WebcamSignal


def test_residual_floors_match_distance_bands():
    assert residual_floor_for_distance(0.30) == (0.30, -2.0, False)
    assert residual_floor_for_distance(0.40) == (0.40, -8.0, False)
    assert residual_floor_for_distance(0.50) == (0.50, -9.0, False)
    assert residual_floor_for_distance(0.55) == (0.55, -9.0, False)
    assert residual_floor_for_distance(0.60) == (0.60, -9.0, False)
    assert residual_floor_for_distance(0.70) == (0.70, -12.0, False)
    assert residual_floor_for_distance(0.71)[2] is True
    assert residual_floor_for_distance(1.2)[2] is True


def test_formula_trips_when_gaze_holds_and_residual_clears_floor():
    ok = evaluate_attention_formula(
        distance_m=0.30,
        residual_deg=-1.0,
        gaze_away_for_ms=4_500,
        gaze_channels=("gaze_down",),
    )
    assert ok.inattentive_or_cheating is True
    assert "attention_formula" in ok.reasons

    early = evaluate_attention_formula(
        distance_m=0.30,
        residual_deg=-1.0,
        gaze_away_for_ms=2_000,
        gaze_channels=("gaze_down",),
    )
    assert early.inattentive_or_cheating is False

    looking_way_up = evaluate_attention_formula(
        distance_m=0.30,
        residual_deg=-5.0,  # below floor -2
        gaze_away_for_ms=5_000,
        gaze_channels=("gaze_up",),
    )
    assert looking_way_up.inattentive_or_cheating is False


def test_too_far_asks_to_move_closer():
    result = evaluate_attention_formula(
        distance_m=0.85,
        residual_deg=0.0,
        gaze_away_for_ms=0,
        gaze_channels=(),
    )
    assert result.too_far is True
    assert "move closer" in result.coach_message.lower()


def _sig(**kwargs) -> WebcamSignal:
    base = dict(
        participant_id="p1",
        timestamp_ms=kwargs.pop("timestamp_ms", 10_000),
        face_count=1,
        liveness_state="live",
        detector_source="face_mesh",
        gaze_frontal=0.9,
        gaze_down_score=0.0,
        distance_from_camera_m=0.50,
        stare_residual_deg=0.0,
        light_quality_score=0.9,
        mean_luminance=0.45,
        sharpness_score=0.8,
        image_detection_confidence=0.9,
    )
    base.update(kwargs)
    return WebcamSignal(**base)


def test_analyzer_pauses_when_too_far():
    analyzer = WebcamSessionAnalyzer()
    result = analyzer.evaluate(
        session_id="far",
        mode=ClassMode.SOLO,
        signals=[_sig(distance_from_camera_m=0.95, face_size_ratio=0.12)],
    )
    assert result.participants[0].too_far_for_class is True
    assert result.training_paused is True
    assert result.pause_reason == "too_far_from_camera"


def test_analyzer_flags_attention_formula_after_gaze_hold():
    analyzer = WebcamSessionAnalyzer()
    # Warm-up present frame.
    analyzer.evaluate(
        session_id="attn",
        mode=ClassMode.SOLO,
        signals=[_sig(timestamp_ms=1_000, gaze_down_score=0.0)],
    )
    # Start looking down.
    analyzer.evaluate(
        session_id="attn",
        mode=ClassMode.SOLO,
        signals=[
            _sig(
                timestamp_ms=2_000,
                gaze_down_score=0.6,
                gaze_frontal=0.2,
                stare_residual_deg=0.0,
                distance_from_camera_m=0.50,
            )
        ],
    )
    # Hold past 4s with residual clearing the 0.5m floor (-9).
    result = analyzer.evaluate(
        session_id="attn",
        mode=ClassMode.SOLO,
        signals=[
            _sig(
                timestamp_ms=7_000,
                gaze_down_score=0.7,
                gaze_frontal=0.15,
                stare_residual_deg=-5.0,
                distance_from_camera_m=0.50,
            )
        ],
    )
    p = result.participants[0]
    assert p.attention_formula_triggered is True
    assert p.suspected_cheating is True
    assert result.training_paused is True
    assert result.pause_reason == "attention_integrity"
    assert p.attention_band_m == 0.50
    assert p.attention_residual_floor_deg == -9.0


def test_analyzer_pauses_on_pitch_dark_and_asks_for_light():
    analyzer = WebcamSessionAnalyzer()
    # First dark frame starts the quality timer.
    analyzer.evaluate(
        session_id="dark",
        mode=ClassMode.SOLO,
        signals=[
            _sig(
                timestamp_ms=1_000,
                mean_luminance=0.03,
                light_quality_score=0.05,
                underexposed_ratio=0.9,
            )
        ],
    )
    result = analyzer.evaluate(
        session_id="dark",
        mode=ClassMode.SOLO,
        signals=[
            _sig(
                timestamp_ms=1_000 + DEFAULT_ATTENTION_FORMULA.quality_pause_hold_ms + 100,
                mean_luminance=0.03,
                light_quality_score=0.05,
                underexposed_ratio=0.9,
            )
        ],
    )
    assert result.participants[0].pitch_dark is True
    assert result.participants[0].camera_quality_blocking is True
    assert result.training_paused is True
    assert result.pause_reason == "pitch_dark_needs_light"
