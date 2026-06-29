"""Cognitive Trainer — master integration module.

Ties together five specialist training agents into a single cohesive
interface for the orchestrator and meeting-agents lab:

  BehaviorAdaptationAgent  — monitors micro-patterns, adjusts training pace/depth
  CriticalThinkingTrainer  — Socratic questioning, argument analysis, Bloom's taxonomy
  SituationalAwarenessAgent — OODA / DECIDE framework scenario drills
  RapidDecisionAgent        — time-pressured split-second decision training
  EmergencyScenarioAgent    — full end-to-end emergency simulations + AAR
  MentalReadinessAgent      — pre-mortem, rehearsal, TEM, stress inoculation

Design principles
-----------------
- Sensitive: wellness and stress signals gate which agents are activated and
  at what intensity. A learner flagged as stressed/unwell is never pushed into
  high-pressure emergency simulations; they receive restorative exercises first.
- Adaptive: every training event feeds back into BehaviorAdaptationAgent to
  refine the cognitive profile over time.
- Explainable: every recommendation comes with a human-readable rationale.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .critical_thinking import (
    BloomLevel,
    CriticalThinkingResponse,
    CriticalThinkingTrainer,
    SocraticQuestion,
    bloom_for_mastery,
)
from .emergency_scenarios import (
    AARReport,
    EmergencyScenarioAgent,
    ScenarioDomain,
    SimulationRun,
)
from .mental_readiness import (
    CognitivePressure,
    MentalReadinessAgent,
    ReadinessExercise,
    RegulationCheckIn,
    StressInoculationSession,
)
from .rapid_decision import (
    DrillResult,
    PressureLevel,
    RapidDecisionAgent,
    RapidDecisionSession,
)
from .situational_awareness import (
    DECIDEState,
    OODAState,
    SituationalAwarenessAgent,
    SituationalAwarenessResult,
)


# ---------------------------------------------------------------------------
# Behavior Adaptation Agent
# ---------------------------------------------------------------------------
class LearningPattern(str, Enum):
    """Micro-patterns detected from learner interaction history."""
    HESITATES_UNDER_TIME_PRESSURE = "hesitates_under_time_pressure"
    RUSHES_WITHOUT_READING = "rushes_without_reading"
    AVOIDS_ANALYSIS_QUESTIONS = "avoids_analysis_questions"
    STRONG_RECALL_WEAK_APPLICATION = "strong_recall_weak_application"
    CONSISTENT_LOGICAL_FALLACIES = "consistent_logical_fallacies"
    MISSES_ENVIRONMENTAL_CUES = "misses_environmental_cues"
    OVER_RELIES_ON_SINGLE_FRAMEWORK = "over_relies_on_single_framework"
    HEALTHY_PATTERN = "healthy_pattern"


@dataclass
class CognitiveLearnerProfile:
    """Persistent cognitive training profile for one learner."""
    learner_id: str
    # Mastery scores per skill (0..1)
    skill_mastery: Dict[str, float] = field(default_factory=dict)
    # Pattern detection
    detected_patterns: List[LearningPattern] = field(default_factory=list)
    pattern_counts: Dict[str, int] = field(default_factory=dict)
    # Session history
    completed_scenarios: List[str] = field(default_factory=list)
    completed_drills: List[str] = field(default_factory=list)
    bloom_history: List[str] = field(default_factory=list)  # BloomLevel values
    # Wellness / readiness
    wellness_state: str = "ok"
    last_check_in_at: Optional[float] = None
    # Training path progress
    total_cognitive_sessions: int = 0
    cognitive_training_minutes: float = 0.0
    # Recent exercise history for variety
    recent_exercises: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def update_skill(self, skill: str, delta: float) -> None:
        current = self.skill_mastery.get(skill, 0.4)
        self.skill_mastery[skill] = max(0.0, min(1.0, current + delta))
        self.updated_at = time.time()

    def get_skill(self, skill: str) -> float:
        return self.skill_mastery.get(skill, 0.4)

    def record_pattern(self, pattern: LearningPattern) -> None:
        key = pattern.value
        self.pattern_counts[key] = self.pattern_counts.get(key, 0) + 1
        if pattern not in self.detected_patterns:
            self.detected_patterns.append(pattern)

    def record_exercise(self, exercise: str) -> None:
        self.recent_exercises.append(exercise)
        if len(self.recent_exercises) > 10:
            self.recent_exercises = self.recent_exercises[-10:]

    def to_dict(self) -> dict:
        return {
            "learner_id": self.learner_id,
            "skill_mastery": dict(self.skill_mastery),
            "detected_patterns": [p.value for p in self.detected_patterns],
            "pattern_counts": dict(self.pattern_counts),
            "completed_scenarios": list(self.completed_scenarios),
            "completed_drills": list(self.completed_drills),
            "wellness_state": self.wellness_state,
            "total_cognitive_sessions": self.total_cognitive_sessions,
            "cognitive_training_minutes": round(self.cognitive_training_minutes, 1),
            "recent_exercises": list(self.recent_exercises),
        }


class BehaviorAdaptationAgent:
    """Monitors cross-session micro-patterns and updates the cognitive profile.

    Called after every training event to detect systematic gaps and adjust
    the training plan accordingly.
    """

    def detect_patterns(
        self, profile: CognitiveLearnerProfile, event: dict
    ) -> List[LearningPattern]:
        """Analyse a training event for behavioral patterns."""
        patterns: List[LearningPattern] = []
        event_type = event.get("type", "")

        if event_type == "rapid_drill":
            outcome = event.get("outcome", "")
            time_taken = float(event.get("time_taken_s", 0))
            allowed = float(event.get("allowed_s", 10))
            if outcome == "timeout" or (time_taken > allowed * 0.9 and "incorrect" in outcome):
                patterns.append(LearningPattern.HESITATES_UNDER_TIME_PRESSURE)
            if "incorrect_fast" in outcome and time_taken < allowed * 0.3:
                patterns.append(LearningPattern.RUSHES_WITHOUT_READING)

        if event_type == "critical_thinking":
            bloom = event.get("bloom_level", "")
            score = float(event.get("score", 0.5))
            if bloom in ("analyze", "evaluate", "create") and score < 0.4:
                patterns.append(LearningPattern.AVOIDS_ANALYSIS_QUESTIONS)
            if bloom in ("remember", "understand") and score > 0.8:
                # Good recall — check if application is weaker
                app_mastery = profile.skill_mastery.get("application", 0.5)
                if app_mastery < 0.45:
                    patterns.append(LearningPattern.STRONG_RECALL_WEAK_APPLICATION)
            fallacies = event.get("fallacies_found", [])
            if len(fallacies) >= 2:
                patterns.append(LearningPattern.CONSISTENT_LOGICAL_FALLACIES)

        if event_type == "situational_awareness":
            blind_spots = event.get("blind_spots", [])
            if any("environmental" in b.lower() or "weather" in b.lower()
                   or "temperature" in b.lower() for b in blind_spots):
                patterns.append(LearningPattern.MISSES_ENVIRONMENTAL_CUES)
            framework_count = profile.pattern_counts.get("framework_used", 0)
            if framework_count > 3 and len(set(profile.recent_exercises)) <= 2:
                patterns.append(LearningPattern.OVER_RELIES_ON_SINGLE_FRAMEWORK)

        if not patterns:
            patterns.append(LearningPattern.HEALTHY_PATTERN)

        for p in patterns:
            profile.record_pattern(p)

        return patterns

    def adaptation_plan(self, profile: CognitiveLearnerProfile) -> Dict[str, str]:
        """Return a training adjustment plan based on detected patterns."""
        plan: Dict[str, str] = {}
        counts = profile.pattern_counts

        if counts.get(LearningPattern.HESITATES_UNDER_TIME_PRESSURE.value, 0) >= 2:
            plan["rapid_decision"] = "Increase DELIBERATE pressure drills; graduate slowly"
        if counts.get(LearningPattern.RUSHES_WITHOUT_READING.value, 0) >= 2:
            plan["critical_thinking"] = "Enforce minimum-word-count responses; add UNDERSTAND-level Bloom questions"
        if counts.get(LearningPattern.AVOIDS_ANALYSIS_QUESTIONS.value, 0) >= 2:
            plan["bloom_target"] = "Stay at APPLY level; scaffold ANALYZE with worked examples"
        if counts.get(LearningPattern.CONSISTENT_LOGICAL_FALLACIES.value, 0) >= 2:
            plan["fallacy_training"] = "Dedicated argument analysis module before Socratic progression"
        if counts.get(LearningPattern.MISSES_ENVIRONMENTAL_CUES.value, 0) >= 2:
            plan["situational_awareness"] = "Restart OODA OBSERVE phase focus; add environmental cue salience drills"
        if counts.get(LearningPattern.OVER_RELIES_ON_SINGLE_FRAMEWORK.value, 0) >= 2:
            plan["framework_variety"] = "Force alternate framework (DECIDE vs OODA) for next three scenarios"

        if not plan:
            plan["status"] = "Profile healthy — progress to next difficulty tier"

        return plan

    def wellness_gating(
        self, profile: CognitiveLearnerProfile, requested_exercise: str
    ) -> tuple[str, str]:
        """Gate exercise selection by wellness; return (approved_exercise, reason)."""
        high_intensity = {
            "emergency_scenario", "split_second_drill", "stress_inoculation_high",
        }
        wellness = profile.wellness_state
        if wellness in ("stressed", "unwell") and requested_exercise in high_intensity:
            return "grounding_breath", f"Wellness state '{wellness}' — high-intensity training deferred"
        if wellness == "low_energy" and requested_exercise == "emergency_scenario":
            return "mental_rehearsal", "Low energy — mental rehearsal is preparatory without full simulation load"
        return requested_exercise, "approved"


# ---------------------------------------------------------------------------
# CognitiveTrainer — unified facade
# ---------------------------------------------------------------------------
class CognitiveTrainer:
    """Top-level cognitive training coordinator.

    Wraps all specialist agents; exposes a single API for the orchestrator
    and meeting-agents lab.  Sensitive, adaptive, explainable.
    """

    def __init__(self) -> None:
        self.behavior = BehaviorAdaptationAgent()
        self.critical_thinking = CriticalThinkingTrainer()
        self.situational = SituationalAwarenessAgent()
        self.rapid_decision = RapidDecisionAgent()
        self.emergency = EmergencyScenarioAgent()
        self.mental_readiness = MentalReadinessAgent()

    # --- Profile management ------------------------------------------------
    def create_profile(self, learner_id: str) -> CognitiveLearnerProfile:
        return CognitiveLearnerProfile(learner_id=learner_id)

    # --- Wellness & check-in -----------------------------------------------
    def check_in(
        self,
        profile: CognitiveLearnerProfile,
        stress_level: int,
        focus_level: int,
    ) -> RegulationCheckIn:
        result = self.mental_readiness.check_in(
            stress_level, focus_level, profile.wellness_state
        )
        profile.wellness_state = (
            "stressed" if stress_level >= 8
            else "low_energy" if focus_level <= 3
            else "ok"
        )
        profile.last_check_in_at = time.time()
        return result

    # --- Session start: pick appropriate exercise --------------------------
    def recommend_next_session(
        self, profile: CognitiveLearnerProfile
    ) -> Dict[str, str]:
        """Return the recommended next training exercise with rationale."""
        approved, gate_reason = self.behavior.wellness_gating(
            profile,
            requested_exercise="emergency_scenario"
            if profile.total_cognitive_sessions > 5 else "critical_thinking",
        )
        adaptation = self.behavior.adaptation_plan(profile)

        # Pick domain from weakest skill
        weakest_skill = min(profile.skill_mastery, key=profile.skill_mastery.get) \
            if profile.skill_mastery else "critical_thinking"
        weakest_mastery = profile.get_skill(weakest_skill)

        bloom = bloom_for_mastery(weakest_mastery)
        pressure = self.mental_readiness.cognitive_pressure(
            profile.wellness_state, weakest_mastery
        )

        recent_ex = [ReadinessExercise(e) for e in profile.recent_exercises
                     if e in ReadinessExercise._value2member_map_]
        recommended_readiness = self.mental_readiness.recommend_exercise(
            profile.wellness_state, weakest_mastery, recent_ex
        )

        return {
            "approved_exercise": approved,
            "wellness_gate": gate_reason,
            "weakest_skill": weakest_skill,
            "weakest_mastery": str(round(weakest_mastery, 2)),
            "bloom_level": bloom.value,
            "cognitive_pressure": pressure.value,
            "readiness_exercise": recommended_readiness.value,
            "adaptation_notes": str(adaptation),
        }

    # --- Critical thinking session -----------------------------------------
    def critical_thinking_question(
        self,
        profile: CognitiveLearnerProfile,
        term: str,
        passage: str,
        *,
        scenario: str = "",
        claim: str = "",
    ) -> SocraticQuestion:
        mastery = profile.get_skill("critical_thinking")
        return self.critical_thinking.next_question(
            term, passage,
            mastery=mastery,
            wellness_state=profile.wellness_state,
            scenario=scenario,
            claim=claim,
        )

    def critical_thinking_evaluate(
        self,
        profile: CognitiveLearnerProfile,
        question: SocraticQuestion,
        answer: str,
    ) -> CriticalThinkingResponse:
        result = self.critical_thinking.evaluate(
            question, answer, wellness_state=profile.wellness_state
        )
        delta = 0.05 if result.score >= 0.75 else (-0.03 if result.score < 0.4 else 0.0)
        profile.update_skill("critical_thinking", delta)
        profile.record_exercise("critical_thinking")
        self.behavior.detect_patterns(profile, {
            "type": "critical_thinking",
            "bloom_level": question.bloom_level.value,
            "score": result.score,
            "fallacies_found": [],
        })
        return result

    # --- Situational awareness session -------------------------------------
    def sa_list_scenarios(self, domain: Optional[str] = None):
        return self.situational.list_scenarios(domain)

    def sa_ooda_prompt(
        self,
        profile: CognitiveLearnerProfile,
        scenario_id: str,
        phase,
    ) -> str:
        scenario = self.situational.get_scenario(scenario_id)
        if not scenario:
            return f"Scenario {scenario_id!r} not found."
        return self.situational.ooda_prompt(phase, scenario, wellness_state=profile.wellness_state)

    def sa_ooda_result(
        self,
        profile: CognitiveLearnerProfile,
        state: OODAState,
        scenario_id: str,
    ) -> SituationalAwarenessResult:
        scenario = self.situational.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id!r} not found")
        result = self.situational.ooda_result(state, scenario)
        delta = 0.08 if result.overall_score >= 0.8 else (-0.04 if result.overall_score < 0.4 else 0.02)
        profile.update_skill("situational_awareness", delta)
        profile.completed_scenarios.append(scenario_id)
        profile.record_exercise("situational_awareness")
        self.behavior.detect_patterns(profile, {
            "type": "situational_awareness",
            "blind_spots": result.blind_spots,
        })
        return result

    # --- Rapid decision session --------------------------------------------
    def rd_evaluate(
        self,
        profile: CognitiveLearnerProfile,
        drill_id: str,
        chosen_label: str,
        time_taken_s: float,
        pressure_level: PressureLevel,
        session: Optional[RapidDecisionSession] = None,
    ) -> Optional[DrillResult]:
        drill = self.rapid_decision.get_drill(drill_id)
        if not drill:
            return None
        from .rapid_decision import DrillAttempt
        attempt = DrillAttempt(
            drill_id=drill_id,
            chosen_label=chosen_label,
            time_taken_s=time_taken_s,
            pressure_level=pressure_level,
        )
        result = self.rapid_decision.evaluate_attempt(drill, attempt, session)
        correct = result.outcome.value.startswith("correct")
        delta = 0.06 if correct else -0.03
        profile.update_skill("rapid_decision", delta)
        profile.completed_drills.append(drill_id)
        profile.record_exercise("rapid_decision")
        self.behavior.detect_patterns(profile, {
            "type": "rapid_drill",
            "outcome": result.outcome.value,
            "time_taken_s": time_taken_s,
            "allowed_s": result.allowed_seconds,
        })
        return result

    # --- Emergency scenario session ----------------------------------------
    def em_list_scenarios(self, domain: Optional[ScenarioDomain] = None):
        return self.emergency.list_scenarios(domain)

    def em_start(
        self, profile: CognitiveLearnerProfile, scenario_id: str
    ) -> Optional[SimulationRun]:
        # Wellness gate: stressed/unwell → block emergency simulation
        if profile.wellness_state in ("stressed", "unwell"):
            return None
        scenario = self.emergency.get_scenario(scenario_id)
        if not scenario:
            return None
        return self.emergency.start_run(scenario, profile.learner_id)

    def em_aar(
        self,
        profile: CognitiveLearnerProfile,
        run: SimulationRun,
    ) -> Optional[AARReport]:
        scenario = self.emergency.get_scenario(run.scenario_id)
        if not scenario:
            return None
        aar = self.emergency.generate_aar(run, scenario)
        delta = 0.10 if aar.outcome_score >= 0.8 else (-0.05 if aar.outcome_score < 0.4 else 0.03)
        profile.update_skill(f"emergency_{scenario.domain.value}", delta)
        profile.completed_scenarios.append(run.scenario_id)
        profile.record_exercise("emergency_scenario")
        return aar

    # --- Mental readiness session ------------------------------------------
    def readiness_pre_mortem(
        self,
        profile: CognitiveLearnerProfile,
        plan: str,
        failure_modes: List[str],
    ):
        result = self.mental_readiness.run_pre_mortem(
            plan, failure_modes, wellness_state=profile.wellness_state
        )
        profile.update_skill("anticipatory_thinking", 0.04)
        profile.record_exercise("pre_mortem")
        return result

    def readiness_rehearsal(
        self, profile: CognitiveLearnerProfile, rehearsal_key: str
    ) -> str:
        profile.record_exercise("mental_rehearsal")
        return self.mental_readiness.rehearsal_prompt(
            rehearsal_key, wellness_state=profile.wellness_state
        )

    def readiness_tem(
        self,
        profile: CognitiveLearnerProfile,
        scenario_description: str,
        learner_threats: List[str],
    ):
        result = self.mental_readiness.analyse_threats(
            scenario_description, learner_threats
        )
        profile.update_skill("threat_analysis", 0.04)
        profile.record_exercise("threat_error_mgmt")
        return result

    # --- Adaptation summary -----------------------------------------------
    def adaptation_summary(self, profile: CognitiveLearnerProfile) -> Dict[str, object]:
        """Return a human-readable summary of the learner's cognitive training state."""
        plan = self.behavior.adaptation_plan(profile)
        rec = self.recommend_next_session(profile)
        return {
            "learner_id": profile.learner_id,
            "wellness": profile.wellness_state,
            "skill_mastery": {k: round(v, 2) for k, v in profile.skill_mastery.items()},
            "detected_patterns": [p.value for p in profile.detected_patterns],
            "adaptation_plan": plan,
            "next_session_recommendation": rec,
            "total_sessions": profile.total_cognitive_sessions,
            "completed_scenarios": profile.completed_scenarios,
            "completed_drills": profile.completed_drills,
        }
