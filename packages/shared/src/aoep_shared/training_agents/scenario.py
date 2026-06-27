"""Scenario model + built-in critical-thinking / emergency training scenarios.

A *scenario* is a branching drill: an ordered list of phases, each presenting a
situational picture (observable cues + latent threats) and a set of timed
decision options scored by quality. The cognitive agents in :mod:`.agents`
consume this structure to coach situational awareness, rapid decision-making,
forecasting (pre-mortem), and critical thinking - and to score the learner.

Pure data + deterministic; no model server, network, or GPU required. New
domains (medical, fire, driving, ...) are authored by adding a :class:`Scenario`
to ``BUILTIN_SCENARIOS`` - no code forks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DecisionOption:
    """One choice the learner can make at a phase.

    ``score`` is the decision quality in 0..1 (1.0 = the textbook-correct action,
    lower for partially-right or dangerous choices). ``next_phase`` lets an option
    branch the scenario; ``None`` falls through to the scenario's linear order.
    """

    id: str
    text: str
    score: float
    feedback: str
    is_correct: bool = False
    consequence: str = ""
    next_phase: Optional[str] = None


@dataclass
class ScenarioPhase:
    """A single beat of the drill: a situation and the timed decision."""

    id: str
    title: str
    situation: str
    prompt: str
    options: List[DecisionOption]
    cues: List[str] = field(default_factory=list)        # observable now (perception)
    threats: List[str] = field(default_factory=list)     # latent risks (projection)
    decision_window_s: float = 10.0                      # split-second budget
    skills: List[str] = field(default_factory=list)
    recommended: str = ""                                # the pre-planned right move

    def option(self, option_id: str) -> Optional[DecisionOption]:
        for opt in self.options:
            if opt.id == option_id:
                return opt
        return None

    def best_option(self) -> DecisionOption:
        return max(self.options, key=lambda o: o.score)


@dataclass
class Scenario:
    """A complete training scenario (ordered, optionally branching phases)."""

    id: str
    title: str
    domain: str
    summary: str
    learning_objectives: List[str]
    phases: List[ScenarioPhase]
    difficulty: str = "intermediate"
    pass_threshold: float = 0.7

    def phase(self, phase_id: str) -> Optional[ScenarioPhase]:
        for ph in self.phases:
            if ph.id == phase_id:
                return ph
        return None

    def first_phase(self) -> ScenarioPhase:
        return self.phases[0]

    def next_phase_id(self, current_id: str) -> Optional[str]:
        """The phase that linearly follows ``current_id`` (None at the end)."""
        ids = [ph.id for ph in self.phases]
        try:
            idx = ids.index(current_id)
        except ValueError:
            return None
        return ids[idx + 1] if idx + 1 < len(ids) else None

    def all_skills(self) -> List[str]:
        seen: List[str] = []
        for ph in self.phases:
            for sk in ph.skills:
                if sk not in seen:
                    seen.append(sk)
        return seen

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "domain": self.domain,
            "summary": self.summary,
            "difficulty": self.difficulty,
            "phases": len(self.phases),
            "learning_objectives": list(self.learning_objectives),
            "skills": self.all_skills(),
        }


# --------------------------------------------------------------------------- #
# Built-in scenarios
# --------------------------------------------------------------------------- #
def _engine_out_landing() -> Scenario:
    """Flagship: single-engine total power loss -> forced/emergency landing.

    Mirrors the real airmanship priority ladder: Aviate (best glide) -> Navigate
    (pick a field) -> troubleshoot -> Communicate (mayday) -> secure & land.
    """
    return Scenario(
        id="engine-out-emergency-landing",
        title="Engine Failure & Emergency Landing (Cessna 172)",
        domain="aviation",
        summary=(
            "Your single-engine trainer loses all power in the climb. Fly the "
            "airplane, find a field, work the problem, declare the emergency, and "
            "put it down safely - under a ticking clock."
        ),
        difficulty="advanced",
        learning_objectives=[
            "Prioritize Aviate -> Navigate -> Communicate under stress",
            "Establish and hold best-glide attitude before anything else",
            "Read the situation fast and project the glide footprint",
            "Pre-plan failure modes (pre-mortem) before committing to a field",
        ],
        phases=[
            ScenarioPhase(
                id="engine_failure",
                title="Power loss in the climb",
                situation=(
                    "Climbing through 4,500 ft AGL, the engine sputters, coughs, "
                    "and goes silent. The nose is high, airspeed is bleeding off "
                    "fast, and the prop is windmilling. Your stomach drops."
                ),
                prompt="What is your FIRST action?",
                decision_window_s=8.0,
                cues=[
                    "Engine noise gone / prop windmilling",
                    "Nose-high attitude, airspeed decreasing",
                    "Altitude 4,500 ft AGL gives glide time",
                ],
                threats=[
                    "Stall/spin if airspeed decays at the high nose attitude",
                    "Fixation on the engine instead of flying the aircraft",
                ],
                skills=["situational_awareness", "rapid_decision", "emotional_control"],
                recommended="Lower the nose and establish best-glide airspeed (~68 kt).",
                options=[
                    DecisionOption(
                        "pitch_best_glide",
                        "Lower the nose to the best-glide attitude and trim for ~68 kt",
                        1.0, "Correct - Aviate first. Best glide buys maximum time and range "
                        "to solve everything else.", is_correct=True,
                        consequence="You're now gliding stably with time to think.",
                    ),
                    DecisionOption(
                        "hold_altitude",
                        "Pull back to hold altitude and stretch the glide",
                        0.05, "Dangerous - pulling up with no power bleeds airspeed toward a "
                        "stall/spin at low energy. Never trade speed you don't have.",
                        consequence="Airspeed decays toward stall; you're behind the aircraft.",
                    ),
                    DecisionOption(
                        "restart_first",
                        "Heads-down immediately on the restart checklist",
                        0.35, "Premature - troubleshooting before establishing the glide is the "
                        "classic fixation trap. Fly first, then fix.",
                        consequence="You drift off attitude while heads-down.",
                    ),
                    DecisionOption(
                        "mayday_first",
                        "Grab the mic and broadcast a mayday right now",
                        0.2, "Out of order - Communicate is third. Talking before you're "
                        "gliding wastes your most precious seconds.",
                        consequence="Seconds lost on the radio with the nose still high.",
                    ),
                ],
            ),
            ScenarioPhase(
                id="pick_field",
                title="Find somewhere to land",
                situation=(
                    "Gliding at best speed you have roughly 6 nm of range. Below: a "
                    "busy highway, a long plowed field aligned into the wind, a "
                    "wooded ridge, and the departure airport behind you - probably "
                    "too far to reach from this altitude."
                ),
                prompt="Where do you commit to land?",
                decision_window_s=12.0,
                cues=[
                    "~6 nm glide footprint",
                    "Plowed field aligned into the wind",
                    "Highway has traffic, signs, and wires",
                    "Departure airport is behind and likely out of glide",
                ],
                threats=[
                    "The 'impossible turn' back to the airport stalls many pilots",
                    "Power lines and traffic on roads are hard to see until late",
                ],
                skills=["situational_analysis", "forecasting", "rapid_decision"],
                recommended="Commit early to the open field into the wind.",
                options=[
                    DecisionOption(
                        "field_into_wind",
                        "Commit to the open field, landing into the wind",
                        1.0, "Correct - an open surface into the wind minimizes groundspeed and "
                        "obstacles. Committing early lets you set up a stable approach.",
                        is_correct=True,
                        consequence="You have a workable approach to a survivable surface.",
                    ),
                    DecisionOption(
                        "turn_back",
                        "Turn back toward the departure airport",
                        0.1, "The 'impossible turn' - from this altitude the turn back usually "
                        "ends in a stall/spin short of the runway. Resist it.",
                        consequence="You burn altitude in the turn and come up short.",
                    ),
                    DecisionOption(
                        "highway",
                        "Set up for the highway",
                        0.4, "Risky - roads hide power lines, signs, vehicles, and crowns. Use "
                        "only if no open field is reachable.",
                        consequence="Wires and traffic become a serious hazard on short final.",
                    ),
                    DecisionOption(
                        "trees",
                        "Aim for the wooded ridge to cushion the landing",
                        0.15, "Poor - trees are a last resort; impact forces and penetration are "
                        "high. An open field is far better here.",
                        consequence="High-energy contact with terrain and trees.",
                    ),
                ],
            ),
            ScenarioPhase(
                id="troubleshoot",
                title="Work the problem (engine restart flow)",
                situation=(
                    "The field is made and you have a few hundred feet to spare. "
                    "Before you're committed to the flare, you have time for the "
                    "engine-failure flow from memory."
                ),
                prompt="What do you do with the spare seconds?",
                decision_window_s=10.0,
                cues=[
                    "Field is made with margin",
                    "Time for one memory checklist pass",
                ],
                threats=[
                    "A missed fuel selector / mixture item can leave a restartable engine off",
                    "Re-fixating on restart and forgetting to fly the approach",
                ],
                skills=["critical_thinking", "situational_awareness"],
                recommended="Run the flow: fuel BOTH, mixture rich, carb heat, mags, primer in.",
                options=[
                    DecisionOption(
                        "run_flow",
                        "Run the engine-failure flow: fuel selector BOTH, mixture rich, "
                        "carb heat ON, mags both/start, primer locked",
                        1.0, "Correct - a fast, disciplined memory flow can catch a simple cause "
                        "(fuel selector, mixture, carb ice) and is worth the seconds when the "
                        "field is already made.", is_correct=True,
                        consequence="No restart, but you've ruled out the simple causes - keep flying.",
                    ),
                    DecisionOption(
                        "skip_flow",
                        "Skip troubleshooting entirely and just fly the approach",
                        0.45, "Defensible but incomplete - with the field made you had time for "
                        "one flow pass that might have restarted the engine.",
                        consequence="You commit to a dead-stick landing without ruling out simple causes.",
                    ),
                    DecisionOption(
                        "obsess_restart",
                        "Keep cycling the starter and ignore the approach",
                        0.1, "Dangerous fixation - the engine is secondary now; an unflown "
                        "approach kills you faster than a stopped engine.",
                        consequence="You stop flying the airplane while heads-down.",
                    ),
                ],
            ),
            ScenarioPhase(
                id="declare",
                title="Communicate the emergency",
                situation=(
                    "Passing ~1,500 ft, committed to the field, the engine cold. "
                    "You have a moment to let someone know."
                ),
                prompt="How do you communicate?",
                decision_window_s=10.0,
                cues=[
                    "Committed to the field, ~1,500 ft",
                    "121.5 guard and transponder available",
                ],
                threats=[
                    "Over-talking on the radio at the expense of flying the approach",
                ],
                skills=["communication", "rapid_decision"],
                recommended="Mayday x3 on 121.5, squawk 7700, state position/souls/intentions - briefly.",
                options=[
                    DecisionOption(
                        "mayday_squawk",
                        "Mayday x3 on 121.5, squawk 7700, state position, souls on board, "
                        "and intentions - then back to flying",
                        1.0, "Correct - a concise mayday plus 7700 gets help moving without "
                        "stealing attention from the approach.", is_correct=True,
                        consequence="Help is alerted and you're still flying the airplane.",
                    ),
                    DecisionOption(
                        "long_call",
                        "Make a detailed, lengthy radio call explaining everything",
                        0.4, "Too much - brevity matters. Long transmissions pull your focus off "
                        "the flare you're about to fly.",
                        consequence="Attention drifts from the approach.",
                    ),
                    DecisionOption(
                        "no_call",
                        "Skip the radio - just land",
                        0.5, "Understandable under load, but a 5-second mayday + 7700 costs little "
                        "and could save your life after touchdown.",
                        consequence="No one knows where to send help.",
                    ),
                ],
            ),
            ScenarioPhase(
                id="secure_land",
                title="Secure the aircraft and land",
                situation=(
                    "Short final to the field. Touchdown is seconds away. You want "
                    "to arrive slow, under control, and survivable."
                ),
                prompt="Final actions before touchdown?",
                decision_window_s=10.0,
                cues=[
                    "Short final, low energy desired",
                    "Time for the securing items and a brace",
                ],
                threats=[
                    "Fuel/electrical left on raises post-impact fire risk",
                    "Excess speed at touchdown raises impact forces",
                ],
                skills=["critical_thinking", "emotional_control"],
                recommended=(
                    "Flaps as needed, fuel OFF, mixture idle cut-off, mags OFF, master OFF "
                    "before touchdown, doors cracked, touch down at minimum controllable speed, brace."
                ),
                options=[
                    DecisionOption(
                        "secure_brace",
                        "Flaps as needed, fuel OFF, mixture cut-off, mags + master OFF, doors "
                        "unlatched, touch down slow, brace",
                        1.0, "Correct - securing fuel and electrics cuts fire risk, unlatched "
                        "doors prevent jamming, and minimum speed lowers impact forces.",
                        is_correct=True,
                        consequence="Controlled, low-energy touchdown; everyone walks away.",
                    ),
                    DecisionOption(
                        "fast_flat",
                        "Keep extra speed for control and land flat and fast",
                        0.2, "Dangerous - extra speed multiplies impact energy and float. Arrive "
                        "as slow as you safely can.",
                        consequence="High-energy arrival; greater damage and injury risk.",
                    ),
                    DecisionOption(
                        "leave_systems",
                        "Leave fuel and electrics on in case the engine catches",
                        0.25, "Risky - by now the engine won't save you; live fuel and sparks "
                        "after impact are a fire hazard.",
                        consequence="Avoidable post-impact fire risk.",
                    ),
                ],
            ),
        ],
    )


def _kitchen_fire() -> Scenario:
    """A short everyday emergency: a stovetop grease fire (general critical thinking)."""
    return Scenario(
        id="kitchen-grease-fire",
        title="Stovetop Grease Fire",
        domain="home-safety",
        summary=(
            "A pan of oil bursts into flame while you cook. Quick, correct action "
            "in the first seconds is everything."
        ),
        difficulty="beginner",
        learning_objectives=[
            "Recognize fire class and pick the right suppression",
            "Avoid the instinctive-but-wrong response (water on grease)",
            "Project how a small fire becomes a large one",
        ],
        phases=[
            ScenarioPhase(
                id="ignition",
                title="The pan ignites",
                situation=(
                    "Oil in the frying pan starts smoking, then flames leap up a "
                    "foot above the pan. The burner is still on."
                ),
                prompt="First action?",
                decision_window_s=6.0,
                cues=["Flames from an oil pan", "Burner still on", "Lid within reach"],
                threats=["Water on grease causes an explosive flare-up",
                         "Fire spreads to cabinets/range hood within seconds"],
                skills=["rapid_decision", "situational_awareness"],
                recommended="Turn off the heat and smother with a lid; never use water.",
                options=[
                    DecisionOption(
                        "lid_off_heat",
                        "Slide a metal lid over the pan and turn off the burner",
                        1.0, "Correct - smothering removes oxygen and killing the heat stops the "
                        "fuel. This is the textbook grease-fire response.", is_correct=True,
                        consequence="Flames starve and die within seconds.",
                    ),
                    DecisionOption(
                        "water",
                        "Throw a cup of water on it",
                        0.0, "Dangerous - water flashes to steam and hurls burning oil outward, "
                        "creating a fireball. Never put water on a grease fire.",
                        consequence="A violent flare-up spreads fire across the kitchen.",
                    ),
                    DecisionOption(
                        "carry_outside",
                        "Pick up the flaming pan and carry it outside",
                        0.1, "Dangerous - moving burning oil risks spills and severe burns.",
                        consequence="Burning oil sloshes; you risk dropping it and spreading fire.",
                    ),
                    DecisionOption(
                        "baking_soda",
                        "Smother it with baking soda",
                        0.7, "Workable for a small fire - baking soda smothers, but a lid is faster "
                        "and more reliable. Flour would be dangerous.", 
                        consequence="It helps, but you used more time than a lid would.",
                    ),
                ],
            ),
            ScenarioPhase(
                id="after",
                title="After the flames are out",
                situation=(
                    "The lid is on and flames are out, but the pan is extremely hot "
                    "and smoke fills the kitchen."
                ),
                prompt="Next?",
                decision_window_s=10.0,
                cues=["Pan very hot under the lid", "Smoke in the room"],
                threats=["Re-ignition if the lid is lifted too soon",
                         "Smoke inhalation"],
                skills=["critical_thinking", "forecasting"],
                recommended="Leave the lid on to cool, ventilate, and stay ready with an extinguisher.",
                options=[
                    DecisionOption(
                        "leave_cool_ventilate",
                        "Leave the lid on to cool, open windows, and keep an extinguisher handy",
                        1.0, "Correct - hot oil can re-ignite; let it cool fully before lifting the "
                        "lid, and clear the smoke.", is_correct=True,
                        consequence="Fire stays out; air clears safely.",
                    ),
                    DecisionOption(
                        "peek",
                        "Lift the lid right away to check",
                        0.2, "Risky - introducing oxygen to still-hot oil can re-ignite it.",
                        consequence="A small re-flare is possible.",
                    ),
                ],
            ),
        ],
    )


def _build_registry() -> Dict[str, Scenario]:
    scenarios = [_engine_out_landing(), _kitchen_fire()]
    return {s.id: s for s in scenarios}


BUILTIN_SCENARIOS: Dict[str, Scenario] = _build_registry()


def list_scenarios() -> List[Scenario]:
    return list(BUILTIN_SCENARIOS.values())


def get_scenario(scenario_id: str) -> Optional[Scenario]:
    return BUILTIN_SCENARIOS.get(scenario_id)
