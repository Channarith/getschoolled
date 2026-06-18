"""Phase 4 - Bayesian learner modeling.

- Bayesian Knowledge Tracing (BKT): a 2-state dynamic Bayesian network that
  tracks the posterior P(known) for a skill from each correct/incorrect
  observation (learn/slip/guess/forget parameters).
- SkillGraph: a Bayesian belief network of prerequisite relationships, so a
  skill's effective mastery is gated by its prerequisites (the "mastery graph").

Pure/dependency-free and fully unit-testable. Feeds the adaptive policy
(aoep_shared.adaptive) and replaces the ad-hoc EMA mastery in services/memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class BKTParams:
    p_init: float = 0.2     # prior P(known) before any evidence
    p_learn: float = 0.15   # P(not-known -> known) per opportunity
    p_slip: float = 0.10    # P(incorrect | known)
    p_guess: float = 0.20   # P(correct | not known)
    p_forget: float = 0.0   # P(known -> not-known) per step


class BayesianKnowledgeTracing:
    def __init__(self, params: Optional[BKTParams] = None) -> None:
        self.params = params or BKTParams()

    def update(self, p_known: float, correct: bool) -> float:
        """Posterior P(known) after one observation, then the learn/forget step."""
        s = self.params
        if correct:
            num = p_known * (1 - s.p_slip)
            den = num + (1 - p_known) * s.p_guess
        else:
            num = p_known * s.p_slip
            den = num + (1 - p_known) * (1 - s.p_guess)
        posterior = (num / den) if den > 0 else p_known
        # Transition: learning, then forgetting.
        p_next = posterior + (1 - posterior) * s.p_learn
        p_next = p_next * (1 - s.p_forget)
        return _clamp01(p_next)

    def sequence(self, outcomes: Sequence[bool], p0: Optional[float] = None) -> float:
        """Fold a sequence of observations into a final P(known)."""
        p = self.params.p_init if p0 is None else p0
        for correct in outcomes:
            p = self.update(p, correct)
        return p

    def p_correct(self, p_known: float) -> float:
        """Predicted P(correct) on the next opportunity given P(known)."""
        s = self.params
        return _clamp01(p_known * (1 - s.p_slip) + (1 - p_known) * s.p_guess)


class SkillGraph:
    """Prerequisite belief network over skills."""

    def __init__(self) -> None:
        self._prereqs: Dict[str, List[str]] = {}

    def add_prereq(self, skill: str, prerequisite: str) -> None:
        self._prereqs.setdefault(skill, [])
        if prerequisite not in self._prereqs[skill]:
            self._prereqs[skill].append(prerequisite)
        self._prereqs.setdefault(prerequisite, [])

    def prerequisites(self, skill: str) -> List[str]:
        return list(self._prereqs.get(skill, []))

    def propagate(self, mastery: Dict[str, float], *, weight: float = 0.5) -> Dict[str, float]:
        """Gate each skill's mastery by its weakest prerequisite.

        A skill can't be considered well-mastered if a prerequisite isn't; blend
        the observed mastery with that prerequisite floor.
        """
        out: Dict[str, float] = {}
        for skill, m in mastery.items():
            pres = self._prereqs.get(skill, [])
            if pres:
                floor = min(mastery.get(p, 0.0) for p in pres)
                out[skill] = _clamp01((1 - weight) * m + weight * min(m, floor))
            else:
                out[skill] = _clamp01(m)
        return out

    def ready(self, skill: str, mastery: Dict[str, float], *, threshold: float = 0.7) -> bool:
        """Whether all of ``skill``'s prerequisites are mastered >= threshold."""
        return all(mastery.get(p, 0.0) >= threshold for p in self._prereqs.get(skill, []))
