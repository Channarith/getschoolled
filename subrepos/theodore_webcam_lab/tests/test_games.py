from __future__ import annotations

from theodore_webcam_lab.analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from theodore_webcam_lab.games import WebcamLearningGameEngine
from theodore_webcam_lab.types import ClassMode, WebcamGameType, WebcamSignal


def test_focus_streak_challenge_passes_with_clean_attention():
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(gaze_away_grace_ms=45_000))
    engine = WebcamLearningGameEngine(analyzer)
    challenge = engine.create_challenge(
        session_id="game-1",
        mode=ClassMode.SOLO,
        learning_prompt="Explain Newton's first law.",
        preferred_game_type=WebcamGameType.FOCUS_STREAK,
    )
    result = engine.score_attempt(
        challenge_id=challenge.challenge_id,
        session_id="game-1",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=0,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.2,
                gaze_frontal=0.9,
                gaze_down_score=0.1,
            ),
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=8_500,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.2,
                gaze_frontal=0.9,
                gaze_down_score=0.1,
            ),
        ],
    )
    assert result.passed is True
    assert result.score_delta == 12
    assert result.total_score == 12
    assert result.streak == 1


def test_integrity_challenge_fails_with_cheating_signals():
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(gaze_away_grace_ms=1_000))
    engine = WebcamLearningGameEngine(analyzer)
    challenge = engine.create_challenge(
        session_id="game-2",
        mode=ClassMode.SOLO,
        learning_prompt="State the capital of France.",
        preferred_game_type=WebcamGameType.INTEGRITY_GUARD,
    )
    result = engine.score_attempt(
        challenge_id=challenge.challenge_id,
        session_id="game-2",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.2,
                gaze_frontal=0.1,
                gaze_down_score=0.8,
                keyboard_typing_audio_score=0.9,
            ),
            WebcamSignal(
                participant_id="learner",
                timestamp_ms=8_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.3,
                motion_score=0.2,
                gaze_frontal=0.1,
                gaze_down_score=0.8,
                keyboard_typing_audio_score=0.9,
            ),
        ],
    )
    assert result.passed is False
    assert result.score_delta == -3
    assert result.total_score == 0
    assert result.streak == 0
    assert result.evaluation.suspected_cheating_participant_ids == ["learner"]
