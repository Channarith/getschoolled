"""Come get jiggy with me — dance move catalog and scoring."""

from __future__ import annotations

import random

from theodore_webcam_lab.dance_moves import (
    DANCE_MOVE_IDS,
    DANCE_MOVES,
    JIGGY_BEAT_MS,
    JIGGY_MATCH_THRESHOLD,
    JIGGY_SEQUENCE_LEN,
    jiggy_target_duration_ms,
    move_confidence,
    move_encouragement,
    move_prompt,
    random_jiggy_sequence,
    sequence_progress,
)
from theodore_webcam_lab.types import WebcamSignal


def _signal(**kwargs) -> WebcamSignal:
    base = dict(
        participant_id="learner",
        timestamp_ms=0,
        face_count=1,
        liveness_state="live",
        foreground_ratio=0.3,
        motion_score=0.2,
    )
    base.update(kwargs)
    return WebcamSignal(**base)


def test_dance_move_catalog_is_kid_safe_and_complete():
    assert len(DANCE_MOVE_IDS) >= 10
    for move_id in DANCE_MOVE_IDS:
        move = DANCE_MOVES[move_id]
        assert move.move_id == move_id
        assert move.prompt.endswith("!")
        assert move.encourage


def test_move_prompt_and_encouragement():
    assert move_prompt("shake_shake") == "Shake shake!"
    assert move_encouragement("high_five") == "High five hero!"


def test_random_jiggy_sequence_is_unique_and_bounded():
    rng = random.Random(7)
    seq = random_jiggy_sequence(length=JIGGY_SEQUENCE_LEN, rng=rng)
    assert len(seq) == JIGGY_SEQUENCE_LEN
    assert len(set(seq)) == JIGGY_SEQUENCE_LEN


def test_move_confidence_uses_real_webcam_signals():
    shake = _signal(motion_score=0.9, fidget_score=0.85, hand_gesture_energy=0.4)
    assert move_confidence("shake_shake", shake) >= JIGGY_MATCH_THRESHOLD

    spin = _signal(motion_score=0.5, head_pose_yaw=20.0, body_motion_score=0.4)
    assert move_confidence("spin", spin) >= JIGGY_MATCH_THRESHOLD

    snake = _signal(hand_gesture_energy=0.7, motion_score=0.3, wand_spell_label="loop")
    assert move_confidence("snake_hands", snake, spell="loop") >= JIGGY_MATCH_THRESHOLD

    quiet = _signal(motion_score=0.05, fidget_score=0.02)
    assert move_confidence("shake_shake", quiet) < JIGGY_MATCH_THRESHOLD


def test_sequence_progress_matches_moves_in_order():
    expected = ["shake_shake", "bop_head", "dance", "wave_hello"]
    signals = [
        _signal(
            timestamp_ms=0,
            dance_move_matched="shake_shake",
            motion_score=0.9,
            fidget_score=0.8,
        ),
        _signal(
            timestamp_ms=600,
            dance_move_matched="bop_head",
            face_motion_energy=0.85,
            motion_score=0.5,
        ),
        _signal(
            timestamp_ms=1200,
            dance_move_matched="dance",
            motion_score=0.7,
            hand_gesture_energy=0.75,
            face_motion_energy=0.6,
            excitement_score=0.5,
        ),
        _signal(
            timestamp_ms=1800,
            dance_move_matched="wave_hello",
            hand_gesture_energy=0.8,
            motion_score=0.4,
        ),
    ]
    count, matched = sequence_progress(signals, expected)
    assert count == 4
    assert matched == expected


def test_sequence_progress_ignores_wrong_move_labels():
    expected = ["high_five", "get_low"]
    signals = [
        _signal(
            timestamp_ms=0,
            dance_move_matched="dance",
            motion_score=0.9,
            hand_gesture_energy=0.9,
        ),
        _signal(
            timestamp_ms=800,
            dance_move_matched="high_five",
            motion_score=0.8,
            hand_gesture_energy=0.85,
            excitement_score=0.4,
        ),
    ]
    count, matched = sequence_progress(signals, expected)
    assert count == 1
    assert matched == ["high_five"]


def test_jiggy_target_duration_scales_with_move_count():
    assert jiggy_target_duration_ms(4) == 4 * JIGGY_BEAT_MS
    assert jiggy_target_duration_ms(1) == JIGGY_BEAT_MS
