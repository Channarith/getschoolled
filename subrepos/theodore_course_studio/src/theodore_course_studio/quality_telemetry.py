"""Teach/build telemetry for Theodore Course Studio.

`StudioTelemetryStore` records course authoring and live-teaching signals:
courses built (by audience), slides taught, quiz/game starts + passes (games
broken out by kind), voice/TTS turns, checkpoint pauses, language switches,
review keep/reject verdicts, offline training epochs, and content-quality
rejects. `snapshot` returns a flat dict (>20 keys) with computed averages and a
blended `engagement_score`.
"""

from __future__ import annotations

import threading
from typing import Any


class StudioTelemetryStore:
    def __init__(self, history_points: int = 256) -> None:
        self._lock = threading.Lock()
        self._history_points = max(1, int(history_points))
        self._reset()

    def _reset(self) -> None:
        self.courses_built = 0
        self.early_courses = 0
        self.cert_courses = 0
        self.slides_taught = 0
        self.quizzes_started = 0
        self.quizzes_passed = 0
        self.pop_quizzes = 0
        self.summary_quizzes = 0
        self.games_started = 0
        self.games_passed = 0
        self.games_by_kind_started: dict[str, int] = {}
        self.games_by_kind_passed: dict[str, int] = {}
        self.voice_turns = 0
        self.tts_requests = 0
        self.checkpoint_pauses = 0
        self.language_switches = 0
        self.review_keeps = 0
        self.review_rejects = 0
        self.offline_epochs = 0
        self.quality_rejects = 0
        self._quiz_score_sum = 0.0
        self._quiz_score_count = 0
        self._game_score_sum = 0.0
        self._game_score_count = 0
        self._teach_latency_sum = 0
        self._teach_latency_count = 0
        self._recent_scores: list[float] = []

    def reset(self) -> None:
        with self._lock:
            self._reset()

    def record_course_built(self, *, audience: str = "general") -> None:
        with self._lock:
            self.courses_built += 1
            aud = (audience or "").lower()
            if aud in {"adult_cert_prep", "corporate"} or "cert" in aud:
                self.cert_courses += 1
            elif aud not in {"general", ""}:
                self.early_courses += 1

    def record_early_course(self) -> None:
        with self._lock:
            self.courses_built += 1
            self.early_courses += 1

    def record_cert_course(self) -> None:
        with self._lock:
            self.courses_built += 1
            self.cert_courses += 1

    def record_slide_taught(self, *, latency_ms: int = 0) -> None:
        with self._lock:
            self.slides_taught += 1
            if latency_ms:
                self._teach_latency_sum += max(0, int(latency_ms))
                self._teach_latency_count += 1

    def record_quiz(self, *, kind: str, score: float, passed: bool) -> None:
        with self._lock:
            self.quizzes_started += 1
            if passed:
                self.quizzes_passed += 1
            if (kind or "").lower() == "summary":
                self.summary_quizzes += 1
            else:
                self.pop_quizzes += 1
            self._quiz_score_sum += float(score)
            self._quiz_score_count += 1
            self._push_score(float(score))

    def record_game(self, *, kind: str, score: float, passed: bool) -> None:
        with self._lock:
            self.games_started += 1
            k = (kind or "unknown").lower()
            self.games_by_kind_started[k] = self.games_by_kind_started.get(k, 0) + 1
            if passed:
                self.games_passed += 1
                self.games_by_kind_passed[k] = self.games_by_kind_passed.get(k, 0) + 1
            self._game_score_sum += float(score)
            self._game_score_count += 1
            self._push_score(float(score))

    def record_voice_turn(self, *, tts: bool = False) -> None:
        with self._lock:
            self.voice_turns += 1
            if tts:
                self.tts_requests += 1

    def record_tts_request(self) -> None:
        with self._lock:
            self.tts_requests += 1

    def record_checkpoint_pause(self) -> None:
        with self._lock:
            self.checkpoint_pauses += 1

    def record_language_switch(self) -> None:
        with self._lock:
            self.language_switches += 1

    def record_review(self, *, keep: bool) -> None:
        with self._lock:
            if keep:
                self.review_keeps += 1
            else:
                self.review_rejects += 1

    def record_offline_epochs(self, epochs: int) -> None:
        with self._lock:
            self.offline_epochs += max(0, int(epochs))

    def record_quality_reject(self, count: int = 1) -> None:
        with self._lock:
            self.quality_rejects += max(0, int(count))

    def _push_score(self, score: float) -> None:
        self._recent_scores.append(score)
        if len(self._recent_scores) > self._history_points:
            self._recent_scores = self._recent_scores[-self._history_points :]

    def _engagement_score(self) -> float:
        quiz_pass_ratio = (
            self.quizzes_passed / self.quizzes_started if self.quizzes_started else 0.0
        )
        game_pass_ratio = (
            self.games_passed / self.games_started if self.games_started else 0.0
        )
        parts: list[float] = []
        if self.quizzes_started:
            parts.append(quiz_pass_ratio)
        if self.games_started:
            parts.append(game_pass_ratio)
        if self._recent_scores:
            parts.append(sum(self._recent_scores) / len(self._recent_scores))
        if not parts:
            return 0.0
        return round(sum(parts) / len(parts), 3)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "courses_built": self.courses_built,
                "early_courses": self.early_courses,
                "cert_courses": self.cert_courses,
                "slides_taught": self.slides_taught,
                "quizzes_started": self.quizzes_started,
                "quizzes_passed": self.quizzes_passed,
                "pop_quizzes": self.pop_quizzes,
                "summary_quizzes": self.summary_quizzes,
                "games_started": self.games_started,
                "games_passed": self.games_passed,
                "games_by_kind_started": dict(self.games_by_kind_started),
                "games_by_kind_passed": dict(self.games_by_kind_passed),
                "voice_turns": self.voice_turns,
                "tts_requests": self.tts_requests,
                "checkpoint_pauses": self.checkpoint_pauses,
                "language_switches": self.language_switches,
                "review_keeps": self.review_keeps,
                "review_rejects": self.review_rejects,
                "offline_epochs": self.offline_epochs,
                "quality_rejects": self.quality_rejects,
                "avg_quiz_score": round(
                    self._quiz_score_sum / self._quiz_score_count, 3
                )
                if self._quiz_score_count
                else 0.0,
                "avg_game_score": round(
                    self._game_score_sum / self._game_score_count, 3
                )
                if self._game_score_count
                else 0.0,
                "latency_teach_ms_avg": round(
                    self._teach_latency_sum / self._teach_latency_count, 1
                )
                if self._teach_latency_count
                else 0.0,
                "engagement_score": self._engagement_score(),
            }


# Shared store used by the FastAPI app + teach engine.
_STORE = StudioTelemetryStore()


def get_telemetry() -> StudioTelemetryStore:
    return _STORE
