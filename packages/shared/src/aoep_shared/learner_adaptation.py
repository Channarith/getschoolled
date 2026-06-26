"""Evolving learner profile: pace, goals, strategy outcomes, sensitivity memory."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .adaptive import AdaptivePolicy, Difficulty, LearnerSignals, Pacing, PacingPlan
from .course_complexity import finish_pace_label
from .schemas import ClassType

WELLNESS_STATES = frozenset({"ok", "low_energy", "stressed", "unwell"})


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
class CourseFinishRecord:
    course_id: str
    minutes: float
    expected_min: float
    complexity: int
    pace_vs_expected: str
    finished_at: float = field(default_factory=lambda: time.time())


@dataclass
class LearnerAdaptation:
    """Behavioral overlay on declared survey profile (updates over time)."""
    learning_goals: List[str] = field(default_factory=list)
    goal_timeline: str = ""
    observed_pace: str = "moderate"   # slow | moderate | fast (inferred)
    avg_minutes_per_lesson: Optional[float] = None
    completion_samples: List[float] = field(default_factory=list)
    course_finishes: List[CourseFinishRecord] = field(default_factory=list)
    strategy_wins: Dict[str, int] = field(default_factory=dict)
    strategy_losses: Dict[str, int] = field(default_factory=dict)
    failed_approaches: List[FailedApproach] = field(default_factory=list)
    sensitivity_rules: List[SensitivityRule] = field(default_factory=list)
    known_triggers: List[str] = field(default_factory=list)
    wellness_state: str = "ok"
    wellness_reason: str = ""
    wellness_updated_at: Optional[float] = None
    lx_score_ema: Optional[float] = None
    lx_samples: List[float] = field(default_factory=list)
    strategy_bandit: Dict[str, List[float]] = field(default_factory=dict)
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

    def record_course_finish(
        self,
        course_id: str,
        minutes: float,
        *,
        expected_min: float,
        complexity: int = 3,
    ) -> CourseFinishRecord:
        pace = finish_pace_label(minutes, expected_min)
        rec = CourseFinishRecord(
            course_id=course_id,
            minutes=minutes,
            expected_min=expected_min,
            complexity=complexity,
            pace_vs_expected=pace,
        )
        self.course_finishes.append(rec)
        if len(self.course_finishes) > 30:
            self.course_finishes = self.course_finishes[-30:]
        self.record_completion(minutes)
        return rec

    def record_wellness(self, state: str, reason: str = "") -> None:
        st = (state or "ok").strip().lower()
        if st not in WELLNESS_STATES:
            st = "ok"
        self.wellness_state = st
        self.wellness_reason = (reason or "").strip()
        self.wellness_updated_at = time.time()
        if st in ("stressed", "unwell", "low_energy"):
            self.record_trigger(
                f"wellness:{st}",
                self.wellness_reason or st,
                severity="high",
                allow_retry=True,
            )
        else:
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

    def avg_complexity_completed(self) -> Optional[float]:
        if not self.course_finishes:
            return None
        return sum(r.complexity for r in self.course_finishes) / len(self.course_finishes)

    def record_lx_sample(
        self,
        score: float,
        *,
        strategy: str = "",
        success: Optional[bool] = None,
    ) -> None:
        from .learning_experience import (
            bandit_from_dict, bandit_to_dict, record_strategy_outcome, update_lx_ema,
        )

        self.lx_samples.append(float(score))
        if len(self.lx_samples) > 40:
            self.lx_samples = self.lx_samples[-40:]
        self.lx_score_ema = update_lx_ema(self.lx_score_ema, float(score))
        if strategy:
            bandit = bandit_from_dict(self.strategy_bandit or None)
            if success is None:
                success = score >= 70.0
            record_strategy_outcome(bandit, strategy, success=success)
            self.strategy_bandit = bandit_to_dict(bandit)
            self.record_strategy(strategy, success=success)
        self.profile_revision += 1

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
            "course_finishes": [
                {
                    "course_id": r.course_id,
                    "minutes": r.minutes,
                    "expected_min": r.expected_min,
                    "complexity": r.complexity,
                    "pace_vs_expected": r.pace_vs_expected,
                    "finished_at": r.finished_at,
                }
                for r in self.course_finishes[-15:]
            ],
            "wellness_state": self.wellness_state,
            "wellness_reason": self.wellness_reason,
            "wellness_updated_at": self.wellness_updated_at,
            "lx_score_ema": self.lx_score_ema,
            "lx_samples": self.lx_samples[-20:],
            "strategy_bandit": dict(self.strategy_bandit),
            "profile_revision": self.profile_revision,
        }


def adaptation_from_dict(raw: dict, *, learning_goals: Optional[List[str]] = None,
                         goal_timeline: str = "") -> LearnerAdaptation:
    """Rebuild LearnerAdaptation from persisted JSON."""
    adapt = LearnerAdaptation(
        learning_goals=list(learning_goals or raw.get("learning_goals", [])),
        goal_timeline=str(goal_timeline or raw.get("goal_timeline", "")),
        observed_pace=str(raw.get("observed_pace", "moderate")),
        avg_minutes_per_lesson=raw.get("avg_minutes_per_lesson"),
        completion_samples=list(raw.get("completion_samples", [])),
        strategy_wins=dict(raw.get("strategy_wins", {})),
        strategy_losses=dict(raw.get("strategy_losses", {})),
        known_triggers=list(raw.get("known_triggers", [])),
        wellness_state=str(raw.get("wellness_state", "ok")),
        wellness_reason=str(raw.get("wellness_reason", "")),
        wellness_updated_at=raw.get("wellness_updated_at"),
        lx_score_ema=raw.get("lx_score_ema"),
        lx_samples=list(raw.get("lx_samples", [])),
        strategy_bandit=dict(raw.get("strategy_bandit", {})),
        profile_revision=int(raw.get("profile_revision", 0)),
    )
    adapt.failed_approaches = [
        FailedApproach(**f) for f in raw.get("failed_approaches", [])
    ]
    adapt.sensitivity_rules = [
        SensitivityRule(**r) for r in raw.get("sensitivity_rules", [])
    ]
    adapt.course_finishes = [
        CourseFinishRecord(**r) for r in raw.get("course_finishes", [])
    ]
    return adapt


def merge_pacing_plan(
    signals: LearnerSignals,
    *,
    declared_pace: str = "moderate",
    adaptation: Optional[LearnerAdaptation] = None,
    class_type: ClassType = ClassType.GROUP,
    policy: Optional[AdaptivePolicy] = None,
    course_complexity: int = 3,
    wellness_state: str = "ok",
) -> PacingPlan:
    """Merge behavioral signals, declared survey, wellness, and evolving adaptation."""
    base = (policy or AdaptivePolicy()).plan(signals, class_type=class_type)
    reasons = list(base.reasons)
    pacing, difficulty, reteach = base.pacing, base.difficulty, base.reteach

    effective_wellness = wellness_state
    if adaptation and adaptation.wellness_state in WELLNESS_STATES - {"ok"}:
        effective_wellness = adaptation.wellness_state

    if effective_wellness in ("unwell", "stressed", "low_energy"):
        pacing = Pacing.SLOW
        difficulty = Difficulty.EASY
        reteach = True
        reasons.append(f"wellness_{effective_wellness}->gentle_session")

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

        if course_complexity >= 4 and adaptation.observed_pace == "slow":
            difficulty = Difficulty.EASY
            reasons.append("high_complexity_slow_learner")

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

WELLNESS_MARKERS = (
    ("unwell", ("sick", "not feeling well", "ill", "headache", "migraine", "nausea")),
    ("low_energy", ("tired", "exhausted", "no energy", "sleepy", "burnt out", "burned out")),
    ("stressed", ("stressed", "anxious", "overwhelmed", "bad mood", "upset", "worried")),
)


def detect_frustration(text: str) -> Optional[str]:
    lower = (text or "").lower()
    for marker in FRUSTRATION_MARKERS:
        if marker in lower:
            return marker
    return None


def detect_wellness(text: str) -> Optional[tuple[str, str]]:
    """Return (wellness_state, matched_phrase) when mood/health cues appear."""
    lower = (text or "").lower()
    for state, markers in WELLNESS_MARKERS:
        for marker in markers:
            if marker in lower:
                return state, marker
    return None
