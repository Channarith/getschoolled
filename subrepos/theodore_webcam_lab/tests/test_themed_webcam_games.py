"""Themed webcam game engine scoring."""

from theodore_webcam_lab.analysis import WebcamSessionAnalyzer
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
        smile_score=0.7,
        accessory_count=2,
    )
    base.update(kwargs)
    return WebcamSignal(**base)


def test_halloween_wand_challenge_passes_with_spell_label():
    engine = WebcamLearningGameEngine(WebcamSessionAnalyzer())
    challenge = engine.create_challenge(
        session_id="wand-1",
        mode=ClassMode.SOLO,
        learning_prompt="Cast a spell!",
        theme="halloween",
    )
    assert challenge.game_type is WebcamGameType.HALLOWEEN_WAND
    result = engine.score_attempt(
        challenge_id=challenge.challenge_id,
        session_id="wand-1",
        mode=ClassMode.SOLO,
        signals=[
            _signal(timestamp_ms=0, wand_spell_label="swish"),
            _signal(timestamp_ms=4500, wand_spell_label="swish"),
        ],
    )
    assert result.passed is True
    assert result.spell_detected == "swish"


def test_cute_enough_updates_leaderboard():
    engine = WebcamLearningGameEngine(WebcamSessionAnalyzer())
    challenge = engine.create_challenge(
        session_id="cute-1",
        mode=ClassMode.SOLO,
        learning_prompt="Show your style!",
        theme="cute",
    )
    assert challenge.game_type is WebcamGameType.CUTE_ENOUGH
    result = engine.score_attempt(
        challenge_id=challenge.challenge_id,
        session_id="cute-1",
        mode=ClassMode.SOLO,
        signals=[
            _signal(timestamp_ms=0, cute_confidence_score=78),
            _signal(timestamp_ms=4500, cute_confidence_score=82),
        ],
    )
    assert result.passed is True
    assert result.cute_score == 82
    board = engine.leaderboard("cute-1")
    assert board[0]["participant_id"] == "learner"
    assert board[0]["cute_score"] == 82
