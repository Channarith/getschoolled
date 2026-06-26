"""Evolving learner profile: pace, goals, strategy outcomes, sensitivity memory."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .adaptive import AdaptivePolicy, LearnerSignals, Pacing, PacingPlan
from .schemas import ClassType


@dataclass
class SensitivityRule:
    """Something that upset the learner — avoid repeating unless ``allow_retry``."""
    rule_id: str
    trigger: str          # phrase, method id, or topic pattern
    reason: str = ""
    created_at: float = field(default_factory=lambda: time.time())
    allow_retry: bool = False
    severity: str = "medium"  # low | medium | high


@dataclass
class FailedApproach:
    strategy: str
    topic: str
    reason: str
    at: float = field(default_factory=lambda: time.time())


@dataclass
class LearnerAdaptation:
    """Behavioral overlay on declared survey profile (updates over time)."""
    learning_goals: List[str] = field(default_factory=list)
    goal_timeline: str = ""
    observed_pace: str = "moderate"   # slow | moderate | fast (inferred)
    avg_minutes_per_lesson: Optional[float] = None
    completion_samples: List[float] = field(default_factory=list)
    strategy_wins: Dict[str, int] = field(default_factory=dict)
    strategy_losses: Dict[str, int] = field(default_factory=dict)
    failed_approaches: List[FailedApproach] = field(default_factory=list)
    sensitivity_rules: List[SensitivityRule] = field(default_factory=list)
    known_triggers: List[str] = field(default_factory=list)
    profile_revision: int = 0

    def record_completion(self, minutes: float) -> None:
        self.completion_samples.append(minutes)
        if len(self.completion_samples) > 20:
            self.completion_samples = self.completion_samples[-20:]
        self.avg_minutes_per_lesson = sum(self.completion_samples) / len(self.completion_samples)
        avg = self.avg_minutes_per_lesson
        if avg < 15:
            self.observed_pace = "fast"
        elif avg > 35:
            self.observed_pace = "slow"
        else:
            self.observed_pace = "moderate"
        self.profile_revision += 1

    def record_strategy(self, strategy: str, *, success: bool) -> None:
        if success:
            self.strategy_wins[strategy] = self.strategy_wins.get(strategy, 0) + 1
        else:
            self.strategy_losses[strategy] = self.strategy_losses.get(strategy, 0) + 1
        self.profile_revision += 1

    def record_failed_approach(self, strategy: str, topic: str, reason: str) -> None:
        self.failed_approaches.append(FailedApproach(strategy=strategy, topic=topic, reason=reason))
        if len(self.failed_approaches) > 30:
            self.failed_approaches = self.failed_approaches[-30:]
        self.record_strategy(strategy, success=False)
        self.profile_revision += 1

    def record_trigger(self, trigger: str, reason: str, *, severity: str = "medium",
                       allow_retry: bool = False) -> None:
        rid = f"tr_{int(time.time())}_{len(self.sensitivity_rules)}"
        self.sensitivity_rules.append(SensitivityRule(
            rule_id=rid, trigger=trigger.strip().lower(), reason=reason,
            severity=severity, allow_retry=allow_retry,
        ))
        if trigger.strip().lower() not in self.known_triggers:
            self.known_triggers.append(trigger.strip().lower())
        self.profile_revision += 1

    def should_avoid(self, phrase_or_strategy: str) -> bool:
        key = (phrase_or_strategy or "").strip().lower()
        if not key:
            return False
        for rule in self.sensitivity_rules:
            if not rule.allow_retry and key in rule.trigger:
                return True
            if not rule.allow_retry and rule.trigger in key:
                return True
        return False

    def best_strategy(self, candidates: List[str]) -> Optional[str]:
        scored: List[tuple[float, str]] = []
        for c in candidates:
            if self.should_avoid(c):
                continue
            if any(f.strategy == c for f in self.failed_approaches[-5:]):
                continue
            w = self.strategy_wins.get(c, 0)
            l = self.strategy_losses.get(c, 0)
            score = (w + 1) / (w + l + 2)
            scored.append((score, c))
        if not scored:
            return candidates[0] if candidates else None
        scored.sort(reverse=True)
        return scored[0][1]

    def to_dict(self) -> dict:
        return {
            "learning_goals": self.learning_goals,
            "goal_timeline": self.goal_timeline,
            "observed_pace": self.observed_pace,
            "avg_minutes_per_lesson": self.avg_minutes_per_lesson,
            "strategy_wins": dict(self.strategy_wins),
            "strategy_losses": dict(self.strategy_losses),
            "failed_approaches": [
                {"strategy": f.strategy, "topic": f.topic, "reason": f.reason, "at": f.at}
                for f in self.failed_approaches[-10:]
            ],
            "sensitivity_rules": [
                {"rule_id": r.rule_id, "trigger": r.trigger, "reason": r.reason,
                 "allow_retry": r.allow_retry, "severity": r.severity}
                for r in self.sensitivity_rules[-15:]
            ],
            "known_triggers": self.known_triggers,
            "profile_revision": self.profile_revision,
        }


def merge_pacing_plan(
    signals: LearnerSignals,
    *,
    declared_pace: str = "moderate",
    adaptation: Optional[LearnerAdaptation] = None,
    class_type: ClassType = ClassType.GROUP,
    policy: Optional[AdaptivePolicy] = None,
) -> PacingPlan:
    """Merge behavioral signals, declared survey, and evolving adaptation."""
    base = (policy or AdaptivePolicy()).plan(signals, class_type=class_type)
    reasons = list(base.reasons)
    pacing, difficulty, reteach = base.pacing, base.difficulty, base.reteach

    if adaptation:
        if adaptation.observed_pace == "slow" and pacing is not Pacing.SLOW:
            pacing = Pacing.SLOW
            reasons.append("observed_slow_completion_pace")
        elif adaptation.observed_pace == "fast" and pacing is Pacing.NORMAL:
            pacing = Pacing.FAST
            reasons.append("observed_fast_completion_pace")

        if adaptation.sensitivity_rules:
            reteach = True
            reasons.append("sensitivity_rules_active->gentler_reteach")

    if declared_pace == "slow" and pacing is Pacing.FAST:
        pacing = Pacing.NORMAL
        reasons.append("declared_slow_overrides_fast_behavior")

    return PacingPlan(pacing=pacing, difficulty=difficulty, reteach=reteach, reasons=reasons)


# Phrases that suggest frustration — used by clients to auto-record triggers.
FRUSTRATION_MARKERS = (
    "this is stupid", "this makes no sense", "i hate this", "stop saying",
    "you already told me", "this doesn't work", "i'm angry", "i am angry",
    "too fast", "too slow", "confusing", "frustrated",
)


def detect_frustration(text: str) -> Optional[str]:
    lower = (text or "").lower()
    for marker in FRUSTRATION_MARKERS:
        if marker in lower:
            return marker
    return None
