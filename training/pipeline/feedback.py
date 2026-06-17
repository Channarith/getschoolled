"""User feedback -> reward signal + aggregates for training."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence


@dataclass
class Feedback:
    rating: int            # 1..5 star rating
    helpful: bool = True
    correction: Optional[str] = None  # optional corrected answer (gold signal)


def reward_from_feedback(fb: Feedback) -> float:
    """Map feedback to a reward in [-1, 1] for preference-weighted training."""
    base = (fb.rating - 3) / 2.0      # 1->-1, 3->0, 5->+1
    if not fb.helpful:
        base -= 0.5
    if fb.correction:
        # An explicit correction is a strong negative on the given answer.
        base = min(base, -0.5)
    return max(-1.0, min(1.0, base))


def aggregate(feedbacks: Sequence[Feedback]) -> Dict[str, float]:
    if not feedbacks:
        return {"count": 0, "mean_rating": 0.0, "helpful_rate": 0.0, "mean_reward": 0.0}
    n = len(feedbacks)
    return {
        "count": n,
        "mean_rating": sum(f.rating for f in feedbacks) / n,
        "helpful_rate": sum(1 for f in feedbacks if f.helpful) / n,
        "mean_reward": sum(reward_from_feedback(f) for f in feedbacks) / n,
    }
