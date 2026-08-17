"""Drive Mode knob bakeoff (wake + answer quality)."""

from __future__ import annotations

import random
from typing import Any, Optional

from .answer_grounding import evaluate_answers
from .drive_tuning import PRESETS, DriveTuning
from .quality_telemetry import DriveTelemetryStore
from .wake_eval import evaluate_wake, load_wake_cases

try:
    from aoep_shared.optimization import OptimizationLedger
except Exception:  # noqa: BLE001
    OptimizationLedger = None  # type: ignore


class DriveBakeoffRunner:
    def __init__(self) -> None:
        self.tuning = DriveTuning.from_env()
        self.telemetry = DriveTelemetryStore()
        self.cases = load_wake_cases()
        self.ledger = (
            OptimizationLedger(primary_metric="drive_quality", higher_is_better=True)
            if OptimizationLedger is not None
            else None
        )
        self.champion: dict[str, Any] = {}
        self._seed()

    def _score(self, tuning: DriveTuning) -> dict[str, Any]:
        wake = evaluate_wake(self.cases, tuning)
        ans = evaluate_answers(tuning=tuning)
        self.telemetry.record_wake()
        self.telemetry.record_answer()
        drive_quality = round(0.55 * wake["wake_quality"] + 0.45 * ans["answer_quality"], 4)
        return {
            "wake_quality": wake["wake_quality"],
            "wake_precision": wake["wake_precision"],
            "wake_recall": wake["wake_recall"],
            "echo_accuracy": wake["echo_accuracy"],
            "answer_quality": ans["answer_quality"],
            "grounded_rate": ans["grounded_rate"],
            "drive_quality": drive_quality,
            "wake": wake,
            "answer": {k: v for k, v in ans.items() if k != "rows"},
        }

    def _seed(self) -> None:
        metrics = self._score(self.tuning)
        payload = {"tuning": self.tuning.to_dict(), "metrics": metrics, "source": "seed"}
        self.champion = payload
        self.telemetry.set_champion(payload)
        self.telemetry.record(metrics, promoted=True)
        if self.ledger is not None:
            step = self.ledger.commit("drive", self.tuning.to_dict(), metrics)
            self.ledger.promote_if_better(step)

    def _candidate(self, rng: random.Random) -> DriveTuning:
        if rng.random() < 0.4:
            return DriveTuning.preset(rng.choice(list(PRESETS.keys())))
        base = self.tuning.to_dict()
        base["echo_min_overlap"] = round(
            max(0.3, min(0.85, float(base["echo_min_overlap"]) + rng.choice([-0.05, 0.0, 0.05]))),
            4,
        )
        base["pause_submit_ms"] = int(
            max(500, min(15000, int(base["pause_submit_ms"]) + rng.choice([-500, 0, 500])))
        )
        base["answer_min_overlap"] = round(
            max(0.05, min(0.5, float(base["answer_min_overlap"]) + rng.choice([-0.05, 0.0, 0.05]))),
            4,
        )
        base["tts_rate"] = round(
            max(0.5, min(2.0, float(base["tts_rate"]) + rng.choice([-0.05, 0.0, 0.05]))),
            3,
        )
        return DriveTuning(**base)

    def run_round(self, *, seed: Optional[int] = None) -> dict[str, Any]:
        rng = random.Random(seed if seed is not None else None)
        candidate = self._candidate(rng)
        metrics = self._score(candidate)
        promoted = False
        if self.ledger is not None:
            step = self.ledger.commit("drive", candidate.to_dict(), metrics)
            promoted = self.ledger.promote_if_better(step)
            if promoted:
                self.tuning = candidate
                self.champion = {
                    "tuning": candidate.to_dict(),
                    "metrics": metrics,
                    "step_id": step.step_id,
                    "source": "bakeoff",
                }
                self.telemetry.set_champion(self.champion)
        else:
            cur = float(self.champion.get("metrics", {}).get("drive_quality") or 0.0)
            if metrics["drive_quality"] >= cur:
                promoted = True
                self.tuning = candidate
                self.champion = {
                    "tuning": candidate.to_dict(),
                    "metrics": metrics,
                    "source": "bakeoff_no_ledger",
                }
                self.telemetry.set_champion(self.champion)
        self.telemetry.record(metrics, promoted=promoted)
        return {"promoted": promoted, "tuning": candidate.to_dict(), "metrics": metrics}

    def run_bakeoff(self, rounds: Optional[int] = None) -> dict[str, Any]:
        n = int(rounds or self.tuning.bakeoff_rounds)
        n = max(1, min(n, 100))
        results = []
        for i in range(n):
            results.append(self.run_round(seed=i + 1))
        return {
            "rounds": n,
            "champion": self.champion,
            "telemetry": self.telemetry.snapshot(),
            "last": results[-1] if results else {},
        }


_RUNNER: Optional[DriveBakeoffRunner] = None


def get_runner() -> DriveBakeoffRunner:
    global _RUNNER
    if _RUNNER is None:
        _RUNNER = DriveBakeoffRunner()
    return _RUNNER
