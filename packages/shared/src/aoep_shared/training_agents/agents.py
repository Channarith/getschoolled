"""Cognitive training agents.

Five specialized, deterministic agents that train *how a person thinks* under
pressure rather than just handing them answers:

- :class:`SituationalAwarenessAgent` - Endsley's perceive -> comprehend -> project.
- :class:`ForecastingAgent` - pre-mortem: anticipate failure modes before they happen.
- :class:`RapidDecisionAgent` - OODA loop scoring under a split-second clock.
- :class:`CriticalThinkingAgent` - evaluates the learner's reasoning, flags biases.
- :class:`LearningBehaviorAgent` - adapts pacing/difficulty/tone to the learner,
  staying sensitive to frustration and overload.

All pure Python: no model server, network, or GPU. They reuse the platform's
:class:`~aoep_shared.adaptive.AdaptivePolicy` so behavior adaptation is
consistent with the live-class teaching loop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from aoep_shared.adaptive import AdaptivePolicy, LearnerSignals
from aoep_shared.schemas import ClassType

from .scenario import DecisionOption, ScenarioPhase

_STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "are", "but", "not", "has",
    "have", "from", "this", "that", "into", "off", "still", "gives", "give",
    "too", "far", "now", "out", "all", "any", "can", "its", "it's", "a", "an",
    "of", "to", "in", "on", "is", "at", "or", "if", "be", "as", "no",
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _mean(xs: List[float], default: float = 0.0) -> float:
    return (sum(xs) / len(xs)) if xs else default


def _keywords(text: str) -> List[str]:
    """Significant lowercase tokens (len>3, not a stopword) from a string."""
    toks = re.findall(r"[a-zA-Z']+", text.lower())
    return [t for t in toks if len(t) > 3 and t not in _STOPWORDS]


class TrainingAgentRole(str, Enum):
    LEARNING_BEHAVIOR = "learning_behavior"
    CRITICAL_THINKING = "critical_thinking"
    SITUATIONAL_AWARENESS = "situational_awareness"
    RAPID_DECISION = "rapid_decision"
    FORECASTING = "forecasting"


# --------------------------------------------------------------------------- #
# Situational awareness (Endsley): perceive -> comprehend -> project
# --------------------------------------------------------------------------- #
@dataclass
class SituationPicture:
    perception: List[str]
    comprehension: List[str]
    projection: List[str]
    sa_score: Optional[float] = None
    missed_cues: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "perception": list(self.perception),
            "comprehension": list(self.comprehension),
            "projection": list(self.projection),
            "sa_score": self.sa_score,
            "missed_cues": list(self.missed_cues),
        }


@dataclass
class SituationalAwarenessAgent:
    """Builds a 3-level situational picture and (optionally) scores recall."""

    def assess(
        self, phase: ScenarioPhase, noticed: Optional[List[str]] = None
    ) -> SituationPicture:
        perception = list(phase.cues)
        urgency = (
            "high" if phase.decision_window_s <= 8
            else "moderate" if phase.decision_window_s <= 12 else "manageable"
        )
        comprehension = [
            f"{len(phase.cues)} cues and {len(phase.threats)} active threats - "
            f"{urgency} time pressure.",
        ]
        if phase.recommended:
            comprehension.append(f"The picture points to: {phase.recommended}")
        projection = list(phase.threats) or [
            "No immediate threat, but stay ahead of the situation."
        ]

        sa_score: Optional[float] = None
        missed: List[str] = []
        if noticed is not None:
            said = " ".join(noticed).lower() if isinstance(noticed, list) else str(noticed).lower()
            matched = 0
            for cue in phase.cues:
                kws = _keywords(cue)
                if kws and any(k in said for k in kws):
                    matched += 1
                else:
                    missed.append(cue)
            sa_score = _clamp01(matched / max(1, len(phase.cues)))
        return SituationPicture(perception, comprehension, projection, sa_score, missed)


# --------------------------------------------------------------------------- #
# Forecasting / pre-mortem: prepare mentally before it goes wrong
# --------------------------------------------------------------------------- #
@dataclass
class RiskForecast:
    risk: str
    likelihood: str
    mitigation: str

    def as_dict(self) -> dict:
        return {"risk": self.risk, "likelihood": self.likelihood, "mitigation": self.mitigation}


@dataclass
class PreMortem:
    headline: str
    risks: List[RiskForecast]
    contingency: str

    def as_dict(self) -> dict:
        return {
            "headline": self.headline,
            "risks": [r.as_dict() for r in self.risks],
            "contingency": self.contingency,
        }


@dataclass
class ForecastingAgent:
    """Runs a pre-mortem: assume failure, then plan the response in advance."""

    def premortem(self, phase: ScenarioPhase) -> PreMortem:
        threats = phase.threats or ["losing control of the situation"]
        recommended = phase.recommended or (
            phase.best_option().text if phase.options else "act on the strongest cue"
        )
        risks = [
            RiskForecast(
                risk=t,
                likelihood="high" if i == 0 else "medium",
                mitigation=f"Pre-decide your response now so it's automatic: {recommended}",
            )
            for i, t in enumerate(threats)
        ]
        headline = (
            f"Pre-mortem - imagine this has already gone wrong. The most likely "
            f"cause is: {threats[0]}."
        )
        return PreMortem(headline=headline, risks=risks, contingency=recommended)


# --------------------------------------------------------------------------- #
# Rapid decision (OODA) under a split-second clock
# --------------------------------------------------------------------------- #
@dataclass
class RapidDecisionResult:
    quality: float
    timeliness: float
    score: float
    on_time: bool
    elapsed_s: float
    window_s: float
    ooda: Dict[str, str]
    note: str

    def as_dict(self) -> dict:
        return {
            "quality": round(self.quality, 3),
            "timeliness": round(self.timeliness, 3),
            "score": round(self.score, 3),
            "on_time": self.on_time,
            "elapsed_s": round(self.elapsed_s, 2),
            "window_s": self.window_s,
            "ooda": dict(self.ooda),
            "note": self.note,
        }


@dataclass
class RapidDecisionAgent:
    """Scores a decision on quality AND speed (the split-minute dimension)."""

    def score(
        self, phase: ScenarioPhase, option: DecisionOption, elapsed_s: float
    ) -> RapidDecisionResult:
        window = max(1.0, float(phase.decision_window_s))
        elapsed = max(0.0, float(elapsed_s))
        if elapsed <= window:
            timeliness = 1.0
        else:
            over = (elapsed - window) / window
            timeliness = _clamp01(1.0 - 0.6 * over)
        on_time = elapsed <= window
        quality = _clamp01(option.score)
        # Quality dominates (a fast wrong call is still wrong); timeliness scales
        # the credit so a correct-but-slow answer loses a little.
        score = _clamp01(quality * (0.7 + 0.3 * timeliness))

        if not on_time and quality >= 0.7:
            note = (
                f"Right call, but {elapsed:.0f}s vs a {window:.0f}s window - in a real "
                f"emergency that delay can cost you. Build the reflex."
            )
        elif on_time and quality >= 0.7:
            note = f"Decisive and correct - {elapsed:.0f}s, inside the {window:.0f}s window."
        elif quality < 0.4 and on_time:
            note = "Fast but wrong - speed without reading the cues is dangerous. Slow is smooth, smooth is fast."
        else:
            note = "Reassess: weigh the cues against the clock before you commit."

        ooda = {
            "observe": f"{len(phase.cues)} cues available; {len(phase.threats)} threats.",
            "orient": (
                "Choice aligns with the textbook action."
                if quality >= 0.7 else
                "Choice diverges from the recommended action - re-orient on the cues."
            ),
            "decide": option.text,
            "act": option.consequence or "(committed)",
        }
        return RapidDecisionResult(
            quality=quality, timeliness=timeliness, score=score, on_time=on_time,
            elapsed_s=elapsed, window_s=window, ooda=ooda, note=note,
        )


# --------------------------------------------------------------------------- #
# Critical thinking: evaluate the learner's reasoning, flag biases/fallacies
# --------------------------------------------------------------------------- #
@dataclass
class ReasoningReview:
    reasoning_score: float
    rubric: Dict[str, float]
    detected_issues: List[str]
    strengths: List[str]
    socratic_probe: str
    emotional_markers: int = 0

    def as_dict(self) -> dict:
        return {
            "reasoning_score": round(self.reasoning_score, 3),
            "rubric": {k: round(v, 3) for k, v in self.rubric.items()},
            "detected_issues": list(self.detected_issues),
            "strengths": list(self.strengths),
            "socratic_probe": self.socratic_probe,
            "emotional_markers": self.emotional_markers,
        }


@dataclass
class CriticalThinkingAgent:
    """Rates a free-text rationale on a reasoning rubric and probes Socratically."""

    _ABSOLUTES = ("always", "never", "everyone", "no one", "nobody", "everything", "impossible")
    _EMOTIONAL = ("panic", "panicked", "freak", "scared", "gut feeling", "just feel",
                  "instinct told", "felt like", "i guess")
    _ALT_MARKERS = ("instead", "rather", "alternative", "could also", "other option",
                    "versus", " vs ", "weigh", "trade-off", "tradeoff", "on the other hand")
    _CAUSAL = ("because", "so that", "therefore", "since", "that way", "in order to", "due to")

    def evaluate(
        self, phase: ScenarioPhase, option: DecisionOption, rationale: str
    ) -> ReasoningReview:
        text = (rationale or "").strip()
        low = text.lower()
        words = re.findall(r"[a-zA-Z']+", low)
        issues: List[str] = []
        strengths: List[str] = []

        if not words:
            return ReasoningReview(
                reasoning_score=0.0,
                rubric={"clarity": 0.0, "evidence": 0.0, "depth": 0.0, "alternatives": 0.0},
                detected_issues=["no rationale given - articulating *why* is how the skill transfers"],
                strengths=[],
                socratic_probe=(
                    f"In one sentence, why is \"{option.text}\" the right move here - "
                    f"which cue drives it?"
                ),
                emotional_markers=0,
            )

        # Evidence: references to the situation's cues/threats.
        key_terms: set[str] = set()
        for src in list(phase.cues) + list(phase.threats):
            key_terms.update(_keywords(src))
        evidence_hits = sum(1 for t in key_terms if t in low)
        evidence = _clamp01(evidence_hits / 2.0)
        if evidence_hits:
            strengths.append("grounded the decision in the situation's cues")

        # Alternatives considered.
        if any(m in low for m in self._ALT_MARKERS):
            alternatives = 1.0
            strengths.append("weighed alternatives / trade-offs")
        elif "because" in low or "if" in words:
            alternatives = 0.5
        else:
            alternatives = 0.0

        # Depth: causal reasoning + enough substance.
        causal = any(m in low for m in self._CAUSAL)
        depth = _clamp01(len(words) / 40.0)
        depth = min(1.0, depth + (0.3 if causal else 0.0))
        if causal:
            strengths.append("gave a causal reason (because/so/therefore)")

        # Clarity, minus penalties for fallacies / emotional reasoning.
        clarity = 1.0
        emotional_markers = sum(1 for m in self._EMOTIONAL if m in low)
        if any(w in low for w in self._ABSOLUTES):
            issues.append("overgeneralization - absolute language ('always/never') rarely holds; qualify it")
            clarity -= 0.15
        if emotional_markers:
            issues.append("emotional reasoning - decide from cues and procedure, not just feeling")
            clarity -= 0.1
        if len(words) < 4:
            issues.append("hasty / under-justified - too brief to show your reasoning")
            depth = min(depth, 0.2)
            clarity -= 0.1
        clarity = _clamp01(clarity)

        rubric = {
            "clarity": clarity,
            "evidence": evidence,
            "depth": depth,
            "alternatives": alternatives,
        }
        reasoning_score = _clamp01(
            0.3 * clarity + 0.3 * evidence + 0.25 * depth + 0.15 * alternatives
        )

        best = phase.best_option()
        if option.id == best.id:
            socratic = (
                "Solid choice. Now stress-test it: what single change in the situation "
                "would make this the WRONG move?"
            )
        else:
            socratic = (
                f"You chose \"{option.text}\". What evidence argues against the stronger "
                f"option, \"{best.text}\"? Walk me through the trade-off."
            )

        return ReasoningReview(
            reasoning_score=reasoning_score,
            rubric=rubric,
            detected_issues=issues,
            strengths=strengths,
            socratic_probe=socratic,
            emotional_markers=emotional_markers,
        )


# --------------------------------------------------------------------------- #
# Learning behavior: adapt to the learner (sensitive to overload/frustration)
# --------------------------------------------------------------------------- #
@dataclass
class BehaviorAdaptation:
    pacing: str
    difficulty: str
    coaching_style: str   # scaffold | standard | stretch
    tone: str             # supportive | neutral | challenging
    window_scale: float   # multiply decision windows (more time when struggling)
    flags: List[str]
    recommendation: str

    def as_dict(self) -> dict:
        return {
            "pacing": self.pacing,
            "difficulty": self.difficulty,
            "coaching_style": self.coaching_style,
            "tone": self.tone,
            "window_scale": round(self.window_scale, 2),
            "flags": list(self.flags),
            "recommendation": self.recommendation,
        }


@dataclass
class LearningBehaviorAgent:
    """Turns accumulated performance into a coaching adjustment.

    Reuses the platform :class:`AdaptivePolicy` for pacing/difficulty so drills
    adapt the same way live classes do, then layers on tone/scaffolding that is
    deliberately sensitive to frustration and cognitive overload.
    """

    policy: AdaptivePolicy = field(default_factory=AdaptivePolicy)

    def adapt(
        self,
        *,
        scores: List[float],
        timeliness: List[float],
        reasoning_scores: List[float],
        frustration_markers: int = 0,
        class_type: ClassType = ClassType.SOLO,
    ) -> BehaviorAdaptation:
        avg = _mean(scores, 0.5)
        recent = scores[-3:]
        recent_avg = _mean(recent, avg)
        avg_time = _mean(timeliness, 1.0)
        avg_reason = _mean(reasoning_scores, 0.5)

        # Map speed -> a latency proxy the AdaptivePolicy understands (fast=low s).
        latency_proxy = 2.0 + (1.0 - _clamp01(avg_time)) * 12.0
        signals = LearnerSignals(
            topic_mastery=avg,
            quiz_accuracy=recent_avg,
            avg_response_latency_s=latency_proxy,
            attention_trend=_clamp01(avg_time),
            question_rate=0.0,
        )
        plan = self.policy.plan(signals, class_type=class_type)

        flags: List[str] = []
        coaching_style = "standard"
        tone = "neutral"
        window_scale = 1.0
        recommendation = "Keep going - your pacing looks steady."

        struggling = recent_avg < 0.4
        excelling = recent_avg >= 0.8 and avg_time >= 0.7
        rushing = avg_time >= 0.85 and recent_avg < 0.5
        overload = frustration_markers >= 2 or (struggling and avg_reason < 0.3)

        if overload:
            flags.append("overload_detected")
            coaching_style = "scaffold"
            tone = "supportive"
            window_scale = 1.6
            recommendation = (
                "You're carrying a lot right now. Let's take a breath and slow the clock - "
                "we'll rebuild this one small step at a time. Mistakes here are exactly how "
                "the reflex gets trained."
            )
        elif struggling:
            flags.append("struggling")
            coaching_style = "scaffold"
            tone = "supportive"
            window_scale = 1.4
            recommendation = (
                "Let's add a little time and walk the cue-by-cue read before you decide."
            )
        elif rushing:
            flags.append("rushing")
            coaching_style = "standard"
            tone = "neutral"
            window_scale = 1.0
            recommendation = (
                "You're fast but missing cues - slow down half a beat and read the picture "
                "before committing."
            )
        elif excelling:
            flags.append("on_a_roll")
            coaching_style = "stretch"
            tone = "challenging"
            window_scale = 0.85
            recommendation = (
                "Strong work - tightening the clock and raising difficulty to keep you at "
                "the edge of your ability."
            )

        return BehaviorAdaptation(
            pacing=plan.pacing.value,
            difficulty=plan.difficulty.value,
            coaching_style=coaching_style,
            tone=tone,
            window_scale=window_scale,
            flags=flags,
            recommendation=recommendation,
        )
