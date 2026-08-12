"""Quality telemetry for RAG auto-tune runs."""

from __future__ import annotations

import threading
from typing import Any


class RagTelemetryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.eval_runs = 0
            self.bakeoff_rounds = 0
            self.promotions = 0
            self.rejections = 0
            self.hours_simulated = 0.0
            self._quality_sum = 0.0
            self._quality_n = 0
            self._recall_sum = 0.0
            self._ground_sum = 0.0
            self._latency_sum = 0.0
            self.last_report: dict[str, Any] = {}
            self.champion: dict[str, Any] = {}

    def record_eval(self, report: dict[str, Any]) -> None:
        with self._lock:
            self.eval_runs += 1
            q = float(report.get("rag_quality") or 0.0)
            self._quality_sum += q
            self._quality_n += 1
            self._recall_sum += float(report.get("recall_at_k") or 0.0)
            self._ground_sum += float(report.get("groundedness") or 0.0)
            self._latency_sum += float(report.get("latency_ms_avg") or 0.0)
            self.last_report = dict(report)

    def record_bakeoff_round(self, *, promoted: bool) -> None:
        with self._lock:
            self.bakeoff_rounds += 1
            if promoted:
                self.promotions += 1
            else:
                self.rejections += 1

    def record_hours(self, hours: float) -> None:
        with self._lock:
            self.hours_simulated = max(self.hours_simulated, float(hours))

    def set_champion(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self.champion = dict(payload)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            n = max(1, self._quality_n)
            return {
                "eval_runs": self.eval_runs,
                "bakeoff_rounds": self.bakeoff_rounds,
                "promotions": self.promotions,
                "rejections": self.rejections,
                "hours_simulated": round(self.hours_simulated, 4),
                "avg_rag_quality": round(self._quality_sum / n, 4),
                "avg_recall_at_k": round(self._recall_sum / n, 4),
                "avg_groundedness": round(self._ground_sum / n, 4),
                "avg_latency_ms": round(self._latency_sum / n, 3),
                "promotion_rate": round(self.promotions / max(1, self.bakeoff_rounds), 4),
                "last_report": dict(self.last_report),
                "champion": dict(self.champion),
            }
