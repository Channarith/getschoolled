"""Mental Readiness Agent.

Builds pre-situational mental preparedness through:
  1. Anticipatory thinking (prospective hindsight / pre-mortem analysis)
  2. Failure Mode Enumeration (FMEA-style thinking for scenarios)
  3. Mental rehearsal / mental simulation protocols
  4. Stress inoculation: graduated exposure grading cognitive load
  5. Threat-and-error management (TEM) — borrowed from aviation CRM
  6. Emotional regulation check-in and adaptive response

The agent is *sensitive*: it continuously monitors learner wellness and
adjusts cognitive load, language, and pacing to avoid overwhelming the
learner.  When wellness signals are poor, it shifts from high-challenge
exercises to restorative and grounding techniques.

Pure Python, dependency-free, fully offline-testable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class ReadinessExercise(str, Enum):
    PRE_MORTEM = "pre_mortem"
    MENTAL_REHEARSAL = "mental_rehearsal"
    FAILURE_MODE = "failure_mode"
    STRESS_INOCULATION = "stress_inoculation"
    THREAT_ERROR_MGMT = "threat_error_mgmt"
    REGULATION_CHECKIN = "regulation_checkin"
    GROUNDING_BREATH = "grounding_breath"   # restorative; low cognitive load


class CognitivePressure(str, Enum):
    """How much mental challenge to apply."""
    RESTORATIVE = "restorative"    # wellness poor — no new challenge
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ThreatCategory(str, Enum):
    """Threat-and-Error Management categories (aviation CRM origin)."""
    ENVIRONMENTAL = "environmental"
    ORGANIZATIONAL = "organizational"
    HUMAN_FACTORS = "human_factors"
    EQUIPMENT = "equipment"
    TASK = "task"


# ---------------------------------------------------------------------------
# Pre-mortem analysis
# ---------------------------------------------------------------------------
@dataclass
class PreMortemResult:
    """Output of a pre-mortem exercise on a planned action."""
    plan_description: str
    failure_modes: List[str]
    mitigations: List[str]
    residual_risks: List[str]
    confidence_adjustment: float   # negative = plan de-risked through reflection


def run_pre_mortem(
    plan_description: str,
    learner_failure_modes: List[str],
    *,
    wellness_state: str = "ok",
) -> PreMortemResult:
    """Guide a pre-mortem by scaffolding the learner's failure mode list.

    In a real session the learner types their answers; here we score/annotate
    a provided list and return structured coaching.
    """
    mitigations: List[str] = []
    residual: List[str] = []

    for fm in learner_failure_modes:
        lower = fm.lower()
        # Simple heuristics for mitigation suggestions
        if any(w in lower for w in ("communication", "miscomm", "unclear")):
            mitigations.append(f"Mitigate '{fm}': brief + read-back protocol")
        elif any(w in lower for w in ("time", "rush", "pressure")):
            mitigations.append(f"Mitigate '{fm}': build in 10% time buffer; set explicit go/no-go decision point")
        elif any(w in lower for w in ("equipment", "tool", "system", "fail")):
            mitigations.append(f"Mitigate '{fm}': pre-use equipment check; identify backup")
        elif any(w in lower for w in ("assumption", "assume", "thought")):
            mitigations.append(f"Mitigate '{fm}': explicitly verify key assumptions before acting")
        elif any(w in lower for w in ("distract", "interr", "focus")):
            mitigations.append(f"Mitigate '{fm}': sterile cockpit / focus protocol during critical phases")
        else:
            mitigations.append(f"Mitigate '{fm}': identify specific countermeasure before proceeding")

        # Flag residual risk for items without obvious mitigation
        if len(fm.split()) < 5:
            residual.append(f"Under-specified: '{fm}' — elaborate to enable mitigation")

    # If learner listed fewer than 3 failure modes, flag this
    if len(learner_failure_modes) < 3:
        residual.append("Consider deeper brainstorming — complex plans typically have 5+ failure modes")

    confidence_adj = -0.05 * len(learner_failure_modes)  # more failures found = better calibration
    if wellness_state in ("stressed", "unwell"):
        residual.append("Note: high-stress state may limit divergent thinking — revisit this exercise when feeling better")

    return PreMortemResult(
        plan_description=plan_description,
        failure_modes=learner_failure_modes,
        mitigations=mitigations,
        residual_risks=residual,
        confidence_adjustment=round(max(-0.40, confidence_adj), 3),
    )


# ---------------------------------------------------------------------------
# Failure Mode Enumeration
# ---------------------------------------------------------------------------
@dataclass
class FailureModeCard:
    component: str
    failure_mode: str
    effect: str
    severity: str     # low | medium | high | catastrophic
    detection_method: str
    mitigation: str


def build_failure_mode_cards(scenario_title: str, components: List[str]) -> List[FailureModeCard]:
    """Generate failure mode cards for each component of a scenario."""
    cards: List[FailureModeCard] = []
    severity_map = {
        0: "low",
        1: "medium",
        2: "high",
        3: "catastrophic",
    }
    for i, comp in enumerate(components):
        lower = comp.lower()
        if any(w in lower for w in ("engine", "power", "propulsion")):
            cards.append(FailureModeCard(
                component=comp,
                failure_mode="Complete power loss",
                effect="Loss of propulsion; forced landing required",
                severity="catastrophic",
                detection_method="RPM drop, silence, oil pressure warning",
                mitigation="Emergency checklist; best-glide speed; mayday",
            ))
        elif any(w in lower for w in ("comm", "radio", "communication")):
            cards.append(FailureModeCard(
                component=comp,
                failure_mode="Total communication failure",
                effect="Cannot receive instructions or declare emergency",
                severity="high",
                detection_method="No response from ATC; squelch silent",
                mitigation="Squawk 7600; fly published lost-comm procedure",
            ))
        elif any(w in lower for w in ("medic", "drug", "medication", "epinephrine")):
            cards.append(FailureModeCard(
                component=comp,
                failure_mode="Auto-injector malfunction / expired",
                effect="No epinephrine delivery in anaphylaxis",
                severity="catastrophic",
                detection_method="Check expiry date; check window for cloudiness",
                mitigation="Carry two auto-injectors; check monthly",
            ))
        elif any(w in lower for w in ("network", "firewall", "vpn")):
            cards.append(FailureModeCard(
                component=comp,
                failure_mode="Network segmentation failure",
                effect="Ransomware/attacker moves laterally unchecked",
                severity="catastrophic",
                detection_method="IDS/IPS alert; unusual east-west traffic",
                mitigation="Zero-trust segmentation; rapid isolation runbook",
            ))
        else:
            sev = severity_map[i % 4]
            cards.append(FailureModeCard(
                component=comp,
                failure_mode=f"Degraded performance of {comp}",
                effect=f"Reduced effectiveness in {scenario_title}",
                severity=sev,
                detection_method="Monitoring / pre-use checklist",
                mitigation=f"Identify backup for {comp} before operation begins",
            ))
    return cards


# ---------------------------------------------------------------------------
# Mental rehearsal
# ---------------------------------------------------------------------------
@dataclass
class RehearsalScript:
    """A structured mental rehearsal script for a procedure."""
    procedure_name: str
    steps: List[str]
    sensory_anchors: List[str]    # what the learner should visualise/feel
    decision_gates: List[str]     # explicit decision points to rehearse
    success_image: str            # closing positive outcome visualisation


REHEARSAL_TEMPLATES: Dict[str, RehearsalScript] = {
    "engine_failure_landing": RehearsalScript(
        procedure_name="Engine Failure — Forced Landing",
        steps=[
            "Feel the sudden silence as the engine stops; notice the RPM needle dropping.",
            "Pitch forward immediately — feel the nose drop, airspeed stabilise at 65 kts.",
            "Scan outside for the landing field; identify the wind direction from trees/smoke.",
            "Run the restart checklist: carb heat, fuel, mags — methodical, not rushed.",
            "Select the field; commit; fly left-base, final.",
            "Full flaps on final; 65 kts over the fence; flare; touchdown.",
        ],
        sensory_anchors=[
            "The silence when the engine stops",
            "Wind noise as airspeed stabilises",
            "The visual picture of the field growing in the windscreen",
            "The thump of the flare and touchdown",
        ],
        decision_gates=[
            "Altitude call: below 500 ft — no turn-back, straight ahead only",
            "Restart attempt: max 30 seconds, then commit to field",
            "Field commitment point: below 1,000 ft AGL — do not change field",
        ],
        success_image="Aircraft stopped safely in the field. Passengers uninjured. Mayday acknowledged. Calm, methodical performance throughout.",
    ),
    "anaphylaxis_response": RehearsalScript(
        procedure_name="Anaphylaxis Emergency Response",
        steps=[
            "Notice the patient: swelling, hives, voice change — immediate recognition.",
            "Reach for the EpiPen — locate it without looking (muscle memory from drills).",
            "Remove cap; press firmly to outer thigh; count 10 seconds.",
            "Call emergency services — state: 'anaphylaxis, epinephrine given, patient conscious'.",
            "Lay patient supine; keep calm; reassure them.",
            "Monitor every 2 minutes; prepare second EpiPen for biphasic reaction.",
        ],
        sensory_anchors=[
            "The sound of stridor (throat tightness)",
            "The click of the EpiPen firing",
            "Your own steady voice reassuring the patient",
        ],
        decision_gates=[
            "Symptoms present: DO NOT give antihistamine first — EpiPen first always",
            "Patient feels better: do NOT discharge — biphasic risk requires 4-hour observation",
        ],
        success_image="Patient stable, EMS en route, all steps completed in sequence, no hesitation.",
    ),
    "incident_response": RehearsalScript(
        procedure_name="Ransomware Incident Response",
        steps=[
            "Alert received: read it fully before acting — understand scope first.",
            "Containment decision: isolate affected segment — this is reflexive, not debated.",
            "Preserve evidence: memory snapshots before shutdown.",
            "Assess backup integrity: independent of affected network.",
            "Escalate: board, legal, security team — in that order.",
            "Communicate: regulator first (legal window), then customers, then public.",
        ],
        sensory_anchors=[
            "The flat line of containment — network traffic graphs showing isolation",
            "The backup status dashboard showing a clean snapshot",
        ],
        decision_gates=[
            "Never pay ransom as a first response — verify backup options first",
            "Notify regulator within the legally required window (typically 72 hours for GDPR)",
        ],
        success_image="Incident contained, evidence preserved, recovery underway, stakeholders informed, regulatory obligations met.",
    ),
}


def get_rehearsal_script(key: str) -> Optional[RehearsalScript]:
    return REHEARSAL_TEMPLATES.get(key)


def format_rehearsal(script: RehearsalScript, *, wellness_state: str = "ok") -> str:
    """Format a rehearsal script for delivery to the learner."""
    lines = [
        f"MENTAL REHEARSAL: {script.procedure_name}",
        "",
        "Close your eyes if safe to do so. Breathe slowly.",
        "",
        "Walk through the following steps mentally — visualise each one:",
        "",
    ]
    for i, step in enumerate(script.steps, 1):
        lines.append(f"  {i}. {step}")

    if wellness_state not in ("stressed", "unwell"):
        lines.extend([
            "",
            "Sensory anchors to include:",
            *[f"  - {s}" for s in script.sensory_anchors],
            "",
            "Decision gates (rehearse each as a conscious choice):",
            *[f"  ▶ {g}" for g in script.decision_gates],
        ])

    lines.extend([
        "",
        "Success image:",
        f"  {script.success_image}",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stress inoculation
# ---------------------------------------------------------------------------
@dataclass
class StressInoculationSession:
    """Tracks a graduated stress inoculation programme for a learner."""
    learner_id: str
    domain: str
    current_level: int = 1         # 1 (low stress) → 5 (high stress)
    sessions_at_level: int = 0
    success_rate_at_level: float = 0.5
    total_sessions: int = 0
    notes: List[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def advance_level(self, success_rate: float) -> Tuple[bool, str]:
        """Check if the learner is ready to advance to the next stress level."""
        self.success_rate_at_level = success_rate
        self.sessions_at_level += 1
        self.total_sessions += 1

        if success_rate >= 0.80 and self.sessions_at_level >= 3 and self.current_level < 5:
            self.current_level += 1
            self.sessions_at_level = 0
            return True, f"Advancing to stress level {self.current_level}"
        if success_rate < 0.50 and self.current_level > 1:
            self.current_level -= 1
            self.sessions_at_level = 0
            return False, f"Returning to stress level {self.current_level} for consolidation"
        return False, f"Continuing at stress level {self.current_level}"


STRESS_LEVEL_DESCRIPTIONS = {
    1: "Familiar setting, unlimited time, no stakes — build procedural memory",
    2: "Familiar setting, soft time limit, low stakes — mild time pressure",
    3: "Unfamiliar variant, moderate time limit, distractor events present",
    4: "High complexity, strict time limit, incomplete information",
    5: "Maximum complexity, split-second decisions, emotional stressors added",
}


# ---------------------------------------------------------------------------
# Threat and Error Management (TEM)
# ---------------------------------------------------------------------------
@dataclass
class ThreatEntry:
    category: ThreatCategory
    description: str
    countermeasure: str
    detected_early: bool = True


@dataclass
class TEMAnalysis:
    scenario_description: str
    threats_identified: List[ThreatEntry] = field(default_factory=list)
    undetected_threats: List[str] = field(default_factory=list)
    error_traps: List[str] = field(default_factory=list)
    feedback: str = ""


def analyse_threats(scenario_description: str, learner_threats: List[str]) -> TEMAnalysis:
    """Map learner-identified threats to TEM categories and flag gaps."""
    lower_desc = scenario_description.lower()
    identified: List[ThreatEntry] = []
    undetected: List[str] = []

    # Auto-categorise based on keywords
    categories_checked = set()
    for threat in learner_threats:
        lower = threat.lower()
        if any(w in lower for w in ("weather", "wind", "ice", "visibility", "terrain")):
            cat = ThreatCategory.ENVIRONMENTAL
        elif any(w in lower for w in ("procedure", "policy", "resource", "staffing", "management")):
            cat = ThreatCategory.ORGANIZATIONAL
        elif any(w in lower for w in ("fatigue", "stress", "distract", "complacen", "rush")):
            cat = ThreatCategory.HUMAN_FACTORS
        elif any(w in lower for w in ("equipment", "system", "failure", "malfunction", "tool")):
            cat = ThreatCategory.EQUIPMENT
        else:
            cat = ThreatCategory.TASK
        categories_checked.add(cat)
        identified.append(ThreatEntry(
            category=cat,
            description=threat,
            countermeasure=f"Identify mitigation for: {threat}",
            detected_early=True,
        ))

    # Flag unchecked categories likely present in scenario
    all_cats = set(ThreatCategory)
    for missing in all_cats - categories_checked:
        if missing is ThreatCategory.ENVIRONMENTAL and any(
            w in lower_desc for w in ("weather", "terrain", "environment")
        ):
            undetected.append(f"Environmental threat not identified — check scenario conditions")
        elif missing is ThreatCategory.HUMAN_FACTORS:
            undetected.append("Human factors threats (fatigue, complacency, workload) not listed — always consider these")

    error_traps = []
    if "rushed" in lower_desc or "time" in lower_desc:
        error_traps.append("Time pressure → likely to skip verification steps")
    if "unfamiliar" in lower_desc or "new" in lower_desc:
        error_traps.append("Novelty → may over-rely on pattern-matching from different context")

    feedback = (
        "Good threat identification covering multiple TEM categories."
        if len(categories_checked) >= 3 else
        "Expand threat identification to cover environmental, organisational, and human-factor dimensions."
    )

    return TEMAnalysis(
        scenario_description=scenario_description,
        threats_identified=identified,
        undetected_threats=undetected,
        error_traps=error_traps,
        feedback=feedback,
    )


# ---------------------------------------------------------------------------
# Emotional regulation check-in
# ---------------------------------------------------------------------------
@dataclass
class RegulationCheckIn:
    """Brief pre-exercise emotional regulation self-assessment."""
    stress_level: int           # 1–10
    focus_level: int            # 1–10
    readiness_note: str
    recommended_exercise: ReadinessExercise
    breath_cue: str


def regulation_check_in(
    stress_level: int,      # 1–10
    focus_level: int,       # 1–10
    wellness_state: str = "ok",
) -> RegulationCheckIn:
    """Map learner self-report to a readiness recommendation."""
    stress_level = max(1, min(10, stress_level))
    focus_level = max(1, min(10, focus_level))

    if wellness_state in ("unwell", "stressed") or stress_level >= 8 or focus_level <= 3:
        exercise = ReadinessExercise.GROUNDING_BREATH
        note = "High stress or low focus detected. Starting with a grounding exercise before any cognitive challenge."
        breath = "4-7-8 breathing: inhale 4 s, hold 7 s, exhale 8 s. Repeat 3 times before continuing."
    elif stress_level >= 6 or focus_level <= 5:
        exercise = ReadinessExercise.MENTAL_REHEARSAL
        note = "Moderate stress. A guided mental rehearsal will build readiness without adding cognitive load."
        breath = "Box breathing: inhale 4 s, hold 4 s, exhale 4 s, hold 4 s. Repeat twice."
    elif focus_level >= 7 and stress_level <= 4:
        exercise = ReadinessExercise.PRE_MORTEM
        note = "Good readiness state. Proceeding to pre-mortem analysis to build anticipatory awareness."
        breath = "One slow breath in through the nose, out through the mouth."
    else:
        exercise = ReadinessExercise.FAILURE_MODE
        note = "Moderate readiness. Failure mode enumeration will engage focused analytical thinking."
        breath = "Two slow breaths. Bring attention to the task."

    return RegulationCheckIn(
        stress_level=stress_level,
        focus_level=focus_level,
        readiness_note=note,
        recommended_exercise=exercise,
        breath_cue=breath,
    )


# ---------------------------------------------------------------------------
# MentalReadinessAgent — main interface
# ---------------------------------------------------------------------------
class MentalReadinessAgent:
    """Stateless mental readiness training agent.

    Sensitive: tracks wellness and stress signals; adjusts cognitive load
    dynamically.  All persistent state owned by the caller.
    """

    # --- Check-in ----------------------------------------------------------
    def check_in(
        self,
        stress_level: int,
        focus_level: int,
        wellness_state: str = "ok",
    ) -> RegulationCheckIn:
        return regulation_check_in(stress_level, focus_level, wellness_state)

    # --- Pre-mortem --------------------------------------------------------
    def run_pre_mortem(
        self,
        plan: str,
        failure_modes: List[str],
        *,
        wellness_state: str = "ok",
    ) -> PreMortemResult:
        return run_pre_mortem(plan, failure_modes, wellness_state=wellness_state)

    # --- Failure mode analysis ---------------------------------------------
    def failure_mode_cards(
        self, scenario_title: str, components: List[str]
    ) -> List[FailureModeCard]:
        return build_failure_mode_cards(scenario_title, components)

    # --- Mental rehearsal --------------------------------------------------
    def rehearsal_script(self, key: str) -> Optional[RehearsalScript]:
        return get_rehearsal_script(key)

    def rehearsal_prompt(
        self, key: str, *, wellness_state: str = "ok"
    ) -> str:
        script = get_rehearsal_script(key)
        if not script:
            return f"No rehearsal script found for key: {key}"
        return format_rehearsal(script, wellness_state=wellness_state)

    def list_rehearsal_keys(self) -> List[str]:
        return list(REHEARSAL_TEMPLATES.keys())

    # --- Stress inoculation ------------------------------------------------
    def stress_level_description(self, level: int) -> str:
        return STRESS_LEVEL_DESCRIPTIONS.get(level, "Unknown level")

    def advance_stress_level(
        self, session: StressInoculationSession, success_rate: float
    ) -> Tuple[bool, str]:
        return session.advance_level(success_rate)

    # --- TEM ---------------------------------------------------------------
    def analyse_threats(
        self, scenario_description: str, learner_threats: List[str]
    ) -> TEMAnalysis:
        return analyse_threats(scenario_description, learner_threats)

    # --- Cognitive pressure selection --------------------------------------
    def cognitive_pressure(self, wellness_state: str, mastery: float) -> CognitivePressure:
        """Select appropriate cognitive pressure level for training."""
        if wellness_state in ("unwell", "stressed"):
            return CognitivePressure.RESTORATIVE
        if wellness_state == "low_energy" or mastery < 0.3:
            return CognitivePressure.LOW
        if mastery < 0.6:
            return CognitivePressure.MODERATE
        return CognitivePressure.HIGH

    # --- Wellness-aware exercise selection ---------------------------------
    def recommend_exercise(
        self,
        wellness_state: str,
        mastery: float,
        recent_exercises: Optional[List[ReadinessExercise]] = None,
    ) -> ReadinessExercise:
        """Recommend next exercise based on readiness and recent history."""
        recent = set(recent_exercises or [])
        pressure = self.cognitive_pressure(wellness_state, mastery)

        if pressure is CognitivePressure.RESTORATIVE:
            return ReadinessExercise.GROUNDING_BREATH

        if pressure is CognitivePressure.LOW:
            if ReadinessExercise.MENTAL_REHEARSAL not in recent:
                return ReadinessExercise.MENTAL_REHEARSAL
            return ReadinessExercise.REGULATION_CHECKIN

        if pressure is CognitivePressure.MODERATE:
            for ex in (
                ReadinessExercise.PRE_MORTEM,
                ReadinessExercise.FAILURE_MODE,
                ReadinessExercise.THREAT_ERROR_MGMT,
            ):
                if ex not in recent:
                    return ex
            return ReadinessExercise.MENTAL_REHEARSAL

        # HIGH pressure
        for ex in (
            ReadinessExercise.STRESS_INOCULATION,
            ReadinessExercise.THREAT_ERROR_MGMT,
            ReadinessExercise.PRE_MORTEM,
        ):
            if ex not in recent:
                return ex
        return ReadinessExercise.STRESS_INOCULATION
