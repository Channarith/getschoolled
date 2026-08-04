from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .analysis import WebcamSessionAnalyzer
from .types import (
    ClassEvaluation,
    ClassMode,
    WebcamGameResult,
    WebcamGameType,
    WebcamLearningChallenge,
    WebcamSignal,
)


@dataclass
class _GameState:
    score: int = 0
    streak: int = 0
    issued: int = 0
    active_challenge: WebcamLearningChallenge | None = None


class WebcamLearningGameEngine:
    """Generates and scores webcam-based learning reinforcement challenges."""

    def __init__(self, analyzer: WebcamSessionAnalyzer) -> None:
        self._analyzer = analyzer
        self._sessions: dict[str, _GameState] = {}
        self._rotation = [
            WebcamGameType.FOCUS_STREAK,
            WebcamGameType.CONFIDENCE_SMILE,
            WebcamGameType.INTEGRITY_GUARD,
        ]

    def create_challenge(
        self,
        *,
        session_id: str,
        mode: ClassMode,
        learning_prompt: str,
        participant_ids: list[str] | None = None,
        preferred_game_type: WebcamGameType | None = None,
    ) -> WebcamLearningChallenge:
        state = self._sessions.setdefault(session_id, _GameState())
        state.issued += 1
        if preferred_game_type is None:
            game_type = self._rotation[(state.issued - 1) % len(self._rotation)]
        else:
            game_type = preferred_game_type

        challenge = self._build_challenge(
            session_id=session_id,
            mode=mode,
            game_type=game_type,
            learning_prompt=learning_prompt,
            participant_ids=participant_ids or [],
        )
        state.active_challenge = challenge
        return challenge

    def score_attempt(
        self,
        *,
        challenge_id: str,
        session_id: str,
        mode: ClassMode,
        signals: list[WebcamSignal],
        expected_participant_ids: list[str] | None = None,
    ) -> WebcamGameResult:
        state = self._sessions.setdefault(session_id, _GameState())
        challenge = state.active_challenge
        if challenge is None or challenge.challenge_id != challenge_id:
            raise ValueError("challenge not found or no longer active")

        evaluation = self._analyzer.evaluate(
            session_id=session_id,
            mode=mode,
            signals=signals,
            expected_participant_ids=expected_participant_ids or challenge.participant_ids,
        )

        passed, feedback = self._evaluate_challenge(
            challenge=challenge,
            evaluation=evaluation,
            signals=signals,
        )
        score_delta = 12 if passed else -3
        state.score = max(0, state.score + score_delta)
        state.streak = (state.streak + 1) if passed else 0
        state.active_challenge = None
        return WebcamGameResult(
            challenge_id=challenge.challenge_id,
            passed=passed,
            score_delta=score_delta,
            total_score=state.score,
            streak=state.streak,
            feedback=feedback,
            evaluation=evaluation,
        )

    def _build_challenge(
        self,
        *,
        session_id: str,
        mode: ClassMode,
        game_type: WebcamGameType,
        learning_prompt: str,
        participant_ids: list[str],
    ) -> WebcamLearningChallenge:
        if game_type is WebcamGameType.FOCUS_STREAK:
            return WebcamLearningChallenge(
                challenge_id=f"challenge-{uuid4().hex[:12]}",
                session_id=session_id,
                mode=mode,
                game_type=game_type,
                title="Focus Streak Challenge",
                instruction="Keep your eyes on the learning screen while answering.",
                learning_prompt=learning_prompt,
                target_duration_ms=8_000,
                participant_ids=participant_ids,
            )
        if game_type is WebcamGameType.CONFIDENCE_SMILE:
            return WebcamLearningChallenge(
                challenge_id=f"challenge-{uuid4().hex[:12]}",
                session_id=session_id,
                mode=mode,
                game_type=game_type,
                title="Confidence Smile Challenge",
                instruction="Show a confident or happy expression after your answer.",
                learning_prompt=learning_prompt,
                target_duration_ms=2_000,
                participant_ids=participant_ids,
            )
        return WebcamLearningChallenge(
            challenge_id=f"challenge-{uuid4().hex[:12]}",
            session_id=session_id,
            mode=mode,
            game_type=game_type,
            title="Integrity Guard Challenge",
            instruction=(
                "Answer from memory while staying focused on camera with "
                "no phone/typing behavior."
            ),
            learning_prompt=learning_prompt,
            target_duration_ms=6_000,
            participant_ids=participant_ids,
        )

    def _evaluate_challenge(
        self,
        *,
        challenge: WebcamLearningChallenge,
        evaluation: ClassEvaluation,
        signals: list[WebcamSignal],
    ) -> tuple[bool, str]:
        if not evaluation.participants:
            return False, "No participants were detected for this challenge attempt."
        if evaluation.training_paused:
            reason = evaluation.pause_reason or "training_paused"
            return False, f"Training is paused ({reason}); challenge attempt is blocked."

        timestamps = [s.timestamp_ms for s in signals]
        observed_ms = (max(timestamps) - min(timestamps)) if len(timestamps) >= 2 else 0
        if challenge.game_type is WebcamGameType.FOCUS_STREAK:
            if observed_ms < challenge.target_duration_ms:
                return False, (
                    "Stay focused longer to complete the challenge "
                    f"({observed_ms}ms/{challenge.target_duration_ms}ms)."
                )
            if evaluation.suspected_cheating_participant_ids:
                return False, "Focus challenge failed due to possible cheating signals."
            any_eyes_away = any(p.eyes_away_for_ms > 0 for p in evaluation.participants)
            if any_eyes_away:
                return False, "Keep eyes on screen for the full focus streak."
            return True, "Great focus control — challenge passed."

        if challenge.game_type is WebcamGameType.CONFIDENCE_SMILE:
            if not evaluation.happy_participant_ids:
                return False, "Show a confident/happy expression while answering."
            return True, "Strong confidence signal detected — challenge passed."

        # Integrity guard
        if observed_ms < challenge.target_duration_ms:
            return False, (
                "Continue the integrity challenge a bit longer "
                f"({observed_ms}ms/{challenge.target_duration_ms}ms)."
            )
        if evaluation.suspected_cheating_participant_ids:
            return False, "Integrity challenge failed due to suspicious signals."
        return True, "Integrity challenge passed with clean attention signals."
