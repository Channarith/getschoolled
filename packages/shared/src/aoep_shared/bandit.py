"""Phase 4 - feedback-tuned content bandit (Thompson sampling).

Chooses the next item/explanation variant to maximize success/engagement,
learning online from outcomes (and the existing feedback/correction signals).
Each arm holds a Beta(alpha, beta) posterior over its success probability;
selection samples each posterior and picks the best (Thompson sampling), which
balances exploration and exploitation. Pure Python; a seeded RNG makes it
deterministic for tests.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ContentBandit:
    # arm -> [alpha, beta] Beta posterior (priors start at 1,1 = uniform).
    arms: Dict[str, List[float]] = field(default_factory=dict)

    def add_arm(self, arm: str) -> None:
        self.arms.setdefault(arm, [1.0, 1.0])

    def record(self, arm: str, success: bool) -> None:
        a = self.arms.setdefault(arm, [1.0, 1.0])
        if success:
            a[0] += 1.0
        else:
            a[1] += 1.0

    def estimate(self, arm: str) -> float:
        a, b = self.arms.get(arm, [1.0, 1.0])
        return a / (a + b)

    def select(self, rng: Optional[random.Random] = None) -> Optional[str]:
        if not self.arms:
            return None
        r = rng or random
        best_arm, best_sample = None, -1.0
        for arm, (a, b) in self.arms.items():
            sample = r.betavariate(a, b)
            if sample > best_sample:
                best_sample, best_arm = sample, arm
        return best_arm
