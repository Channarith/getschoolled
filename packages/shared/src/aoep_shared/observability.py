"""Phase 10 - latency budget + lightweight metrics (hardening scaffold).

The hardest real-time constraint is the speech-in -> think -> speech-out loop.
This module encodes the target budget and a dependency-free latency recorder so
services can measure and assert against it; a real deployment exports these to
the observability stack. Pure and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


# Target end-to-end budget (milliseconds), split across the pipeline stages.
DEFAULT_BUDGET_MS: Dict[str, float] = {
    "asr": 300.0,        # streaming ASR endpointing
    "think": 500.0,      # LLM/director decision (first token/sentence)
    "tts": 300.0,        # speech synthesis (first chunk)
}
TOTAL_BUDGET_MS: float = sum(DEFAULT_BUDGET_MS.values())  # 1100 ms


@dataclass
class LatencyBudget:
    stages: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_BUDGET_MS))

    @property
    def total_ms(self) -> float:
        return sum(self.stages.values())

    def within_budget(self, measured_ms: Dict[str, float]) -> bool:
        """True if every measured stage is within its budget."""
        return all(
            measured_ms.get(stage, 0.0) <= limit
            for stage, limit in self.stages.items()
        )

    def overages(self, measured_ms: Dict[str, float]) -> Dict[str, float]:
        """Stages exceeding budget -> by how many ms."""
        out: Dict[str, float] = {}
        for stage, limit in self.stages.items():
            over = measured_ms.get(stage, 0.0) - limit
            if over > 0:
                out[stage] = over
        return out


@dataclass
class LatencyRecorder:
    """Collects per-stage samples and computes simple aggregates."""

    samples: Dict[str, List[float]] = field(default_factory=dict)

    def record(self, stage: str, ms: float) -> None:
        self.samples.setdefault(stage, []).append(ms)

    def mean(self, stage: str) -> float:
        xs = self.samples.get(stage, [])
        return sum(xs) / len(xs) if xs else 0.0

    def p95(self, stage: str) -> float:
        xs = sorted(self.samples.get(stage, []))
        if not xs:
            return 0.0
        idx = max(0, min(len(xs) - 1, int(round(0.95 * (len(xs) - 1)))))
        return xs[idx]

    def summary(self) -> Dict[str, Dict[str, float]]:
        return {
            stage: {"mean": self.mean(stage), "p95": self.p95(stage)}
            for stage in self.samples
        }
