"""Jiggy dance webcam game engine scoring."""

from __future__ import annotations

from theodore_webcam_lab.analysis import WebcamSessionAnalyzer
from theodore_webcam_lab.dance_moves import jiggy_target_duration_ms
from theodore_webcam_lab.games import WebcamLearningGameEngine
from theodore_webcam_lab.types import ClassMode, WebcamGameType, WebcamSignal


def _signal(**kwargs) -> WebcamSignal:
    base = dict(
        participant_id="learner",
        timestamp_ms=0,
        face_count=1,
        liveness_state="live",
        foreground_ratio=0.3,
        motion_score=0.2,
        gaze_frontal=0.85,
    )
    base.update(kwargs)
    return WebcamSignal(**base)


def test_jiggy_theme_creates_dance_challenge_with_sequence():
    engine = WebcamLearningGameEngine(WebcamSessionAnalyzer())
    challenge = engine.create_challenge(
        session_id="jiggy-1",
        mode=ClassMode.SOLO,
        learning_prompt="Come get jiggy with me!",
        theme="jiggy",
    )
    assert challenge.game_type is WebcamGameType.JIGGY_DANCE
    assert challenge.title == "Come get jiggy with me!"
    assert len(challenge.move_sequence) == 4
    assert challenge.target_duration_ms == jiggy_target_duration_ms(len(challenge.move_sequence))


def test_jiggy_challenge_passes_when_all_moves_matched():
    engine = WebcamLearningGameEngine(WebcamSessionAnalyzer())
    challenge = engine.create_challenge(
        session_id="jiggy-2",
        mode=ClassMode.SOLO,
        learning_prompt="Dance!",
        theme="jiggy",
    )
    moves = challenge.move_sequence
    duration = challenge.target_duration_ms
    signals = []
    for idx, move_id in enumerate(moves):
        kwargs = dict(
            timestamp_ms=idx * 900,
            dance_move_matched=move_id,
            dance_move_index=idx,
            motion_score=0.85,
            fidget_score=0.8,
            hand_gesture_energy=0.75,
            face_motion_energy=0.7,
            excitement_score=0.6,
            head_pose_yaw=18.0,
            head_pose_pitch=12.0,
            head_pose_roll=14.0,
            wand_spell_label="loop" if move_id == "snake_hands" else None,
        )
        signals.append(_signal(**kwargs))
    signals[-1] = signals[-1].model_copy(update={"timestamp_ms": duration})

    result = engine.score_attempt(
        challenge_id=challenge.challenge_id,
        session_id="jiggy-2",
        mode=ClassMode.SOLO,
        signals=signals,
    )
    assert result.passed is True
    assert "Jiggy complete!" in result.feedback
    assert result.score_delta == 10 + len(moves) * 2
    assert result.theme == "jiggy"


def test_jiggy_challenge_fails_when_duration_too_short():
    engine = WebcamLearningGameEngine(WebcamSessionAnalyzer())
    challenge = engine.create_challenge(
        session_id="jiggy-3",
        mode=ClassMode.SOLO,
        learning_prompt="Dance!",
        theme="jiggy",
    )
    result = engine.score_attempt(
        challenge_id=challenge.challenge_id,
        session_id="jiggy-3",
        mode=ClassMode.SOLO,
        signals=[
            _signal(timestamp_ms=0, dance_move_matched=challenge.move_sequence[0], motion_score=0.9),
            _signal(timestamp_ms=500, dance_move_matched=challenge.move_sequence[0], motion_score=0.9),
        ],
    )
    assert result.passed is False
    assert "Keep going" in result.feedback


def test_jiggy_partial_moves_give_encouraging_feedback():
    engine = WebcamLearningGameEngine(WebcamSessionAnalyzer())
    challenge = engine.create_challenge(
        session_id="jiggy-4",
        mode=ClassMode.SOLO,
        learning_prompt="Dance!",
        theme="jiggy",
    )
    move_id = challenge.move_sequence[0]
    duration = challenge.target_duration_ms
    strong = dict(
        dance_move_matched=move_id,
        motion_score=0.95,
        fidget_score=0.9,
        hand_gesture_energy=0.9,
        face_motion_energy=0.9,
        excitement_score=0.85,
        head_pose_yaw=22.0,
        head_pose_pitch=15.0,
        head_pose_roll=18.0,
        body_motion_score=0.8,
        wand_spell_label="loop" if move_id == "snake_hands" else None,
    )
    result = engine.score_attempt(
        challenge_id=challenge.challenge_id,
        session_id="jiggy-4",
        mode=ClassMode.SOLO,
        signals=[
            _signal(timestamp_ms=0, **strong),
            _signal(timestamp_ms=duration, **strong),
        ],
    )
    assert result.passed is False
    assert "Nice dancing" in result.feedback or "1/" in result.feedback
