from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from .analysis import WebcamSessionAnalyzer
from .cute_score import (
    CUTE_PASS_THRESHOLD,
    accessory_count_from_ids,
    cute_confidence_score,
    cute_encouragement,
)
from .dance_moves import (
    jiggy_target_duration_ms,
    move_encouragement,
    move_prompt,
    random_jiggy_sequence,
    sequence_progress,
)
from .themed_games import (
    recognize_wand_spell,
    theme_spec,
    trail_heart_shape,
)
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
    cute_leaderboard: dict[str, int] = field(default_factory=dict)
    last_theme: str | None = None


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
        theme: str | None = None,
    ) -> WebcamLearningChallenge:
        state = self._sessions.setdefault(session_id, _GameState())
        state.issued += 1
        spec = theme_spec(theme)
        state.last_theme = spec.theme_id
        if preferred_game_type is None and spec.game_type is not None:
            game_type = spec.game_type
        elif preferred_game_type is None:
            game_type = self._rotation[(state.issued - 1) % len(self._rotation)]
        else:
            game_type = preferred_game_type

        challenge = self._build_challenge(
            session_id=session_id,
            mode=mode,
            game_type=game_type,
            learning_prompt=learning_prompt,
            participant_ids=participant_ids or [],
            theme=spec.theme_id,
        )
        state.active_challenge = challenge
        return challenge

    def leaderboard(self, session_id: str) -> list[dict[str, object]]:
        state = self._sessions.get(session_id)
        if state is None or not state.cute_leaderboard:
            return []
        ranked = sorted(
            state.cute_leaderboard.items(),
            key=lambda item: (-item[1], item[0]),
        )
        return [
            {"rank": idx + 1, "participant_id": pid, "cute_score": score}
            for idx, (pid, score) in enumerate(ranked)
        ]

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

        passed, feedback, cute_score, spell_detected, matched_moves, skipped_moves = (
            self._evaluate_challenge(
                challenge=challenge,
                evaluation=evaluation,
                signals=signals,
                state=state,
            )
        )
        score_delta = 12 if passed else -3
        if challenge.game_type is WebcamGameType.CUTE_ENOUGH and cute_score is not None:
            score_delta = max(0, cute_score // 8) if passed else -2
        if challenge.game_type is WebcamGameType.JIGGY_DANCE:
            score_delta = 4 * len(matched_moves) + (2 if passed else 0)
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
            cute_score=cute_score,
            leaderboard=self.leaderboard(session_id),
            theme=state.last_theme,
            spell_detected=spell_detected,
            matched_moves=matched_moves,
            skipped_moves=skipped_moves,
        )

    def _build_challenge(
        self,
        *,
        session_id: str,
        mode: ClassMode,
        game_type: WebcamGameType,
        learning_prompt: str,
        participant_ids: list[str],
        theme: str = "classic",
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
        if game_type is WebcamGameType.HALLOWEEN_WAND:
            return WebcamLearningChallenge(
                challenge_id=f"challenge-{uuid4().hex[:12]}",
                session_id=session_id,
                mode=mode,
                game_type=game_type,
                title="Halloween Wand Spell",
                instruction=(
                    "Trace a wand spell with your index finger: swish sideways, "
                    "flick up/down, or loop a circle."
                ),
                learning_prompt=learning_prompt,
                target_duration_ms=4_000,
                participant_ids=participant_ids,
            )
        if game_type is WebcamGameType.CHRISTMAS_GINGERBREAD:
            return WebcamLearningChallenge(
                challenge_id=f"challenge-{uuid4().hex[:12]}",
                session_id=session_id,
                mode=mode,
                game_type=game_type,
                title="Gingerbread House Smile",
                instruction=(
                    "Decorate the gingerbread house with your happiest smile "
                    "while facing the camera."
                ),
                learning_prompt=learning_prompt,
                target_duration_ms=3_000,
                participant_ids=participant_ids,
            )
        if game_type is WebcamGameType.VALENTINES_HEARTS:
            return WebcamLearningChallenge(
                challenge_id=f"challenge-{uuid4().hex[:12]}",
                session_id=session_id,
                mode=mode,
                game_type=game_type,
                title="Valentine Heart Match",
                instruction=(
                    "Draw a heart in the air with your index finger, or make a "
                    "heart shape with your hands."
                ),
                learning_prompt=learning_prompt,
                target_duration_ms=4_000,
                participant_ids=participant_ids,
            )
        if game_type is WebcamGameType.MOTHERS_DAY:
            return WebcamLearningChallenge(
                challenge_id=f"challenge-{uuid4().hex[:12]}",
                session_id=session_id,
                mode=mode,
                game_type=game_type,
                title="Mother's Day Bouquet",
                instruction=(
                    "Hold your kindest smile for Mom — add flowers or makeup overlays "
                    "and wave hello to the camera."
                ),
                learning_prompt=learning_prompt,
                target_duration_ms=3_000,
                participant_ids=participant_ids,
            )
        if game_type is WebcamGameType.FATHERS_DAY:
            return WebcamLearningChallenge(
                challenge_id=f"challenge-{uuid4().hex[:12]}",
                session_id=session_id,
                mode=mode,
                game_type=game_type,
                title="Father's Day Hero",
                instruction=(
                    "Strike a confident hero pose for Dad — shades or hammer props "
                    "encouraged, big smile optional."
                ),
                learning_prompt=learning_prompt,
                target_duration_ms=3_000,
                participant_ids=participant_ids,
            )
        if game_type is WebcamGameType.CUTE_ENOUGH:
            return WebcamLearningChallenge(
                challenge_id=f"challenge-{uuid4().hex[:12]}",
                session_id=session_id,
                mode=mode,
                game_type=game_type,
                title="Am I Cute Enough?",
                instruction=(
                    "Dress up with hats, glasses, makeup, and props — then hold your "
                    "confident pose. Every look is celebrated; score reflects energy, "
                    "not appearance."
                ),
                learning_prompt=learning_prompt,
                target_duration_ms=4_000,
                participant_ids=participant_ids,
            )
        if game_type is WebcamGameType.JIGGY_DANCE:
            moves = random_jiggy_sequence()
            return WebcamLearningChallenge(
                challenge_id=f"challenge-{uuid4().hex[:12]}",
                session_id=session_id,
                mode=mode,
                game_type=game_type,
                title="Come get jiggy with me!",
                instruction=(
                    "Follow the dance prompts on camera — shake, bop, spin, and move "
                    "to the beat. Skip any move you cannot or do not want to do."
                ),
                learning_prompt=learning_prompt or "Come get jiggy with me!",
                target_duration_ms=jiggy_target_duration_ms(len(moves)),
                participant_ids=participant_ids,
                move_sequence=moves,
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
        state: _GameState,
    ) -> tuple[bool, str, int | None, str | None, list[str], list[str]]:
        if not evaluation.participants:
            return False, "No participants were detected for this challenge attempt.", None, None, [], []
        if evaluation.training_paused:
            reason = evaluation.pause_reason or "training_paused"
            return False, f"Training is paused ({reason}); challenge attempt is blocked.", None, None, [], []

        timestamps = [s.timestamp_ms for s in signals]
        observed_ms = (max(timestamps) - min(timestamps)) if len(timestamps) >= 2 else 0
        needs_duration = challenge.game_type in {
            WebcamGameType.FOCUS_STREAK,
            WebcamGameType.INTEGRITY_GUARD,
            WebcamGameType.HALLOWEEN_WAND,
            WebcamGameType.CHRISTMAS_GINGERBREAD,
            WebcamGameType.VALENTINES_HEARTS,
            WebcamGameType.MOTHERS_DAY,
            WebcamGameType.FATHERS_DAY,
            WebcamGameType.CUTE_ENOUGH,
        }
        if needs_duration and observed_ms < challenge.target_duration_ms:
            return (
                False,
                (
                    f"Keep going a bit longer "
                    f"({observed_ms}ms/{challenge.target_duration_ms}ms)."
                ),
                None,
                None,
                [],
                [],
            )

        if challenge.game_type is WebcamGameType.HALLOWEEN_WAND:
            spell = self._best_spell(signals)
            if spell:
                return True, f"Spell cast: {spell}! Your wand trail worked.", None, spell, [], []
            return False, "Try a clearer wand swish, flick, or loop with your index finger.", None, None, [], []

        if challenge.game_type is WebcamGameType.CHRISTMAS_GINGERBREAD:
            if evaluation.happy_participant_ids:
                return True, "Gingerbread house glows — lovely festive smile!", None, None, [], []
            return False, "Show a bright smile to light up the gingerbread house.", None, None, [], []

        if challenge.game_type is WebcamGameType.VALENTINES_HEARTS:
            if self._heart_detected(signals):
                return True, "Heart matched! Lovely Valentine energy.", None, None, [], []
            return False, "Draw a heart loop in the air or make a heart with your hands.", None, None, [], []

        if challenge.game_type is WebcamGameType.MOTHERS_DAY:
            if evaluation.happy_participant_ids or any((s.smile_score or 0) >= 0.35 for s in signals):
                return True, "Beautiful Mother's Day warmth — thank-you energy received!", None, None, [], []
            return False, "Share a kind smile or wave for Mother's Day.", None, None, [], []

        if challenge.game_type is WebcamGameType.FATHERS_DAY:
            accessory_ok = any((s.accessory_count or 0) >= 1 for s in signals)
            smile_ok = bool(evaluation.happy_participant_ids) or any(
                (s.smile_score or 0) >= 0.30 for s in signals
            )
            if accessory_ok or smile_ok:
                return True, "Hero pose approved — great Father's Day confidence!", None, None, [], []
            return False, "Add a fun prop or confident smile for Father's Day.", None, None, [], []

        if challenge.game_type is WebcamGameType.CUTE_ENOUGH:
            score = self._best_cute_score(signals)
            pid = signals[-1].participant_id if signals else "camera-local"
            if score > 0:
                prev = state.cute_leaderboard.get(pid, 0)
                state.cute_leaderboard[pid] = max(prev, score)
            passed = score >= CUTE_PASS_THRESHOLD
            msg = cute_encouragement(score)
            if passed:
                msg += f" Cute confidence score: {score}/100."
            else:
                msg += f" Score {score}/100 — add accessories or a bigger smile!"
            return passed, msg, score, None, [], []

        if challenge.game_type is WebcamGameType.JIGGY_DANCE:
            expected = challenge.move_sequence or random_jiggy_sequence(length=4)
            count, matched, skipped = sequence_progress(signals, expected)
            passed = count >= len(expected)
            if passed:
                msg = (
                    f"Jiggy complete! {len(matched)} danced"
                    + (f", {len(skipped)} skipped" if skipped else "")
                    + f" — {move_encouragement(matched[-1]) if matched else 'You finished the set!'}"
                )
            elif matched:
                msg = (
                    f"Nice dancing — camera saw {len(matched)}/{len(expected)} moves. "
                    "Skip any you cannot do, or keep grooving!"
                )
            else:
                msg = (
                    "Keep moving with the prompts — shake, bop, and groove "
                    "when you see each move on screen. Skip is always OK."
                )
            return passed, msg, None, None, matched, skipped

        if challenge.game_type is WebcamGameType.FOCUS_STREAK:
            if evaluation.suspected_cheating_participant_ids:
                return False, "Focus challenge failed due to possible cheating signals.", None, None, [], []
            any_eyes_away = any(p.eyes_away_for_ms > 0 for p in evaluation.participants)
            if any_eyes_away:
                return False, "Keep eyes on screen for the full focus streak.", None, None, [], []
            return True, "Great focus control — challenge passed.", None, None, [], []

        if challenge.game_type is WebcamGameType.CONFIDENCE_SMILE:
            if not evaluation.happy_participant_ids:
                return False, "Show a confident/happy expression while answering.", None, None, [], []
            return True, "Strong confidence signal detected — challenge passed.", None, None, [], []

        if evaluation.suspected_cheating_participant_ids:
            return False, "Integrity challenge failed due to suspicious signals.", None, None, [], []
        return True, "Integrity challenge passed with clean attention signals.", None, None, [], []

    @staticmethod
    def _best_spell(signals: list[WebcamSignal]) -> str | None:
        for signal in reversed(signals):
            if signal.wand_spell_label:
                return signal.wand_spell_label
        return None

    @staticmethod
    def _heart_detected(signals: list[WebcamSignal]) -> bool:
        for signal in signals:
            if signal.wand_spell_label == "heart":
                return True
        return False

    @staticmethod
    def _best_cute_score(signals: list[WebcamSignal]) -> int:
        best = 0
        for signal in signals:
            if signal.cute_confidence_score is not None:
                best = max(best, int(signal.cute_confidence_score))
                continue
            score = cute_confidence_score(
                face_present=signal.face_count > 0,
                smile_score=signal.smile_score or 0.0,
                gaze_frontal=signal.gaze_frontal or 0.5,
                accessory_count=signal.accessory_count or 0,
                head_pose_yaw=signal.head_pose_yaw,
                head_pose_roll=signal.head_pose_roll,
            )
            best = max(best, score)
        return best


def compute_client_cute_score(
    *,
    face_count: int,
    smile_score: float,
    gaze_frontal: float,
    costume_id: str,
    accessory_id: str,
    head_pose_yaw: float | None,
    head_pose_roll: float | None,
) -> int:
    """Mirror of server cute scoring for live HUD display."""
    accessories = accessory_count_from_ids(costume_id, accessory_id)
    return cute_confidence_score(
        face_present=face_count > 0,
        smile_score=smile_score,
        gaze_frontal=gaze_frontal,
        accessory_count=accessories,
        head_pose_yaw=head_pose_yaw,
        head_pose_roll=head_pose_roll,
    )


def spell_from_trail_points(trail: list[tuple[float, float]]) -> str | None:
    return recognize_wand_spell(trail)


def heart_from_trail_points(trail: list[tuple[float, float]]) -> bool:
    return trail_heart_shape(trail)
