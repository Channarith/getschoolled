"""Situational Awareness Trainer Agent.

Trains learners in structured situational analysis using three complementary
frameworks:
  - OODA loop (Observe → Orient → Decide → Act) — originally from military
    fighter-pilot doctrine; applies to any fast-moving situation.
  - DECIDE model (Detect → Estimate → Choose → Identify → Do → Evaluate)
    — favoured in aviation and emergency services.
  - SMEAC / SALUTE briefing skeletons — field-reporting discipline.

The agent presents scenarios, guides the learner through each framework
phase, evaluates their situational picture, and highlights blind spots.
It is sensitive to learner wellness and stress: under pressure it narrows
the focus to the most critical cue rather than overwhelming the learner.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Framework stages
# ---------------------------------------------------------------------------
class OODAPhase(str, Enum):
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ACT = "act"


class DECIDEPhase(str, Enum):
    DETECT = "detect"
    ESTIMATE = "estimate"
    CHOOSE = "choose"
    IDENTIFY = "identify"
    DO = "do"
    EVALUATE = "evaluate"


OODA_SEQUENCE: Tuple[OODAPhase, ...] = (
    OODAPhase.OBSERVE, OODAPhase.ORIENT, OODAPhase.DECIDE, OODAPhase.ACT,
)

DECIDE_SEQUENCE: Tuple[DECIDEPhase, ...] = (
    DECIDEPhase.DETECT, DECIDEPhase.ESTIMATE, DECIDEPhase.CHOOSE,
    DECIDEPhase.IDENTIFY, DECIDEPhase.DO, DECIDEPhase.EVALUATE,
)


# ---------------------------------------------------------------------------
# Scenario data shapes
# ---------------------------------------------------------------------------
@dataclass
class SituationalCue:
    """One observable datum in a scenario (sensory, instrument, report, etc.)."""
    cue_id: str
    description: str
    salience: float        # 0..1 — how prominent/obvious
    critical: bool = False # whether ignoring this cue causes mission failure
    domain: str = "general"  # e.g. "aviation", "medical", "fire", "finance"


@dataclass
class Scenario:
    """A situational awareness training scenario."""
    scenario_id: str
    title: str
    description: str
    domain: str
    cues: List[SituationalCue] = field(default_factory=list)
    correct_decision: str = ""
    decision_rationale: str = ""
    common_mistakes: List[str] = field(default_factory=list)
    time_pressure_seconds: Optional[int] = None   # None = no artificial timer


@dataclass
class OODAState:
    """Running OODA loop state for one scenario attempt."""
    phase: OODAPhase = OODAPhase.OBSERVE
    observed_cue_ids: List[str] = field(default_factory=list)
    orientation_notes: str = ""
    decision_text: str = ""
    action_text: str = ""
    missed_critical: List[str] = field(default_factory=list)
    phase_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class DECIDEState:
    """Running DECIDE model state for one scenario attempt."""
    phase: DECIDEPhase = DECIDEPhase.DETECT
    problem_statement: str = ""
    risk_estimate: str = ""
    chosen_option: str = ""
    identified_resources: List[str] = field(default_factory=list)
    action_taken: str = ""
    evaluation_notes: str = ""
    phase_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class SituationalAwarenessResult:
    """Final evaluation after completing one framework pass."""
    scenario_id: str
    framework: str
    overall_score: float         # 0..1
    critical_cues_caught: int
    critical_cues_total: int
    blind_spots: List[str]
    feedback: str
    coaching_notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in scenario library
# ---------------------------------------------------------------------------
def _make_id(seed: str) -> str:
    return hashlib.md5(seed.encode()).hexdigest()[:10]


SCENARIO_LIBRARY: List[Scenario] = [
    Scenario(
        scenario_id="sa_av_01",
        title="Engine Roughness at Cruise",
        description=(
            "You are flying a single-engine piston aircraft at 8,500 ft. The engine "
            "develops a slight roughness; EGT rises 50°F; fuel flow is nominal; "
            "outside air temperature is -5°C. You are 40 nm from the nearest airport."
        ),
        domain="aviation",
        cues=[
            SituationalCue("c1", "Engine roughness audible", 0.9, critical=True, domain="aviation"),
            SituationalCue("c2", "EGT +50°F above normal", 0.7, critical=True, domain="aviation"),
            SituationalCue("c3", "OAT -5°C (carburetor ice risk window)", 0.5, critical=True, domain="aviation"),
            SituationalCue("c4", "Fuel flow nominal", 0.6, critical=False, domain="aviation"),
            SituationalCue("c5", "40 nm to nearest airport", 0.8, critical=False, domain="aviation"),
        ],
        correct_decision="Apply carburetor heat immediately; monitor EGT/RPM recovery; declare precautionary if no improvement within 60 s.",
        decision_rationale="OAT in ice risk band + roughness + EGT rise = probable carb ice. Carb heat melts ice; EGT briefly rises then drops as ice clears.",
        common_mistakes=["Ignoring OAT cue", "Enriching mixture first", "Not declaring precautionary early enough"],
        time_pressure_seconds=120,
    ),
    Scenario(
        scenario_id="sa_med_01",
        title="Unresponsive Patient in Public",
        description=(
            "You find an adult collapsed in a shopping mall. They are unresponsive, "
            "not breathing normally. A bystander says the person 'just fell'. An AED "
            "is 30 m away. Two bystanders are present."
        ),
        domain="medical",
        cues=[
            SituationalCue("c1", "Unresponsive — no response to voice/touch", 1.0, critical=True, domain="medical"),
            SituationalCue("c2", "Absent / agonal breathing", 1.0, critical=True, domain="medical"),
            SituationalCue("c3", "AED 30 m away", 0.7, critical=True, domain="medical"),
            SituationalCue("c4", "Two bystanders available", 0.6, critical=False, domain="medical"),
            SituationalCue("c5", "Bystander account: 'just fell' (not trauma)", 0.4, critical=False, domain="medical"),
        ],
        correct_decision="Call emergency services → start CPR → send bystander for AED → use AED as soon as available.",
        decision_rationale="Cardiac arrest protocol: early CPR + early defibrillation maximise survival. Delegate AED retrieval to free bystander.",
        common_mistakes=["Waiting for paramedics before starting CPR", "Not delegating AED retrieval", "Recovery position instead of CPR"],
        time_pressure_seconds=60,
    ),
    Scenario(
        scenario_id="sa_fire_01",
        title="Smoke in Office Building",
        description=(
            "You are a floor warden on the 12th floor. You smell smoke; fire alarm "
            "activates. The elevator bank shows one lift is stuck between floors. "
            "There are 25 people on your floor including one wheelchair user. "
            "The nearest stairwell door feels warm to the touch."
        ),
        domain="fire_evacuation",
        cues=[
            SituationalCue("c1", "Smoke smell", 0.9, critical=True, domain="fire_evacuation"),
            SituationalCue("c2", "Fire alarm activated", 1.0, critical=False, domain="fire_evacuation"),
            SituationalCue("c3", "Stairwell door warm — fire likely beyond", 0.9, critical=True, domain="fire_evacuation"),
            SituationalCue("c4", "Elevator stuck — cannot use for evacuation", 0.8, critical=True, domain="fire_evacuation"),
            SituationalCue("c5", "Wheelchair user needs assistance", 0.7, critical=True, domain="fire_evacuation"),
            SituationalCue("c6", "25 people on floor", 0.6, critical=False, domain="fire_evacuation"),
        ],
        correct_decision="Do NOT open warm stairwell door. Use alternate stairwell. Assist wheelchair user to refuge area. Call fire brigade and report location.",
        decision_rationale="Warm door = fire/heat behind it — opening feeds oxygen and exposes occupants to flames. Refuge area is the protocol for mobility-impaired persons.",
        common_mistakes=["Opening warm stairwell door", "Using elevator", "Not accounting for wheelchair user"],
        time_pressure_seconds=90,
    ),
    Scenario(
        scenario_id="sa_cyber_01",
        title="Suspected Ransomware Alert",
        description=(
            "IT security alerts you at 9 AM: three workstations on the finance floor "
            "are showing unusual file-encryption activity. The payroll run is scheduled "
            "at 10 AM. Network logs show lateral movement to a file server. "
            "CEO is traveling and unreachable by phone."
        ),
        domain="cybersecurity",
        cues=[
            SituationalCue("c1", "File-encryption activity on 3 workstations", 1.0, critical=True, domain="cybersecurity"),
            SituationalCue("c2", "Lateral movement to file server in logs", 0.9, critical=True, domain="cybersecurity"),
            SituationalCue("c3", "Payroll run in 60 min", 0.8, critical=True, domain="cybersecurity"),
            SituationalCue("c4", "CEO unreachable", 0.5, critical=False, domain="cybersecurity"),
            SituationalCue("c5", "Finance floor affected (payroll data at risk)", 0.9, critical=True, domain="cybersecurity"),
        ],
        correct_decision="Isolate affected workstations and file server from network immediately; defer payroll run; escalate to CISO/deputy; invoke IR playbook.",
        decision_rationale="Containment before eradication. Every minute the ransomware spreads laterally. Payroll deferral is preferable to encrypted payroll data.",
        common_mistakes=["Waiting for CEO approval before isolating", "Running payroll on compromised network", "Not isolating file server"],
        time_pressure_seconds=180,
    ),
]


def get_scenario(scenario_id: str) -> Optional[Scenario]:
    for s in SCENARIO_LIBRARY:
        if s.scenario_id == scenario_id:
            return s
    return None


def list_scenarios(domain: Optional[str] = None) -> List[Scenario]:
    if domain:
        return [s for s in SCENARIO_LIBRARY if s.domain == domain]
    return list(SCENARIO_LIBRARY)


# ---------------------------------------------------------------------------
# OODA loop trainer
# ---------------------------------------------------------------------------
class OODATrainer:
    """Guides a learner through one OODA loop iteration for a scenario."""

    def prompt_for_phase(
        self, phase: OODAPhase, scenario: Scenario, *, wellness_state: str = "ok"
    ) -> str:
        stressed = wellness_state in ("stressed", "unwell")
        if phase is OODAPhase.OBSERVE:
            focus = "the single most important thing" if stressed else "what you observe"
            return (
                f"OBSERVE: {scenario.description}\n\n"
                f"What do you notice? List {focus} in this situation."
            )
        if phase is OODAPhase.ORIENT:
            return (
                "ORIENT: Based on what you observed, what does the situation mean? "
                "What prior knowledge or mental models apply here? "
                "Are there any competing hypotheses?"
            )
        if phase is OODAPhase.DECIDE:
            return (
                "DECIDE: What is your chosen course of action — and why? "
                "What alternatives did you consider and reject?"
            )
        # ACT
        return (
            "ACT: Describe how you would execute the decision. "
            "Who does what, in what order? How do you monitor the outcome?"
        )

    def evaluate_observe(
        self, state: OODAState, scenario: Scenario, learner_text: str
    ) -> Tuple[float, List[str]]:
        """Score observation phase: which critical cues did the learner catch?"""
        lower = learner_text.lower()
        caught, missed = [], []
        for cue in scenario.cues:
            keywords = cue.description.lower().split()
            significant = [w for w in keywords if len(w) > 4]
            if any(w in lower for w in significant):
                if cue.critical:
                    caught.append(cue.cue_id)
                state.observed_cue_ids.append(cue.cue_id)
            else:
                if cue.critical:
                    missed.append(cue.description)
        score = len(caught) / max(1, sum(1 for c in scenario.cues if c.critical))
        state.missed_critical = missed
        state.phase_scores["observe"] = round(score, 3)
        return score, missed

    def evaluate_decide(self, state: OODAState, scenario: Scenario, learner_text: str) -> float:
        """Score decision phase against correct_decision keywords."""
        lower = learner_text.lower()
        correct_words = [w for w in scenario.correct_decision.lower().split() if len(w) > 4]
        hits = sum(1 for w in correct_words if w in lower)
        score = min(1.0, hits / max(1, len(correct_words)) * 1.5)  # generous
        state.phase_scores["decide"] = round(score, 3)
        return score

    def final_result(self, state: OODAState, scenario: Scenario) -> SituationalAwarenessResult:
        scores = list(state.phase_scores.values())
        overall = sum(scores) / max(1, len(scores))
        critical_total = sum(1 for c in scenario.cues if c.critical)
        caught = critical_total - len(state.missed_critical)

        coaching = []
        if state.missed_critical:
            coaching.append(f"Missed critical cues: {'; '.join(state.missed_critical[:3])}.")
        if state.phase_scores.get("decide", 0) < 0.5:
            coaching.append(f"Correct decision: {scenario.correct_decision}")
            coaching.append(f"Rationale: {scenario.decision_rationale}")
        if scenario.common_mistakes:
            coaching.append(f"Common traps: {'; '.join(scenario.common_mistakes)}.")

        if overall >= 0.8:
            feedback = "Excellent situational awareness — you caught the critical cues and acted correctly."
        elif overall >= 0.55:
            feedback = "Good foundation. Review the missed cues and decision rationale above."
        else:
            feedback = "Several critical cues were missed. Repeat this scenario focusing on cue salience."

        return SituationalAwarenessResult(
            scenario_id=scenario.scenario_id,
            framework="ooda",
            overall_score=round(overall, 3),
            critical_cues_caught=max(0, caught),
            critical_cues_total=critical_total,
            blind_spots=state.missed_critical,
            feedback=feedback,
            coaching_notes=coaching,
        )


# ---------------------------------------------------------------------------
# DECIDE model trainer
# ---------------------------------------------------------------------------
class DECIDETrainer:
    """Guides a learner through the DECIDE model for a scenario."""

    PHASE_PROMPTS: Dict[DECIDEPhase, str] = {
        DECIDEPhase.DETECT: (
            "DETECT: What is the problem or hazard you have identified? "
            "State it as specifically as possible."
        ),
        DECIDEPhase.ESTIMATE: (
            "ESTIMATE: What is the likely impact if you take no action? "
            "How quickly is the situation changing?"
        ),
        DECIDEPhase.CHOOSE: (
            "CHOOSE: List at least two possible courses of action. "
            "Which do you prefer and why?"
        ),
        DECIDEPhase.IDENTIFY: (
            "IDENTIFY: What resources, personnel, or information do you "
            "need to execute your chosen action?"
        ),
        DECIDEPhase.DO: (
            "DO: Execute your plan. Describe the first three concrete steps "
            "you would take, in order."
        ),
        DECIDEPhase.EVALUATE: (
            "EVALUATE: How will you know the action worked? What are the "
            "indicators that would tell you to switch to a different plan?"
        ),
    }

    def prompt_for_phase(
        self, phase: DECIDEPhase, scenario: Scenario, *, wellness_state: str = "ok"
    ) -> str:
        prefix = f"Scenario: {scenario.title}\n\n" if phase is DECIDEPhase.DETECT else ""
        return prefix + self.PHASE_PROMPTS[phase]

    def score_phase(self, phase: DECIDEPhase, learner_text: str, scenario: Scenario) -> float:
        lower = (learner_text or "").lower()
        word_count = len(lower.split())
        base = min(1.0, word_count / 25.0)  # length heuristic

        if phase is DECIDEPhase.DETECT:
            # Check problem identification
            hits = sum(1 for w in scenario.description.lower().split() if len(w) > 5 and w in lower)
            return min(1.0, 0.4 * base + 0.6 * (hits / max(1, len([w for w in scenario.description.split() if len(w) > 5]))))
        if phase is DECIDEPhase.CHOOSE:
            # Penalise if only one option is discussed
            multi = any(w in lower for w in ("alternatively", "or", "option", "either", "instead"))
            return min(1.0, base * (1.3 if multi else 0.7))
        if phase is DECIDEPhase.EVALUATE:
            indicators = any(w in lower for w in ("if", "when", "indicator", "sign", "monitor", "check"))
            return min(1.0, base * (1.2 if indicators else 0.8))
        return min(1.0, base)

    def final_result(self, state: DECIDEState, scenario: Scenario) -> SituationalAwarenessResult:
        scores = list(state.phase_scores.values())
        overall = sum(scores) / max(1, len(scores))
        critical_total = sum(1 for c in scenario.cues if c.critical)

        problem_mentioned = sum(
            1 for cue in scenario.cues
            if cue.critical and any(
                w in (state.problem_statement + state.risk_estimate).lower()
                for w in cue.description.lower().split()
                if len(w) > 4
            )
        )
        coaching = []
        if overall < 0.6:
            coaching.append("Work through each DECIDE phase more thoroughly before acting.")
        if not state.evaluation_notes:
            coaching.append("Always define your success indicators before executing (Evaluate phase).")
        coaching.append(f"Best action for this scenario: {scenario.correct_decision}")

        feedback = (
            "Strong DECIDE model application."
            if overall >= 0.75 else
            "Solid start — the evaluation and estimation phases need more depth."
            if overall >= 0.5 else
            "Practice the full DECIDE cycle; rushing to action misses critical steps."
        )

        return SituationalAwarenessResult(
            scenario_id=scenario.scenario_id,
            framework="decide",
            overall_score=round(overall, 3),
            critical_cues_caught=problem_mentioned,
            critical_cues_total=critical_total,
            blind_spots=[
                c.description for c in scenario.cues
                if c.critical and c.description.lower() not in state.problem_statement.lower()
            ][:3],
            feedback=feedback,
            coaching_notes=coaching,
        )


# ---------------------------------------------------------------------------
# SituationalAwarenessAgent — facade
# ---------------------------------------------------------------------------
class SituationalAwarenessAgent:
    """Top-level agent that selects a framework and guides the full training loop.

    Stateless: all mutable state is owned by the caller (OODAState / DECIDEState).
    """

    def __init__(self) -> None:
        self._ooda = OODATrainer()
        self._decide = DECIDETrainer()

    def list_scenarios(self, domain: Optional[str] = None) -> List[Scenario]:
        return list_scenarios(domain)

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        return get_scenario(scenario_id)

    # OODA helpers
    def ooda_prompt(self, phase: OODAPhase, scenario: Scenario, *, wellness_state: str = "ok") -> str:
        return self._ooda.prompt_for_phase(phase, scenario, wellness_state=wellness_state)

    def ooda_evaluate_observe(
        self, state: OODAState, scenario: Scenario, learner_text: str
    ) -> Tuple[float, List[str]]:
        return self._ooda.evaluate_observe(state, scenario, learner_text)

    def ooda_evaluate_decide(
        self, state: OODAState, scenario: Scenario, learner_text: str
    ) -> float:
        return self._ooda.evaluate_decide(state, scenario, learner_text)

    def ooda_result(self, state: OODAState, scenario: Scenario) -> SituationalAwarenessResult:
        return self._ooda.final_result(state, scenario)

    # DECIDE helpers
    def decide_prompt(
        self, phase: DECIDEPhase, scenario: Scenario, *, wellness_state: str = "ok"
    ) -> str:
        return self._decide.prompt_for_phase(phase, scenario, wellness_state=wellness_state)

    def decide_score_phase(
        self, phase: DECIDEPhase, state: DECIDEState, scenario: Scenario, learner_text: str
    ) -> float:
        score = self._decide.score_phase(phase, learner_text, scenario)
        state.phase_scores[phase.value] = round(score, 3)
        return score

    def decide_result(self, state: DECIDEState, scenario: Scenario) -> SituationalAwarenessResult:
        return self._decide.final_result(state, scenario)
