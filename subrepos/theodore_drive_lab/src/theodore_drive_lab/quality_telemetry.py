"""Telemetry for Drive Mode fine-tune runs."""

from __future__ import annotations

import threading
from typing import Any


class DriveTelemetryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.wake_evals = 0
            self.answer_evals = 0
            self.bakeoff_rounds = 0
            self.promotions = 0
            self._wake_q_sum = 0.0
            self._answer_q_sum = 0.0
            self._drive_q_sum = 0.0
            self._n = 0
            self.champion: dict[str, Any] = {}
            self.last: dict[str, Any] = {}

    def record(self, payload: dict[str, Any], *, promoted: bool = False) -> None:
        with self._lock:
            self.bakeoff_rounds += 1
            if promoted:
                self.promotions += 1
            self._n += 1
            self._wake_q_sum += float(payload.get("wake_quality") or 0.0)
            self._answer_q_sum += float(payload.get("answer_quality") or 0.0)
            self._drive_q_sum += float(payload.get("drive_quality") or 0.0)
            self.last = dict(payload)

    def record_wake(self) -> None:
        with self._lock:
            self.wake_evals += 1

    def record_answer(self) -> None:
        with self._lock:
            self.answer_evals += 1

    def set_champion(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self.champion = dict(payload)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            n = max(1, self._n)
            return {
                "wake_evals": self.wake_evals,
                "answer_evals": self.answer_evals,
                "bakeoff_rounds": self.bakeoff_rounds,
                "promotions": self.promotions,
                "avg_wake_quality": round(self._wake_q_sum / n, 4),
                "avg_answer_quality": round(self._answer_q_sum / n, 4),
                "avg_drive_quality": round(self._drive_q_sum / n, 4),
                "promotion_rate": round(self.promotions / max(1, self.bakeoff_rounds), 4),
                "last": dict(self.last),
                "champion": dict(self.champion),
            }
