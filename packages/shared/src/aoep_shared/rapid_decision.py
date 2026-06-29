"""Rapid Decision Training Agent.

Trains split-second and time-critical decision-making under controlled
cognitive pressure.  Used for scenarios where a learner must choose and
act faster than deliberate analysis allows — fighter-pilot OODA collapse,
ER triage, trading floor stops, etc.

Design
------
- Pressure calibration: time windows scale with learner proficiency so
  novices are not overwhelmed (stress inoculation theory: graduated exposure).
- Cognitive load awareness: if the learner's wellness state is "stressed"
  or "unwell", the agent reduces time pressure and supplies more scaffolding.
- Post-drill debrief: every drill ends with a structured After-Decision Review
  (ADR) explaining the ideal choice and common failure modes.
- Pure Python, dependency-free, testable offline.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class PressureLevel(str, Enum):
    """Cognitive pressure tier for a drill."""
    DELIBERATE = "deliberate"    # no timer — build mental model
    MODERATE = "moderate"        # 2× ideal time
    TIME_CRITICAL = "time_critical"  # 1.1× ideal time
    SPLIT_SECOND = "split_second"   # 0.6× ideal time (reflex training)


class DrillOutcome(str, Enum):
    CORRECT_FAST = "correct_fast"
    CORRECT_SLOW = "correct_slow"
    INCORRECT_FAST = "incorrect_fast"
    INCORRECT_SLOW = "incorrect_slow"
    TIMEOUT = "timeout"


# ---------------------------------------------------------------------------
# Drill shapes
# ---------------------------------------------------------------------------
@dataclass
class DecisionOption:
    label: str           # short identifier, e.g. "A"
    text: str            # description shown to learner
    is_correct: bool
    rationale: str = ""  # why this is correct or not


@dataclass
class RapidDrill:
    """One rapid-decision training drill."""
    drill_id: str
    domain: str
    situation: str           # scenario vignette (2–3 sentences max)
    options: List[DecisionOption]
    ideal_seconds: float     # time a trained expert would take
    cue_to_spot: str         # the key recognition cue that short-circuits deliberation
    failure_mode: str        # most common mistake under pressure
    skill_tag: str = "general"

    def correct_option(self) -> Optional[DecisionOption]:
        for o in self.options:
            if o.is_correct:
                return o
        return None


@dataclass
class DrillAttempt:
    """Records a learner's attempt at one rapid drill."""
    drill_id: str
    chosen_label: str
    time_taken_s: float
    pressure_level: PressureLevel
    started_at: float = field(default_factory=time.time)

    def outcome(self, drill: RapidDrill, allowed_seconds: float) -> DrillOutcome:
        correct = any(
            o.label == self.chosen_label and o.is_correct for o in drill.options
        )
        over_time = self.time_taken_s > allowed_seconds
        if over_time and not correct:
            return DrillOutcome.TIMEOUT
        if correct and not over_time:
            return DrillOutcome.CORRECT_FAST
        if correct and over_time:
            return DrillOutcome.CORRECT_SLOW
        if not correct and not over_time:
            return DrillOutcome.INCORRECT_FAST
        return DrillOutcome.INCORRECT_SLOW


@dataclass
class DrillResult:
    drill_id: str
    outcome: DrillOutcome
    time_taken_s: float
    allowed_seconds: float
    correct_option_label: str
    feedback: str
    adr: str               # After-Decision Review narrative
    cue_spotlight: str     # what cue the expert spots first


@dataclass
class RapidDecisionSession:
    """Tracks a learner's performance across a set of drills in one session."""
    session_id: str
    pressure_level: PressureLevel
    drill_results: List[DrillResult] = field(default_factory=list)
    streak_correct: int = 0
    total_drills: int = 0
    correct_count: int = 0

    def accuracy(self) -> float:
        if not self.total_drills:
            return 0.0
        return self.correct_count / self.total_drills

    def avg_time(self) -> float:
        if not self.drill_results:
            return 0.0
        return sum(r.time_taken_s for r in self.drill_results) / len(self.drill_results)

    def recommended_next_pressure(self) -> PressureLevel:
        """Recommend next pressure level based on session performance."""
        acc = self.accuracy()
        if acc >= 0.85 and self.pressure_level is PressureLevel.MODERATE:
            return PressureLevel.TIME_CRITICAL
        if acc >= 0.85 and self.pressure_level is PressureLevel.TIME_CRITICAL:
            return PressureLevel.SPLIT_SECOND
        if acc < 0.5 and self.pressure_level is not PressureLevel.DELIBERATE:
            return PressureLevel.DELIBERATE
        return self.pressure_level


# ---------------------------------------------------------------------------
# Drill library
# ---------------------------------------------------------------------------
DRILL_LIBRARY: List[RapidDrill] = [
    RapidDrill(
        drill_id="rd_av_01",
        domain="aviation",
        situation=(
            "Engine stops on takeoff at 300 ft AGL. Runway remaining is 400 ft. "
            "Terrain ahead is flat open field. Wind is calm."
        ),
        options=[
            DecisionOption("A", "Land straight ahead on remaining runway or field", is_correct=True,
                           rationale="Below critical height — turning back is statistically fatal."),
            DecisionOption("B", "Turn back to runway (180° turn)", is_correct=False,
                           rationale="Insufficient altitude for a 'dead-man's curve' turn-back."),
            DecisionOption("C", "Climb and troubleshoot engine", is_correct=False,
                           rationale="No power means no climb; troubleshoot = delay action."),
            DecisionOption("D", "Declare Mayday and wait for vectors", is_correct=False,
                           rationale="No time for ATC contact at 300 ft with engine out."),
        ],
        ideal_seconds=4.0,
        cue_to_spot="300 ft AGL → below decision height for turn-back",
        failure_mode="Attempting runway turn-back below 500 ft",
        skill_tag="aviation_emergency",
    ),
    RapidDrill(
        drill_id="rd_av_02",
        domain="aviation",
        situation=(
            "IFR flight: autopilot disconnects, attitude indicator shows 60° bank. "
            "Aircraft descending at 2,000 fpm. Clouds obscure outside reference."
        ),
        options=[
            DecisionOption("A", "Level wings on attitude indicator; reduce power; pull gently", is_correct=True,
                           rationale="Unusual attitude recovery: wings first, then pitch."),
            DecisionOption("B", "Pull back to stop descent first", is_correct=False,
                           rationale="Pulling in a bank tightens the spiral — accelerates descent."),
            DecisionOption("C", "Increase power to climb out", is_correct=False,
                           rationale="Power in a spiral increases speed and structural load."),
            DecisionOption("D", "Declare emergency and ask for vectors", is_correct=False,
                           rationale="No time — aircraft will exceed Vne or hit terrain first."),
        ],
        ideal_seconds=5.0,
        cue_to_spot="High bank + descending = incipient spiral dive",
        failure_mode="Pulling back before levelling wings",
        skill_tag="aviation_unusual_attitude",
    ),
    RapidDrill(
        drill_id="rd_med_01",
        domain="medical",
        situation=(
            "ER nurse: patient suddenly becomes unresponsive mid-conversation. "
            "No pulse felt. Defibrillator is 15 ft away."
        ),
        options=[
            DecisionOption("A", "Start CPR immediately; shout for help + AED", is_correct=True,
                           rationale="Every minute without CPR reduces survival by ~10%."),
            DecisionOption("B", "Fetch the defibrillator first (15 ft away)", is_correct=False,
                           rationale="15 seconds of CPR delay for retrieval reduces survival."),
            DecisionOption("C", "Call the code first, then start CPR", is_correct=False,
                           rationale="Shouting for help takes 2 s; CPR should begin simultaneously."),
            DecisionOption("D", "Recheck pulse for 10 s to confirm arrest", is_correct=False,
                           rationale="10-s pulse check delay is no longer recommended; assume arrest."),
        ],
        ideal_seconds=3.0,
        cue_to_spot="Unresponsive + no pulse = cardiac arrest → CPR first",
        failure_mode="Delaying CPR to retrieve equipment",
        skill_tag="cardiac_arrest",
    ),
    RapidDrill(
        drill_id="rd_fire_01",
        domain="fire_evacuation",
        situation=(
            "You enter a corridor and see thick black smoke near the ceiling. "
            "The fire exit is at the far end of the corridor (40 m). "
            "A stairwell is behind you (3 m)."
        ),
        options=[
            DecisionOption("A", "Turn back to stairwell; stay low; use exit behind you", is_correct=True,
                           rationale="Black smoke = toxic gases near ceiling; stairwell is closer and safe."),
            DecisionOption("B", "Run fast through smoke to far exit", is_correct=False,
                           rationale="40 m through toxic smoke risks incapacitation."),
            DecisionOption("C", "Shout for others then assess", is_correct=False,
                           rationale="In life-safety situations self-evacuation precedes rescue by untrained persons."),
            DecisionOption("D", "Open window and await rescue", is_correct=False,
                           rationale="Corridor window doesn't help; stairwell route is available."),
        ],
        ideal_seconds=4.0,
        cue_to_spot="Black smoke near ceiling = high toxicity; closer exit available",
        failure_mode="Committing to the far exit despite closer option",
        skill_tag="fire_evacuation",
    ),
    RapidDrill(
        drill_id="rd_cyber_01",
        domain="cybersecurity",
        situation=(
            "SOC alert: a privileged admin account is logging in from an unusual country "
            "at 3 AM local time and is running a script that deletes shadow copies. "
            "The account holder is currently on holiday."
        ),
        options=[
            DecisionOption("A", "Disable account and isolate affected hosts immediately", is_correct=True,
                           rationale="Shadow-copy deletion = active ransomware; containment first."),
            DecisionOption("B", "Email the account holder to verify", is_correct=False,
                           rationale="Account holder is on holiday; delay enables encryption spread."),
            DecisionOption("C", "Collect evidence for 30 min before acting", is_correct=False,
                           rationale="Evidence collection while ransomware runs = catastrophic data loss."),
            DecisionOption("D", "Alert management and await authorisation", is_correct=False,
                           rationale="Active destructive attack requires immediate technical response."),
        ],
        ideal_seconds=8.0,
        cue_to_spot="Shadow-copy deletion = ransomware deployment in progress",
        failure_mode="Evidence collection or approval delays during active attack",
        skill_tag="incident_response",
    ),
    RapidDrill(
        drill_id="rd_triage_01",
        domain="medical",
        situation=(
            "Mass casualty event: 4 patients arrive simultaneously. "
            "A: unconscious, not breathing after repositioning airway. "
            "B: screaming, leg fracture, walking. "
            "C: silent, pale, rapid weak pulse, abdominal wound. "
            "D: minor lacerations, alert, demanding treatment."
        ),
        options=[
            DecisionOption("A", "Prioritise C (silent, shock signs, abdominal wound)", is_correct=True,
                           rationale="Silent + shock + penetrating wound = immediate life threat. A = expectant (no spontaneous breathing post-reposition)."),
            DecisionOption("B", "Prioritise A (unconscious, not breathing)", is_correct=False,
                           rationale="In mass casualty, A is expectant (non-survivable without resources). C has higher survival probability if treated now."),
            DecisionOption("C", "Prioritise B (screaming, walking)", is_correct=False,
                           rationale="Walking + screaming = delayed category; B can wait."),
            DecisionOption("D", "Prioritise D (demanding treatment)", is_correct=False,
                           rationale="Demanding treatment = minimal category; minor injury."),
        ],
        ideal_seconds=6.0,
        cue_to_spot="Silent + pale + rapid weak pulse = compensated shock → immediate",
        failure_mode="Treating the loudest patient first (they are often the least critical)",
        skill_tag="mass_casualty_triage",
    ),
]


def get_drill(drill_id: str) -> Optional[RapidDrill]:
    for d in DRILL_LIBRARY:
        if d.drill_id == drill_id:
            return d
    return None


def list_drills(domain: Optional[str] = None, skill_tag: Optional[str] = None) -> List[RapidDrill]:
    result = DRILL_LIBRARY
    if domain:
        result = [d for d in result if d.domain == domain]
    if skill_tag:
        result = [d for d in result if d.skill_tag == skill_tag]
    return result


# ---------------------------------------------------------------------------
# Pressure-window calculation
# ---------------------------------------------------------------------------
def allowed_time(
    drill: RapidDrill,
    pressure_level: PressureLevel,
    *,
    wellness_state: str = "ok",
) -> float:
    """Compute allowed seconds given pressure level and wellness state."""
    multipliers = {
        PressureLevel.DELIBERATE: 10.0,
        PressureLevel.MODERATE: 2.0,
        PressureLevel.TIME_CRITICAL: 1.1,
        PressureLevel.SPLIT_SECOND: 0.6,
    }
    base = drill.ideal_seconds * multipliers[pressure_level]
    # Wellness adjustment: stressed/unwell learners get +40% time
    if wellness_state in ("stressed", "unwell", "low_energy"):
        base *= 1.4
    return round(base, 1)


# ---------------------------------------------------------------------------
# After-Decision Review
# ---------------------------------------------------------------------------
def build_adr(drill: RapidDrill, attempt: DrillAttempt, outcome: DrillOutcome) -> str:
    """Construct an After-Decision Review narrative."""
    correct = drill.correct_option()
    chosen = next((o for o in drill.options if o.label == attempt.chosen_label), None)
    lines = [f"--- After-Decision Review: {drill.drill_id} ---"]

    if outcome in (DrillOutcome.CORRECT_FAST, DrillOutcome.CORRECT_SLOW):
        lines.append("DECISION: Correct.")
        if outcome is DrillOutcome.CORRECT_SLOW:
            lines.append(
                f"TIME: {attempt.time_taken_s:.1f}s (ideal: {drill.ideal_seconds:.1f}s). "
                "Build speed by pattern-matching the key cue."
            )
    else:
        if chosen:
            lines.append(f"You chose: {chosen.label} — {chosen.text}")
            lines.append(f"Why that's problematic: {chosen.rationale}")
        if correct:
            lines.append(f"Optimal choice: {correct.label} — {correct.text}")
            lines.append(f"Why: {correct.rationale}")

    lines.append(f"Key recognition cue: {drill.cue_to_spot}")
    lines.append(f"Most common failure mode: {drill.failure_mode}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# RapidDecisionAgent — main interface
# ---------------------------------------------------------------------------
class RapidDecisionAgent:
    """Stateless rapid-decision training agent.

    Callers own DrillAttempt / RapidDecisionSession state.
    """

    def list_drills(
        self, domain: Optional[str] = None, skill_tag: Optional[str] = None
    ) -> List[RapidDrill]:
        return list_drills(domain, skill_tag)

    def get_drill(self, drill_id: str) -> Optional[RapidDrill]:
        return get_drill(drill_id)

    def allowed_time(
        self,
        drill: RapidDrill,
        pressure_level: PressureLevel,
        *,
        wellness_state: str = "ok",
    ) -> float:
        return allowed_time(drill, pressure_level, wellness_state=wellness_state)

    def evaluate_attempt(
        self,
        drill: RapidDrill,
        attempt: DrillAttempt,
        session: Optional[RapidDecisionSession] = None,
    ) -> DrillResult:
        """Score a drill attempt, build ADR, and optionally update session stats."""
        a_time = allowed_time(drill, attempt.pressure_level)
        outcome = attempt.outcome(drill, a_time)
        adr = build_adr(drill, attempt, outcome)

        correct = drill.correct_option()
        correct_label = correct.label if correct else "?"

        if outcome is DrillOutcome.CORRECT_FAST:
            feedback = "Excellent — correct and fast. Pattern recognition is working."
        elif outcome is DrillOutcome.CORRECT_SLOW:
            feedback = (
                f"Correct decision, but {attempt.time_taken_s:.1f}s (allowed {a_time:.1f}s). "
                "Practice spotting the key cue faster."
            )
        elif outcome is DrillOutcome.TIMEOUT:
            feedback = (
                "Time expired. In a real situation, delayed action is often equivalent "
                "to the wrong action. Focus on the key cue."
            )
        else:
            feedback = (
                "Incorrect decision. Review the ADR below and repeat the drill."
            )

        result = DrillResult(
            drill_id=drill.drill_id,
            outcome=outcome,
            time_taken_s=attempt.time_taken_s,
            allowed_seconds=a_time,
            correct_option_label=correct_label,
            feedback=feedback,
            adr=adr,
            cue_spotlight=drill.cue_to_spot,
        )

        if session is not None:
            session.total_drills += 1
            session.drill_results.append(result)
            if outcome in (DrillOutcome.CORRECT_FAST, DrillOutcome.CORRECT_SLOW):
                session.correct_count += 1
                session.streak_correct += 1
            else:
                session.streak_correct = 0

        return result

    def calibrate_pressure(
        self,
        current_accuracy: float,
        current_pressure: PressureLevel,
        *,
        wellness_state: str = "ok",
    ) -> Tuple[PressureLevel, str]:
        """Recommend pressure level adjustment based on performance and wellness."""
        if wellness_state in ("stressed", "unwell"):
            return PressureLevel.DELIBERATE, "wellness_state_requires_reduced_pressure"

        order = [
            PressureLevel.DELIBERATE,
            PressureLevel.MODERATE,
            PressureLevel.TIME_CRITICAL,
            PressureLevel.SPLIT_SECOND,
        ]
        idx = order.index(current_pressure)

        if current_accuracy >= 0.85 and idx < len(order) - 1:
            return order[idx + 1], "accuracy_high_increasing_pressure"
        if current_accuracy < 0.50 and idx > 0:
            return order[idx - 1], "accuracy_low_reducing_pressure"
        return current_pressure, "pressure_maintained"

    def session_summary(self, session: RapidDecisionSession) -> Dict[str, object]:
        return {
            "session_id": session.session_id,
            "pressure_level": session.pressure_level.value,
            "total_drills": session.total_drills,
            "correct_count": session.correct_count,
            "accuracy": round(session.accuracy(), 3),
            "avg_time_s": round(session.avg_time(), 2),
            "streak_correct": session.streak_correct,
            "recommended_next_pressure": session.recommended_next_pressure().value,
        }
