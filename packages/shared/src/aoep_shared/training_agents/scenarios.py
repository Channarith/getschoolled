"""Built-in scenario definitions for critical-thinking and emergency training."""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import ScenarioCue, ScenarioDefinition, ScenarioDomain


def _cue(cid: str, text: str, priority: str = "medium") -> ScenarioCue:
    return ScenarioCue(cue_id=cid, text=text, priority=priority)


AVIATION_EMERGENCY_LANDING = ScenarioDefinition(
    scenario_id="aviation_emergency_landing",
    title="Engine failure — emergency landing (sim)",
    domain=ScenarioDomain.AVIATION,
    briefing=(
        "You are PIC on a single-engine trainer at 3,000 ft MSL, 8 nm from the "
        "nearest airport. Cruise power is set. Suddenly the engine coughs, RPM "
        "drops, and oil pressure falls. Train for calm procedure under pressure — "
        "not memorized answers."
    ),
    cues=[
        _cue("engine", "Engine RPM unstable; partial power only", "critical"),
        _cue("oil", "Oil pressure trending low", "high"),
        _cue("altitude", "3,000 ft MSL; terrain is flat farmland below", "medium"),
        _cue("wind", "Wind 240° at 12 kt — crosswind likely on runway 27", "medium"),
        _cue("traffic", "No other traffic reported in the pattern", "low"),
        _cue("fuel", "Fuel gauges show ~45 minutes remaining", "medium"),
        _cue("airport", "Nearest airport 8 nm on the 270 radial; runway 27/09", "high"),
    ],
    decision_prompt=(
        "You have roughly 60 seconds before you must commit. What is your FIRST "
        "action sequence? State priorities, not every switch."
    ),
    decision_time_limit_s=60,
    emergency_steps=[
        "Aviate — maintain aircraft control; establish best glide if power lost",
        "Navigate — point toward nearest suitable landing area",
        "Communicate — squawk 7700 and declare mayday with position/intent",
        "Checklist — fuel selector, mixture, ignition, carb heat as applicable",
        "Land — stabilize approach; accept off-field if necessary; protect lives first",
    ],
    foresight_prompts=[
        "Before the engine fails: what cues would you brief your student to watch?",
        "If glide range is insufficient: what options do you prepare mentally now?",
        "After touchdown: what hazards remain (fuel, inertia, egress)?",
    ],
    critical_thinking_prompts=[
        "Why prioritize aviate before troubleshoot?",
        "What assumptions are you making about runway length and wind?",
        "How would you know if a partial-power landing is safer than a dead-stick?",
    ],
    debrief_rubric=[
        "Maintained aircraft control first",
        "Selected a landing area early",
        "Communicated position and intent",
        "Used checklist without fixation",
        "Anticipated post-landing hazards",
    ],
    skills=["aviation", "emergency-procedures", "critical-thinking", "situational-awareness"],
)


MEDICAL_TRIAGE_QUICK = ScenarioDefinition(
    scenario_id="medical_triage_quick",
    title="Mass-casualty triage — 60-second sort",
    domain=ScenarioDomain.MEDICAL,
    briefing=(
        "A parking-lot incident produced multiple injured people. You are first on "
        "scene with basic first-aid training. You have one minute to categorize "
        "who needs care first."
    ),
    cues=[
        _cue("victim_a", "Adult male, conscious, yelling, large arm laceration", "medium"),
        _cue("victim_b", "Child, quiet, pale, rapid breathing, femur deformity", "critical"),
        _cue("victim_c", "Older adult, unresponsive, no obvious bleeding", "critical"),
        _cue("victim_d", "Teen, walking, glass in hand, minor cuts", "low"),
        _cue("scene", "Fuel smell near a damaged vehicle — fire risk", "high"),
        _cue("help", "Second responder 3 minutes out", "medium"),
    ],
    decision_prompt="In 60 seconds: who do you approach first, second, third — and why?",
    decision_time_limit_s=60,
    emergency_steps=[
        "Scene safety — remove self/others from immediate danger",
        "Triage — immediate life threats before detailed treatment",
        "Communicate — relay counts and priorities to incoming help",
        "Reassess — victims change category as conditions evolve",
    ],
    foresight_prompts=[
        "What could make victim B deteriorate in the next 5 minutes?",
        "If the fuel ignites, how does your plan change?",
    ],
    critical_thinking_prompts=[
        "Why might the loudest victim not be the most urgent?",
        "What information is missing that would change your order?",
    ],
    debrief_rubric=[
        "Addressed scene safety",
        "Prioritized life threats over visible injuries",
        "Justified order with physiology not noise",
        "Planned for deterioration",
    ],
    skills=["medical-triage", "quick-decision", "situational-analysis"],
)


FIRE_EVACUATION = ScenarioDefinition(
    scenario_id="fire_evacuation",
    title="Office fire — situational evacuation",
    domain=ScenarioDomain.FIRE_SAFETY,
    briefing=(
        "Mid-afternoon on the 4th floor. The fire alarm sounds and you smell smoke "
        "near the east stairwell. Train situational scanning before movement."
    ),
    cues=[
        _cue("smoke", "Light smoke visible at east stair door", "high"),
        _cue("crowd", "Coworkers gathering at main elevator bank", "medium"),
        _cue("exit", "West stairwell sign lit; door cool to touch", "high"),
        _cue("mobility", "Colleague with sprained ankle nearby", "medium"),
        _cue("weather", "Windows show heavy rain — exterior assembly wet/slippery", "low"),
    ],
    decision_prompt="What do you do in the first 30 seconds? Include how you help others.",
    decision_time_limit_s=45,
    emergency_steps=[
        "Alert — activate alarm if not sounding; call emergency services",
        "Assess — choose exit away from smoke; never use elevators",
        "Assist — help mobility-impaired without blocking flow",
        "Account — proceed to assembly point; report missing persons",
    ],
    foresight_prompts=[
        "If the west stair is blocked, what is your backup?",
        "How do you prevent stampede at the elevator bank?",
    ],
    critical_thinking_prompts=[
        "Which cues are reliable vs misleading during alarm fatigue?",
        "How do you balance speed with helping a slower colleague?",
    ],
    debrief_rubric=[
        "Avoided smoke and elevators",
        "Chose viable exit with verification",
        "Coordinated help without blocking egress",
        "Had assembly accountability plan",
    ],
    skills=["fire-safety", "situational-analysis", "critical-thinking"],
)


MEDIA_CLAIM_VERIFICATION = ScenarioDefinition(
    scenario_id="media_claim_verification",
    title="Viral claim — critical thinking under time pressure",
    domain=ScenarioDomain.MEDIA_LITERACY,
    briefing=(
        "A viral post claims a new supplement 'cures' a chronic condition overnight. "
        "Your team must decide whether to share it internally before a meeting in "
        "two minutes. Train evidence evaluation, not debate theater."
    ),
    cues=[
        _cue("source", "Post cites 'a doctor' with no name or credentials", "high"),
        _cue("evidence", "No linked clinical trial or regulatory approval", "critical"),
        _cue("urgency", "Colleague says 'we need to share now before competitors'", "medium"),
        _cue("harm", "Condition affects vulnerable population; bad advice could harm", "high"),
        _cue("counter", "Reputable health agency has no mention of the supplement", "medium"),
    ],
    decision_prompt="Share, hold, or investigate further? Give your reasoning chain in 60 seconds.",
    decision_time_limit_s=60,
    emergency_steps=[],
    foresight_prompts=[
        "If you share and it is false, what harms follow?",
        "What would change your mind with one additional piece of evidence?",
    ],
    critical_thinking_prompts=[
        "What is the claim vs what is actually evidenced?",
        "Which cognitive biases might push you to share quickly?",
        "What is the smallest test that could falsify the claim?",
    ],
    debrief_rubric=[
        "Separated claim from evidence",
        "Named missing information",
        "Considered harm of false positives",
        "Proposed verifiable next step",
    ],
    skills=["critical-thinking", "media-literacy", "quick-decision"],
)


BUILTIN_SCENARIOS: Dict[str, ScenarioDefinition] = {
    s.scenario_id: s
    for s in (
        AVIATION_EMERGENCY_LANDING,
        MEDICAL_TRIAGE_QUICK,
        FIRE_EVACUATION,
        MEDIA_CLAIM_VERIFICATION,
    )
}


def list_scenarios() -> List[ScenarioDefinition]:
    return list(BUILTIN_SCENARIOS.values())


def get_scenario(scenario_id: str) -> Optional[ScenarioDefinition]:
    return BUILTIN_SCENARIOS.get(scenario_id)
