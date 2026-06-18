"""Phase 4/10 - optimization ledger (track accuracy per stage; promote/revert).

Every optimization change - BKT params, policy/bandit posteriors, or a promoted
model/adapter - is committed as a versioned `OptimizationStep` with its metrics
(accuracy, correctness, calibration/log-loss, ...). `promote_if_better` only
adopts a step that does NOT regress the primary metric (generalizes the
training/config/finetune.yaml promote gate), and `revert` rolls a stage back to
any prior step. This is the runtime analog of the per-PR git revert: each stage
is a labeled, evaluated, revertible checkpoint.

Pure Python; fully unit-testable.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class OptimizationStep:
    step_id: str
    stage: str
    params: dict
    metrics: dict
    parent: Optional[str] = None
    created_at: float = field(default_factory=lambda: time.time())


class OptimizationLedger:
    def __init__(self, *, primary_metric: str = "accuracy", higher_is_better: bool = True) -> None:
        self.primary_metric = primary_metric
        self.higher_is_better = higher_is_better
        self._steps: Dict[str, OptimizationStep] = {}
        self._by_stage: Dict[str, List[str]] = {}
        self._champion: Dict[str, str] = {}

    def commit(self, stage: str, params: dict, metrics: dict,
               parent: Optional[str] = None) -> OptimizationStep:
        step = OptimizationStep(
            step_id=uuid.uuid4().hex[:12], stage=stage, params=dict(params),
            metrics=dict(metrics),
            parent=parent if parent is not None else self._champion.get(stage),
        )
        self._steps[step.step_id] = step
        self._by_stage.setdefault(stage, []).append(step.step_id)
        return step

    def _score(self, step: OptimizationStep) -> float:
        return float(step.metrics.get(self.primary_metric, 0.0))

    def _is_better(self, candidate: OptimizationStep, champion: OptimizationStep) -> bool:
        # "do not regress" -> >= (or <= when lower-is-better).
        if self.higher_is_better:
            return self._score(candidate) >= self._score(champion)
        return self._score(candidate) <= self._score(champion)

    def promote_if_better(self, step: OptimizationStep) -> bool:
        """Adopt the step as the stage champion iff it does not regress."""
        champ_id = self._champion.get(step.stage)
        if champ_id is None or self._is_better(step, self._steps[champ_id]):
            self._champion[step.stage] = step.step_id
            return True
        return False

    def champion(self, stage: str) -> Optional[OptimizationStep]:
        cid = self._champion.get(stage)
        return self._steps.get(cid) if cid else None

    def revert(self, stage: str, step_id: str) -> OptimizationStep:
        """Roll a stage's champion back to a prior committed step."""
        step = self._steps.get(step_id)
        if step is None or step.stage != stage:
            raise KeyError(f"no step {step_id!r} in stage {stage!r}")
        self._champion[stage] = step_id
        return step

    def history(self, stage: Optional[str] = None) -> List[OptimizationStep]:
        if stage is not None:
            return [self._steps[s] for s in self._by_stage.get(stage, [])]
        return list(self._steps.values())
