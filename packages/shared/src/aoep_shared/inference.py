"""Phase 4 - Variational Inference ability model (Bayesian IRT).

A Rasch / 1PL item-response model, P(correct) = sigmoid(ability - difficulty),
fit by mean-field variational Bayes (coordinate-ascent gradient updates with
Gaussian priors; posterior std from the Fisher information). Estimates each
student's latent ability and each item's difficulty from correct/incorrect
responses, and selects an item difficulty that targets a desired success
probability (adaptive, slightly-challenging item selection).

Pure Python (no numpy) so every service can use it; fully unit-testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Sequence, Tuple


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def logit(p: float) -> float:
    p = min(1 - 1e-6, max(1e-6, p))
    return math.log(p / (1 - p))


@dataclass
class VariationalAbilityModel:
    prior_var: float = 1.0
    lr: float = 0.5
    iterations: int = 200
    abilities: Dict[str, float] = field(default_factory=dict)
    difficulties: Dict[str, float] = field(default_factory=dict)
    ability_std: Dict[str, float] = field(default_factory=dict)

    def fit(self, responses: Sequence[Tuple[str, str, bool]]) -> "VariationalAbilityModel":
        """Fit on (student_id, item_id, correct) triples via coordinate ascent."""
        students = {s for s, _, _ in responses}
        items = {i for _, i, _ in responses}
        theta = {s: 0.0 for s in students}
        beta = {i: 0.0 for i in items}

        for _ in range(self.iterations):
            g_theta = {s: -theta[s] / self.prior_var for s in students}
            g_beta = {i: -beta[i] / self.prior_var for i in items}
            for s, i, correct in responses:
                p = _sigmoid(theta[s] - beta[i])
                err = (1.0 if correct else 0.0) - p
                g_theta[s] += err
                g_beta[i] -= err
            for s in students:
                theta[s] += self.lr * g_theta[s] / max(1, len(students))
            for i in items:
                beta[i] += self.lr * g_beta[i] / max(1, len(items))

        # Posterior std per student from Fisher information.
        info = {s: 1.0 / self.prior_var for s in students}
        for s, i, _ in responses:
            p = _sigmoid(theta[s] - beta[i])
            info[s] += p * (1 - p)

        self.abilities = theta
        self.difficulties = beta
        self.ability_std = {s: 1.0 / math.sqrt(info[s]) for s in students}
        return self

    def ability(self, student_id: str) -> float:
        return self.abilities.get(student_id, 0.0)

    def difficulty(self, item_id: str) -> float:
        return self.difficulties.get(item_id, 0.0)

    def p_correct(self, student_id: str, item_id: str) -> float:
        return _sigmoid(self.ability(student_id) - self.difficulty(item_id))

    def select_difficulty(self, student_id: str, *, target_p: float = 0.7) -> float:
        """Difficulty that makes the student's predicted success == target_p
        (slightly challenging by default)."""
        return self.ability(student_id) - logit(target_p)
