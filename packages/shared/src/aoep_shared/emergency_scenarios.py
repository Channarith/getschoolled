"""Emergency Scenario Simulation Agent.

Simulates high-stakes emergencies end-to-end and conducts a structured
After Action Review (AAR) when the scenario concludes.  Designed to train:
- Emergency aircraft landings (engine failure, hydraulic loss, fire)
- Medical emergencies (cardiac arrest, trauma, anaphylaxis)
- Crisis management (evacuation, cyber attack, structural failure)

Architecture
------------
A scenario unfolds as a sequence of *phases*.  Each phase presents a
situation update and a decision point.  The learner's choice gates which
branch of the simulation tree executes next.  The agent tracks:
  - Decisions made at each phase
  - Time-critical actions (correct/missed)
  - Cascade errors (one wrong decision that worsens later phases)
  - Overall survivability / outcome score

After the final phase the agent generates a full AAR narrative plus a
comparative "what the expert would have done" walkthrough.

Pure Python, dependency-free, offline-testable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ScenarioDomain(str, Enum):
    AVIATION = "aviation"
    MEDICAL = "medical"
    FIRE = "fire"
    CRISIS = "crisis"
    INDUSTRIAL = "industrial"


class PhaseOutcome(str, Enum):
    OPTIMAL = "optimal"
    ACCEPTABLE = "acceptable"
    SUBOPTIMAL = "suboptimal"
    CRITICAL_ERROR = "critical_error"


class SimulationStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    TERMINATED_EARLY = "terminated_early"   # critical error led to immediate failure


# ---------------------------------------------------------------------------
# Scenario data model
# ---------------------------------------------------------------------------
@dataclass
class PhaseAction:
    """One available action at a decision point."""
    action_id: str
    label: str
    description: str
    outcome: PhaseOutcome
    consequence: str          # narrative of what happens after this choice
    mastery_delta: float = 0.0  # change to scenario mastery score (-1..+1)
    unlocks_phase: Optional[str] = None   # next phase ID if this action is taken
    terminates: bool = False  # if True, scenario ends here (crash, death, etc.)


@dataclass
class ScenarioPhase:
    """One phase in a simulation scenario."""
    phase_id: str
    title: str
    situation_update: str     # what happens / what the learner sees now
    action_prompt: str        # what the learner is asked to do
    available_actions: List[PhaseAction] = field(default_factory=list)
    time_window_seconds: Optional[int] = None  # None = untimed
    expert_action_id: str = ""  # the PhaseAction a trained expert would take
    teaching_point: str = ""   # key lesson from this phase


@dataclass
class EmergencyScenario:
    """Full emergency simulation scenario."""
    scenario_id: str
    title: str
    domain: ScenarioDomain
    description: str           # opening briefing
    initial_phase_id: str
    phases: Dict[str, ScenarioPhase] = field(default_factory=dict)
    learning_objectives: List[str] = field(default_factory=list)
    prerequisite_skills: List[str] = field(default_factory=list)
    difficulty: str = "intermediate"   # beginner | intermediate | advanced

    def get_phase(self, phase_id: str) -> Optional[ScenarioPhase]:
        return self.phases.get(phase_id)


# ---------------------------------------------------------------------------
# Simulation run state
# ---------------------------------------------------------------------------
@dataclass
class PhaseDecision:
    phase_id: str
    action_id: str
    outcome: PhaseOutcome
    consequence: str
    time_taken_s: Optional[float] = None


@dataclass
class SimulationRun:
    """Mutable state for one learner's run through a scenario."""
    scenario_id: str
    learner_id: str
    started_at: float = field(default_factory=time.time)
    current_phase_id: str = ""
    decisions: List[PhaseDecision] = field(default_factory=list)
    mastery_score: float = 0.5     # 0..1
    status: SimulationStatus = SimulationStatus.IN_PROGRESS
    cascade_errors: List[str] = field(default_factory=list)

    def record_decision(self, phase_id: str, action: PhaseAction,
                        time_taken_s: Optional[float] = None) -> None:
        self.decisions.append(PhaseDecision(
            phase_id=phase_id,
            action_id=action.action_id,
            outcome=action.outcome,
            consequence=action.consequence,
            time_taken_s=time_taken_s,
        ))
        self.mastery_score = max(0.0, min(1.0, self.mastery_score + action.mastery_delta))
        if action.outcome is PhaseOutcome.CRITICAL_ERROR:
            self.cascade_errors.append(f"{phase_id}:{action.action_id}")

        if action.terminates:
            self.status = SimulationStatus.TERMINATED_EARLY
        elif action.unlocks_phase:
            self.current_phase_id = action.unlocks_phase
        else:
            self.status = SimulationStatus.COMPLETED


# ---------------------------------------------------------------------------
# AAR (After Action Review)
# ---------------------------------------------------------------------------
@dataclass
class AARReport:
    scenario_id: str
    learner_id: str
    outcome_score: float           # 0..1
    decisions_summary: List[str]   # narrative for each decision
    expert_comparison: List[str]   # what expert did vs learner
    cascade_errors: List[str]
    learning_reinforcements: List[str]  # key lessons
    overall_verdict: str
    recommended_next_scenario: Optional[str] = None


def _outcome_emoji(o: PhaseOutcome) -> str:
    return {
        PhaseOutcome.OPTIMAL: "✓",
        PhaseOutcome.ACCEPTABLE: "~",
        PhaseOutcome.SUBOPTIMAL: "!",
        PhaseOutcome.CRITICAL_ERROR: "✗",
    }.get(o, "?")


def generate_aar(
    run: SimulationRun,
    scenario: EmergencyScenario,
) -> AARReport:
    decisions_summary = []
    expert_comparison = []
    reinforcements = []

    for dec in run.decisions:
        phase = scenario.get_phase(dec.phase_id)
        if not phase:
            continue
        marker = _outcome_emoji(dec.outcome)
        decisions_summary.append(
            f"[{marker}] {phase.title}: You chose '{dec.action_id}'. {dec.consequence}"
        )
        if phase.expert_action_id and phase.expert_action_id != dec.action_id:
            expert_action = next(
                (a for a in phase.available_actions if a.action_id == phase.expert_action_id),
                None,
            )
            if expert_action:
                expert_comparison.append(
                    f"{phase.title}: Expert action — '{expert_action.label}'. "
                    f"{expert_action.consequence}"
                )
        if phase.teaching_point:
            reinforcements.append(phase.teaching_point)

    for obj in scenario.learning_objectives:
        reinforcements.append(f"Objective: {obj}")

    if run.mastery_score >= 0.8:
        verdict = (
            "Outstanding performance. You demonstrated sound emergency discipline "
            "and prioritised correctly throughout."
        )
        recommended = None
    elif run.mastery_score >= 0.55:
        verdict = (
            "Competent performance with some areas to refine. Review the critical "
            "errors and repeat under higher time pressure."
        )
        recommended = scenario.scenario_id
    else:
        verdict = (
            "Several critical errors significantly worsened the outcome. "
            "Practice the foundational procedures for this scenario type before retrying."
        )
        recommended = scenario.scenario_id

    return AARReport(
        scenario_id=scenario.scenario_id,
        learner_id=run.learner_id,
        outcome_score=round(run.mastery_score, 3),
        decisions_summary=decisions_summary,
        expert_comparison=expert_comparison,
        cascade_errors=run.cascade_errors,
        learning_reinforcements=list(dict.fromkeys(reinforcements)),  # dedupe
        overall_verdict=verdict,
        recommended_next_scenario=recommended,
    )


# ---------------------------------------------------------------------------
# Built-in scenario: Emergency Landing
# ---------------------------------------------------------------------------
def _build_engine_failure_scenario() -> EmergencyScenario:
    scenario = EmergencyScenario(
        scenario_id="em_av_engine_failure",
        title="Engine Failure — Emergency Landing",
        domain=ScenarioDomain.AVIATION,
        description=(
            "You are the pilot-in-command of a single-engine Cessna 172 at 4,500 ft AGL, "
            "7 nm east of Riverside Airport (KRAL). Suddenly the engine stops producing "
            "power. The propeller is windmilling. You have approximately 7 minutes of "
            "glide time. The ATIS last reported winds 270° at 12 kt."
        ),
        initial_phase_id="ph1_immediate_actions",
        learning_objectives=[
            "Apply the 3-step immediate action drill (aviate-navigate-communicate)",
            "Select the best forced-landing field using altitude/wind/surface criteria",
            "Fly a stabilised approach to an off-airport landing",
            "Mayday call content and timing",
        ],
        prerequisite_skills=["basic_flight_controls", "emergency_procedures"],
        difficulty="intermediate",
    )

    scenario.phases["ph1_immediate_actions"] = ScenarioPhase(
        phase_id="ph1_immediate_actions",
        title="Immediate Actions",
        situation_update=(
            "Engine has stopped. Propeller windmilling. Airspeed indicator shows 90 kts "
            "and decreasing. Altitude 4,500 ft."
        ),
        action_prompt="What is your first action?",
        expert_action_id="a1_pitch_best_glide",
        teaching_point="Aviate first: establish best-glide speed immediately. Every second at the wrong airspeed costs altitude.",
        available_actions=[
            PhaseAction(
                action_id="a1_pitch_best_glide",
                label="Pitch for best-glide speed (65 kts for C172)",
                description="Lower nose to 65 kts best-glide; begin troubleshooting checklist.",
                outcome=PhaseOutcome.OPTIMAL,
                consequence="Glide stabilised. You now have maximum glide range. Engine restart checklist begins.",
                mastery_delta=0.15,
                unlocks_phase="ph2_restart_attempt",
            ),
            PhaseAction(
                action_id="a1_mayday_first",
                label="Declare Mayday on 121.5 first",
                description="Transmit Mayday before establishing glide speed.",
                outcome=PhaseOutcome.SUBOPTIMAL,
                consequence="Mayday sent, but you lost 200 ft unnecessarily at non-optimal airspeed. ATC advised; landing field selection begins.",
                mastery_delta=-0.05,
                unlocks_phase="ph2_restart_attempt",
            ),
            PhaseAction(
                action_id="a1_attempt_restart_first",
                label="Attempt engine restart immediately",
                description="Manipulate throttle/mixture without establishing glide speed.",
                outcome=PhaseOutcome.SUBOPTIMAL,
                consequence="Airspeed drops to 70 kts (below best glide). Glide range reduced. Restart attempt should follow best-glide pitch.",
                mastery_delta=-0.08,
                unlocks_phase="ph2_restart_attempt",
            ),
            PhaseAction(
                action_id="a1_pull_back",
                label="Pull back to maintain altitude",
                description="Try to maintain altitude by pitching up.",
                outcome=PhaseOutcome.CRITICAL_ERROR,
                consequence="Airspeed decreases rapidly toward stall speed. Aircraft enters aerodynamic stall at 4,200 ft — insufficient altitude for recovery.",
                mastery_delta=-0.30,
                unlocks_phase="ph2_restart_attempt",
                terminates=False,
            ),
        ],
    )

    scenario.phases["ph2_restart_attempt"] = ScenarioPhase(
        phase_id="ph2_restart_attempt",
        title="Engine Restart Attempt",
        situation_update=(
            "Glide established. Altitude 4,100 ft. You have time for one restart attempt. "
            "Fuel selector: LEFT. Mixture: RICH. Carb heat: OFF. Magnetos: BOTH."
        ),
        action_prompt="You notice carb heat is OFF and fuel is on LEFT. What do you do?",
        expert_action_id="a2_carb_heat_switch_fuel",
        teaching_point="Carburetor ice causes ~30% of engine failures in training aircraft. Carb heat ON + fuel switching is the standard first response.",
        available_actions=[
            PhaseAction(
                action_id="a2_carb_heat_switch_fuel",
                label="Apply carb heat ON; switch fuel to BOTH; check magnetos",
                description="Apply carb heat, switch fuel to BOTH, check mags.",
                outcome=PhaseOutcome.OPTIMAL,
                consequence="RPM briefly drops then rises by 200 RPM as carb ice clears. Engine does not fully restart but partial power is recovered.",
                mastery_delta=0.15,
                unlocks_phase="ph3_field_selection",
            ),
            PhaseAction(
                action_id="a2_mixture_only",
                label="Richen mixture only",
                description="Push mixture to full rich.",
                outcome=PhaseOutcome.SUBOPTIMAL,
                consequence="Mixture was already rich. No improvement. Restart not achieved. Field selection begins.",
                mastery_delta=-0.03,
                unlocks_phase="ph3_field_selection",
            ),
            PhaseAction(
                action_id="a2_keep_trying",
                label="Pump throttle repeatedly to restart",
                description="Rapidly cycle the throttle several times.",
                outcome=PhaseOutcome.CRITICAL_ERROR,
                consequence="Flooding the engine makes restart impossible and wastes 400 ft of altitude.",
                mastery_delta=-0.20,
                unlocks_phase="ph3_field_selection",
            ),
        ],
    )

    scenario.phases["ph3_field_selection"] = ScenarioPhase(
        phase_id="ph3_field_selection",
        title="Forced Landing Field Selection",
        situation_update=(
            "Engine not restarting. Altitude 3,600 ft. You can see ahead: "
            "(1) Large grass field, 1.5 nm, into wind. "
            "(2) Road — cars present. "
            "(3) Airport KRAL — 7 nm away (glide range ~5 nm). "
            "Wind 270/12."
        ),
        action_prompt="Which landing site do you select?",
        expert_action_id="a3_grass_field",
        teaching_point="Select the closest suitable site — never stretch a glide hoping to reach a distant preferred surface. An off-airport landing on a clear field is survivable; running out of altitude short of the airport is not.",
        available_actions=[
            PhaseAction(
                action_id="a3_grass_field",
                label="Grass field 1.5 nm — into wind, clear, within glide range",
                description="Turn toward the large grass field.",
                outcome=PhaseOutcome.OPTIMAL,
                consequence="Field is within glide range. You establish a left-base pattern. Approach is stable. Proceed to landing phase.",
                mastery_delta=0.15,
                unlocks_phase="ph4_approach_landing",
            ),
            PhaseAction(
                action_id="a3_road",
                label="Road ahead",
                description="Target the road.",
                outcome=PhaseOutcome.SUBOPTIMAL,
                consequence="Road has vehicles. Risk of collision. Field was a better option. Approach proceeds but hazard risk is elevated.",
                mastery_delta=-0.10,
                unlocks_phase="ph4_approach_landing",
            ),
            PhaseAction(
                action_id="a3_airport",
                label="Stretch glide to KRAL airport",
                description="Aim for the airport 7 nm away.",
                outcome=PhaseOutcome.CRITICAL_ERROR,
                consequence="Glide range at 3,600 ft is ~5 nm. Aircraft runs out of altitude 2 nm short of KRAL. Forced landing in unfamiliar terrain.",
                mastery_delta=-0.30,
                unlocks_phase="ph4_approach_landing",
            ),
        ],
    )

    scenario.phases["ph4_approach_landing"] = ScenarioPhase(
        phase_id="ph4_approach_landing",
        title="Final Approach and Landing",
        situation_update=(
            "Turning final. Altitude 600 ft AGL. Speed 70 kts. "
            "Field is clear. Wind directly on nose. Gear: fixed. "
            "You still have time for one of: full flaps, partial flaps, or no flaps."
        ),
        action_prompt="Flap configuration for forced landing on short grass field?",
        expert_action_id="a4_full_flaps_committed",
        teaching_point="Use full flaps on the final approach to maximise drag and minimise touch-down speed, reducing kinetic energy on impact. Once committed to the field, do not change configuration.",
        available_actions=[
            PhaseAction(
                action_id="a4_full_flaps_committed",
                label="Full flaps — fly stabilised to touchdown",
                description="Deploy full flaps; maintain 65 kts; commit to field.",
                outcome=PhaseOutcome.OPTIMAL,
                consequence="Touchdown at ~55 kts over fence. Smooth deceleration on grass. Aircraft stops safely 300 ft into field. Occupants uninjured.",
                mastery_delta=0.20,
            ),
            PhaseAction(
                action_id="a4_no_flaps",
                label="No flaps — land flat and fast",
                description="Keep flaps up to preserve lift.",
                outcome=PhaseOutcome.SUBOPTIMAL,
                consequence="Touchdown at 70 kts — significant field overrun. Aircraft rolls into fence at 15 kts. Repairable damage; occupants shaken but uninjured.",
                mastery_delta=-0.10,
            ),
            PhaseAction(
                action_id="a4_abort_go_around",
                label="Attempt go-around on final",
                description="Add power and try to abort landing.",
                outcome=PhaseOutcome.CRITICAL_ERROR,
                consequence="No engine power for go-around. Aircraft loses airspeed at 200 ft AGL. Forced to land off-runway in unfavourable terrain at high sink rate. Significant damage.",
                mastery_delta=-0.35,
                terminates=False,
            ),
        ],
    )

    return scenario


def _build_anaphylaxis_scenario() -> EmergencyScenario:
    scenario = EmergencyScenario(
        scenario_id="em_med_anaphylaxis",
        title="Anaphylaxis — Emergency Response",
        domain=ScenarioDomain.MEDICAL,
        description=(
            "You are a school nurse. A 14-year-old student runs in saying they ate "
            "something with nuts by mistake. Within 2 minutes: face is swelling, "
            "hives on arms, student says throat 'feels tight'. Known nut allergy; "
            "epinephrine auto-injector (EpiPen) is in the medical cabinet."
        ),
        initial_phase_id="ph1_recognition",
        learning_objectives=[
            "Recognise anaphylaxis signs rapidly (skin + airway + systemic)",
            "Administer epinephrine as first-line treatment",
            "Call emergency services and position patient correctly",
            "Prepare for biphasic reaction",
        ],
        prerequisite_skills=["basic_first_aid"],
        difficulty="intermediate",
    )

    scenario.phases["ph1_recognition"] = ScenarioPhase(
        phase_id="ph1_recognition",
        title="Recognition and First Action",
        situation_update="Student: swollen face, hives, throat tightness after nut ingestion. Conscious.",
        action_prompt="What is your immediate first action?",
        expert_action_id="a1_epipen",
        teaching_point="Epinephrine is the ONLY first-line treatment for anaphylaxis. Antihistamines and steroids are adjuncts — they work too slowly for airway compromise.",
        available_actions=[
            PhaseAction(
                action_id="a1_epipen",
                label="Administer EpiPen to outer thigh; call 999/911",
                description="Retrieve EpiPen, administer, call emergency services.",
                outcome=PhaseOutcome.OPTIMAL,
                consequence="Epinephrine administered. Symptoms begin to stabilise within 5 minutes. EMS called. Proceed to monitoring.",
                mastery_delta=0.20,
                unlocks_phase="ph2_monitoring",
            ),
            PhaseAction(
                action_id="a1_antihistamine",
                label="Give antihistamine tablet and monitor",
                description="Administer oral antihistamine first.",
                outcome=PhaseOutcome.CRITICAL_ERROR,
                consequence="Antihistamines take 20–40 min to act. Airway swelling progresses. Student deteriorates. Delayed epinephrine required.",
                mastery_delta=-0.30,
                unlocks_phase="ph2_monitoring",
            ),
            PhaseAction(
                action_id="a1_call_then_epi",
                label="Call 999/911 first, then give EpiPen",
                description="Phone EMS before administering epinephrine.",
                outcome=PhaseOutcome.SUBOPTIMAL,
                consequence="30-second delay before epinephrine. EMS called. Symptoms worsen slightly but still manageable. EpiPen administered.",
                mastery_delta=-0.05,
                unlocks_phase="ph2_monitoring",
            ),
        ],
    )

    scenario.phases["ph2_monitoring"] = ScenarioPhase(
        phase_id="ph2_monitoring",
        title="Post-Epinephrine Monitoring",
        situation_update="EpiPen given. Student improving: swelling reducing. EMS en route (8 min). At 6 min post-EpiPen, student says they feel better and wants to go to class.",
        action_prompt="The student feels better. What do you do?",
        expert_action_id="a2_keep_supine_observe",
        teaching_point="Biphasic anaphylaxis occurs in 5–20% of cases, 1–72 hours after the initial reaction. All anaphylaxis patients require hospital observation for at least 4 hours.",
        available_actions=[
            PhaseAction(
                action_id="a2_keep_supine_observe",
                label="Keep student supine; continue to monitor; await EMS",
                description="Do not allow student to leave. Maintain supine position. Observe.",
                outcome=PhaseOutcome.OPTIMAL,
                consequence="Student kept safe. EMS arrives and transports to hospital. No biphasic reaction.",
                mastery_delta=0.20,
            ),
            PhaseAction(
                action_id="a2_let_student_go",
                label="Student feels better — let them return to class",
                description="Allow student to leave the medical room.",
                outcome=PhaseOutcome.CRITICAL_ERROR,
                consequence="Student collapses in corridor 15 minutes later with biphasic anaphylaxis. Requires second epinephrine dose and emergency resuscitation.",
                mastery_delta=-0.35,
                terminates=False,
            ),
            PhaseAction(
                action_id="a2_sit_upright",
                label="Sit student upright and offer water",
                description="Allow student to sit up and drink.",
                outcome=PhaseOutcome.SUBOPTIMAL,
                consequence="Sitting up can cause positional hypotension in anaphylaxis. Student becomes dizzy. Supine position is preferred until EMS arrive.",
                mastery_delta=-0.08,
            ),
        ],
    )

    return scenario


def _build_cyber_incident_scenario() -> EmergencyScenario:
    scenario = EmergencyScenario(
        scenario_id="em_crisis_ransomware",
        title="Active Ransomware Incident Response",
        domain=ScenarioDomain.CRISIS,
        description=(
            "You are the CISO. It is 2 AM. SOC alerts: 40 servers are encrypting files. "
            "Ransomware has spread from a phishing email opened 6 hours ago. "
            "Backup server status: unknown. Customer-facing services are still running. "
            "Ransom note demands $2M in 48 hours."
        ),
        initial_phase_id="ph1_containment",
        learning_objectives=[
            "Containment before eradication — isolate before investigating",
            "Preserve evidence for forensics while containing",
            "Communication protocol: internal escalation before public statement",
            "Never pay ransom as the first response",
        ],
        prerequisite_skills=["incident_response_basics"],
        difficulty="advanced",
    )

    scenario.phases["ph1_containment"] = ScenarioPhase(
        phase_id="ph1_containment",
        title="Initial Containment",
        situation_update="40 servers encrypting. Customer services still live. Backup status unknown.",
        action_prompt="What is your first action?",
        expert_action_id="a1_isolate_network",
        teaching_point="Containment must precede investigation. Every minute of network connectivity allows lateral spread. Take snapshots of running memory on affected hosts for forensics before shutdown.",
        available_actions=[
            PhaseAction(
                action_id="a1_isolate_network",
                label="Isolate affected network segment; take memory snapshots; preserve logs",
                description="Cut network segment; forensic snapshots first; preserve logs.",
                outcome=PhaseOutcome.OPTIMAL,
                consequence="Ransomware contained to 40 servers. Backup server isolated before infection. Evidence preserved. Proceed to assessment.",
                mastery_delta=0.20,
                unlocks_phase="ph2_backup_assessment",
            ),
            PhaseAction(
                action_id="a1_shutdown_all",
                label="Shut down all servers immediately",
                description="Power off all affected servers.",
                outcome=PhaseOutcome.SUBOPTIMAL,
                consequence="Ransomware stopped but memory evidence destroyed. Forensic investigation severely hampered. Backup status still unknown.",
                mastery_delta=-0.08,
                unlocks_phase="ph2_backup_assessment",
            ),
            PhaseAction(
                action_id="a1_pay_ransom",
                label="Contact attackers and negotiate ransom",
                description="Begin ransom negotiation immediately.",
                outcome=PhaseOutcome.CRITICAL_ERROR,
                consequence="Ransomware continues spreading during negotiation. No guarantee of decryption key. Legal/regulatory breach possible. Spread worsens.",
                mastery_delta=-0.35,
                unlocks_phase="ph2_backup_assessment",
            ),
            PhaseAction(
                action_id="a1_investigate_first",
                label="Investigate patient zero before containing",
                description="Trace the phishing email source before acting.",
                outcome=PhaseOutcome.CRITICAL_ERROR,
                consequence="20 more servers encrypted during investigation. Customer-facing services now compromised. Containment window missed.",
                mastery_delta=-0.30,
                unlocks_phase="ph2_backup_assessment",
            ),
        ],
    )

    scenario.phases["ph2_backup_assessment"] = ScenarioPhase(
        phase_id="ph2_backup_assessment",
        title="Backup Assessment and Recovery Path",
        situation_update="Contained. Backup server checked: last clean backup is 18 hours old. Encryption began 6 hours ago so most critical data is in clean backup.",
        action_prompt="Recovery strategy?",
        expert_action_id="a2_restore_from_backup",
        teaching_point="An 18-hour-old clean backup is a viable recovery path. Wipe and restore is almost always faster and safer than decryption with an attacker-supplied key.",
        available_actions=[
            PhaseAction(
                action_id="a2_restore_from_backup",
                label="Wipe affected systems; restore from 18-hour backup; accept data loss window",
                description="Restore clean systems from backup.",
                outcome=PhaseOutcome.OPTIMAL,
                consequence="Recovery RTO: 6–8 hours. 18-hour data gap manageable. Customer services restored. Proceed to communication phase.",
                mastery_delta=0.20,
                unlocks_phase="ph3_communication",
            ),
            PhaseAction(
                action_id="a2_pay_for_key",
                label="Pay ransom to avoid 18-hour data gap",
                description="Pay the ransom to decrypt files.",
                outcome=PhaseOutcome.CRITICAL_ERROR,
                consequence="Payment made. No decryption key received. Data still encrypted. $2M lost. Backup restore now the only option — delayed by 4 hours.",
                mastery_delta=-0.40,
                unlocks_phase="ph3_communication",
            ),
            PhaseAction(
                action_id="a2_decrypt_in_place",
                label="Attempt to decrypt in place using third-party tool",
                description="Try community decryptors for this ransomware variant.",
                outcome=PhaseOutcome.SUBOPTIMAL,
                consequence="No public decryptor exists for this variant. 3-hour delay. Backup restore still required. Recovery delayed.",
                mastery_delta=-0.10,
                unlocks_phase="ph3_communication",
            ),
        ],
    )

    scenario.phases["ph3_communication"] = ScenarioPhase(
        phase_id="ph3_communication",
        title="Stakeholder Communication",
        situation_update="Recovery in progress. Board, legal, and regulator (24-hour notification requirement) must be informed. Media is asking questions on social media.",
        action_prompt="Communication order of priority?",
        expert_action_id="a3_internal_then_regulator",
        teaching_point="Notify board and legal first (decision authority), then regulator within required window, then customers, then public statement. Never lead with public statement — it creates a vacuum you cannot control.",
        available_actions=[
            PhaseAction(
                action_id="a3_internal_then_regulator",
                label="Board → Legal → Regulator → Customers → Public statement",
                description="Structured notification in priority order.",
                outcome=PhaseOutcome.OPTIMAL,
                consequence="All stakeholders informed in correct order. Regulatory notification within window. Controlled public statement issued.",
                mastery_delta=0.20,
            ),
            PhaseAction(
                action_id="a3_public_first",
                label="Issue public statement first to control narrative",
                description="Tweet/press release before internal notifications.",
                outcome=PhaseOutcome.CRITICAL_ERROR,
                consequence="Board and legal not briefed. Statement contains inaccuracies. Regulatory breach (notified late). Customer panic amplified.",
                mastery_delta=-0.30,
            ),
            PhaseAction(
                action_id="a3_say_nothing",
                label="Say nothing until fully recovered",
                description="Maintain silence until systems are back.",
                outcome=PhaseOutcome.CRITICAL_ERROR,
                consequence="Regulatory 24-hour notification breached. Legal exposure. Customer contracts include breach notification clauses — violated.",
                mastery_delta=-0.25,
            ),
        ],
    )

    return scenario


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------
_SCENARIO_REGISTRY: Dict[str, EmergencyScenario] = {
    s.scenario_id: s for s in [
        _build_engine_failure_scenario(),
        _build_anaphylaxis_scenario(),
        _build_cyber_incident_scenario(),
    ]
}


def get_emergency_scenario(scenario_id: str) -> Optional[EmergencyScenario]:
    return _SCENARIO_REGISTRY.get(scenario_id)


def list_emergency_scenarios(domain: Optional[ScenarioDomain] = None) -> List[EmergencyScenario]:
    scenarios = list(_SCENARIO_REGISTRY.values())
    if domain:
        scenarios = [s for s in scenarios if s.domain is domain]
    return scenarios


# ---------------------------------------------------------------------------
# EmergencyScenarioAgent — main interface
# ---------------------------------------------------------------------------
class EmergencyScenarioAgent:
    """Runs learners through emergency simulations and generates AARs.

    Stateless: all run state is owned by the caller (SimulationRun).
    """

    def list_scenarios(
        self, domain: Optional[ScenarioDomain] = None
    ) -> List[EmergencyScenario]:
        return list_emergency_scenarios(domain)

    def get_scenario(self, scenario_id: str) -> Optional[EmergencyScenario]:
        return get_emergency_scenario(scenario_id)

    def start_run(self, scenario: EmergencyScenario, learner_id: str) -> SimulationRun:
        run = SimulationRun(scenario_id=scenario.scenario_id, learner_id=learner_id)
        run.current_phase_id = scenario.initial_phase_id
        return run

    def current_phase(
        self, run: SimulationRun, scenario: EmergencyScenario
    ) -> Optional[ScenarioPhase]:
        return scenario.get_phase(run.current_phase_id)

    def apply_action(
        self,
        run: SimulationRun,
        phase: ScenarioPhase,
        action_id: str,
        time_taken_s: Optional[float] = None,
    ) -> Optional[PhaseAction]:
        """Apply a learner's action choice to the simulation run.

        Returns the chosen PhaseAction (for feedback display), or None if
        action_id is not found in the current phase.
        """
        action = next(
            (a for a in phase.available_actions if a.action_id == action_id), None
        )
        if action is None:
            return None
        run.record_decision(phase.phase_id, action, time_taken_s)
        return action

    def generate_aar(
        self, run: SimulationRun, scenario: EmergencyScenario
    ) -> AARReport:
        return generate_aar(run, scenario)

    def phase_prompt(
        self,
        phase: ScenarioPhase,
        *,
        wellness_state: str = "ok",
        include_options: bool = True,
    ) -> str:
        """Format a phase for display to the learner."""
        lines = [
            f"--- {phase.title} ---",
            phase.situation_update,
            "",
            phase.action_prompt,
        ]
        if include_options:
            lines.append("")
            for action in phase.available_actions:
                lines.append(f"  {action.action_id}: {action.label}")
        if wellness_state in ("stressed", "unwell") and phase.teaching_point:
            lines.append(f"\n[Guidance: consider — {phase.teaching_point[:120]}]")
        return "\n".join(lines)
