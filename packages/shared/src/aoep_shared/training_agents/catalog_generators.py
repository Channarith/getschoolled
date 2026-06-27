"""Programmatic scenario generators — one function per domain."""

from __future__ import annotations

from itertools import product
from typing import Dict, Iterator, List

from .models import ScenarioCue, ScenarioDefinition, ScenarioDomain


def _cue(cid: str, text: str, priority: str = "medium") -> ScenarioCue:
    return ScenarioCue(cue_id=cid, text=text, priority=priority)


def _scenario(
    scenario_id: str,
    title: str,
    domain: ScenarioDomain,
    briefing: str,
    cues: List[ScenarioCue],
    decision_prompt: str,
    *,
    decision_time_limit_s: int = 60,
    emergency_steps: List[str] | None = None,
    foresight_prompts: List[str] | None = None,
    critical_thinking_prompts: List[str] | None = None,
    debrief_rubric: List[str] | None = None,
    skills: List[str] | None = None,
) -> ScenarioDefinition:
    return ScenarioDefinition(
        scenario_id=scenario_id,
        title=title,
        domain=domain,
        briefing=briefing,
        cues=cues,
        decision_prompt=decision_prompt,
        decision_time_limit_s=decision_time_limit_s,
        emergency_steps=emergency_steps or [],
        foresight_prompts=foresight_prompts or [],
        critical_thinking_prompts=critical_thinking_prompts or [],
        debrief_rubric=debrief_rubric or [],
        skills=skills or [],
    )


def _slug(*parts: str) -> str:
    return "_".join(
        p.lower().replace(" ", "_").replace("/", "_").replace("'", "")[:40]
        for p in parts if p
    )[:80]


# --------------------------------------------------------------------------- #
# Aviation
# --------------------------------------------------------------------------- #
_AVIATION_INCIDENTS = [
    ("engine_failure", "Engine failure", "RPM drops and oil pressure falls"),
    ("partial_power", "Partial power loss", "Engine runs rough with intermittent power"),
    ("fuel_exhaustion", "Fuel exhaustion", "Fuel gauges near empty unexpectedly"),
    ("icing", "Structural icing", "Ice accumulates on wings in IMC"),
    ("bird_strike", "Bird strike", "Loud impact; vibration and possible smell"),
    ("gear_failure", "Landing gear malfunction", "Gear indicator disagrees with handle"),
    ("smoke_cockpit", "Smoke in cockpit", "Electrical smell and haze forward"),
    ("spatial_disorientation", "Spatial disorientation", "Vestibular illusion in IMC"),
    ("runway_incursion", "Runway incursion risk", "Another aircraft/taxiway conflict ahead"),
    ("wind_shear", "Wind shear on approach", "Airspeed fluctuates on final"),
]

_AVIATION_CONTEXT = [
    ("C172", "2,500", "8", "day VMC"),
    ("PA-28", "3,800", "12", "twilight"),
    ("DA-40", "5,500", "15", "night"),
    ("C152", "1,800", "5", "hazy day"),
    ("SR20", "4,200", "10", "gusty crosswind"),
]


def gen_aviation() -> Iterator[ScenarioDefinition]:
    steps = [
        "Aviate — maintain aircraft control; best glide if power lost",
        "Navigate — point toward nearest suitable landing area",
        "Communicate — squawk 7700; declare intentions",
        "Checklist — fuel, mixture, ignition as applicable",
        "Land — stabilize approach; lives over equipment",
    ]
    legacy_pinned = False
    for (code, label, symptom), (ac, alt, dist, cond) in product(_AVIATION_INCIDENTS, _AVIATION_CONTEXT):
        if not legacy_pinned and code == "engine_failure" and ac == "C172":
            sid = "aviation_emergency_landing"
            legacy_pinned = True
        else:
            sid = _slug("aviation", code, ac, alt)
        yield _scenario(
            sid,
            f"{label} — {ac} at {alt} ft ({cond})",
            ScenarioDomain.AVIATION,
            (
                f"You are PIC in a {ac} at {alt} ft MSL, {dist} nm from the nearest "
                f"airport. Conditions: {cond}. {symptom}. Train calm procedure under "
                "pressure — not memorized answers."
            ),
            [
                _cue("symptom", symptom, "critical"),
                _cue("altitude", f"{alt} ft MSL; terrain below", "medium"),
                _cue("distance", f"Nearest airport {dist} nm", "high"),
                _cue("conditions", cond, "medium"),
                _cue("fuel", "Fuel sufficient for ~30-45 min at reduced power", "medium"),
                _cue("wind", "Wind reported 10-15 kt; crosswind component likely", "medium"),
            ],
            "You have 60 seconds to commit. State your FIRST action sequence and priorities.",
            emergency_steps=steps,
            foresight_prompts=[
                "What cues would you brief before this flight?",
                "If glide range is insufficient, what options do you prepare now?",
                "What hazards remain after touchdown?",
            ],
            critical_thinking_prompts=[
                "Why aviate before troubleshoot?",
                "What assumptions are you making about runway and wind?",
                "When is off-field landing the better choice?",
            ],
            debrief_rubric=[
                "Maintained aircraft control first",
                "Selected landing area early",
                "Communicated position and intent",
                "Used checklist without fixation",
                "Anticipated post-landing hazards",
            ],
            skills=["aviation", "emergency-procedures", "critical-thinking", "situational-awareness"],
        )


# --------------------------------------------------------------------------- #
# Medical
# --------------------------------------------------------------------------- #
_MEDICAL_EVENTS = [
    ("cardiac", "Possible cardiac arrest", "Unresponsive adult, no normal breathing"),
    ("stroke", "Suspected stroke", "Facial droop, arm weakness, slurred speech"),
    ("anaphylaxis", "Anaphylaxis", "Swelling, wheeze, hives after food exposure"),
    ("hemorrhage", "Severe bleeding", "Arterial spray from limb injury"),
    ("choking", "Choking", "Clutching throat, silent cough"),
    ("overdose", "Suspected overdose", "Pinpoint pupils, slow breathing"),
    ("seizure", "Active seizure", "Generalized convulsion, post-ictal coming"),
    ("heat_stroke", "Heat stroke", "Hot dry skin, confusion, collapse"),
    ("hypothermia", "Hypothermia", "Shivering stopped; altered mental status"),
    ("child_fever", "Febrile child", "Infant lethargic with high fever"),
]

_MEDICAL_SETTINGS = [
    ("parking_lot", "outdoor parking lot"),
    ("office", "open-plan office"),
    ("gym", "fitness center"),
    ("school", "school hallway"),
    ("home", "residential kitchen"),
]


def gen_medical() -> Iterator[ScenarioDefinition]:
    steps = [
        "Scene safety — protect self and bystanders",
        "Primary survey — immediate life threats first",
        "Activate EMS — call or delegate early",
        "Intervene — CPR, pressure, Epi as trained",
        "Reassess — conditions change minute to minute",
    ]
    legacy_pinned = False
    for (code, label, presentation), (place, setting) in product(_MEDICAL_EVENTS, _MEDICAL_SETTINGS):
        if not legacy_pinned and code == "cardiac" and place == "parking_lot":
            sid = "medical_triage_quick"
            legacy_pinned = True
        else:
            sid = _slug("medical", code, place)
        yield _scenario(
            sid,
            f"{label} — {setting}",
            ScenarioDomain.MEDICAL,
            (
                f"A {presentation} occurs in a {setting}. You are first trained "
                "responder on scene. Triage and act under time pressure."
            ),
            [
                _cue("primary", presentation, "critical"),
                _cue("bystanders", "Bystanders anxious; some filming", "low"),
                _cue("scene", f"Setting: {setting}; egress paths visible", "medium"),
                _cue("second", "Additional victim with minor injuries distracting crowd", "medium"),
                _cue("help", "EMS ETA 6-8 minutes", "high"),
            ],
            "In 60 seconds: what do you do first, second, third — and why?",
            emergency_steps=steps,
            foresight_prompts=[
                "What could worsen in the next 5 minutes?",
                "What equipment or help do you wish you had en route?",
            ],
            critical_thinking_prompts=[
                "What is life threat vs visible but non-urgent?",
                "What information is missing that would change your plan?",
            ],
            debrief_rubric=[
                "Addressed scene safety",
                "Prioritized life threats",
                "Activated help early",
                "Justified order with physiology",
            ],
            skills=["medical-triage", "quick-decision", "situational-analysis"],
        )


# --------------------------------------------------------------------------- #
# Fire safety
# --------------------------------------------------------------------------- #
_FIRE_TYPES = [
    ("office_smoke", "Office smoke", "4th floor; smoke at east stair"),
    ("kitchen_grease", "Kitchen grease fire", "Commercial kitchen flare-up"),
    ("warehouse", "Warehouse storage fire", "Pallet stack smoldering"),
    ("highrise", "High-rise alarm", "Alarm on floor above; crowd at elevators"),
    ("dormitory", "Dormitory alarm", "Night; students confused in hallway"),
]

_FIRE_CONTEXT = [
    ("rain", "heavy rain outside"),
    ("crowded", "peak occupancy"),
    ("mobility", "wheelchair user on floor"),
    ("power", "partial power loss; dim emergency lighting"),
]


def gen_fire_safety() -> Iterator[ScenarioDefinition]:
    steps = [
        "Alert — pull alarm; call emergency services",
        "Assess — choose exit away from smoke; no elevators",
        "Assist — help others without blocking flow",
        "Account — assembly point headcount",
    ]
    legacy_pinned = False
    for (code, label, detail), (ctx_code, ctx_detail) in product(_FIRE_TYPES, _FIRE_CONTEXT):
        if not legacy_pinned and code == "office_smoke" and ctx_code == "rain":
            sid = "fire_evacuation"
            legacy_pinned = True
        else:
            sid = _slug("fire", code, ctx_code)
        yield _scenario(
            sid,
            f"{label} ({ctx_detail})",
            ScenarioDomain.FIRE_SAFETY,
            f"{detail}. Context: {ctx_detail}. Scan before you move.",
            [
                _cue("smoke", detail, "high"),
                _cue("crowd", "People drifting toward elevators", "medium"),
                _cue("exit", "Marked stairwell; door cool on first check", "high"),
                _cue("context", ctx_detail, "medium"),
            ],
            "First 45 seconds: your actions and how you help others?",
            decision_time_limit_s=45,
            emergency_steps=steps,
            foresight_prompts=["If primary stair blocks, what is backup?", "Stampede risk at elevators?"],
            critical_thinking_prompts=["Which cues are reliable vs alarm fatigue?"],
            debrief_rubric=["Avoided smoke/elevators", "Verified exit", "Accountability plan"],
            skills=["fire-safety", "situational-analysis"],
        )


# --------------------------------------------------------------------------- #
# Maritime
# --------------------------------------------------------------------------- #
_MARITIME_EVENTS = [
    ("man_overboard", "Man overboard", "Crew member falls astern"),
    ("fire_below", "Engine-room fire", "Smoke from machinery space"),
    ("flooding", "Hull flooding", "Water rising in compartment"),
    ("collision", "Collision risk", "Vessel closing on starboard bow"),
    ("heavy_weather", "Heavy weather", "Seas 4m; cargo shift"),
]


def gen_maritime() -> Iterator[ScenarioDefinition]:
    vessels = ["fishing trawler", "ferry", "yacht", "cargo coaster", "training sailboat"]
    for (code, label, detail), vessel in product(_MARITIME_EVENTS, vessels):
        sid = _slug("maritime", code, vessel)
        yield _scenario(
            sid,
            f"{label} — {vessel}",
            ScenarioDomain.MARITIME,
            f"At sea aboard a {vessel}. {detail}. Lead the first 60 seconds.",
            [
                _cue("event", detail, "critical"),
                _cue("crew", "Mixed experience crew; one injured possibility", "medium"),
                _cue("comms", "VHF available; mayday protocol applies", "high"),
                _cue("weather", "Wind 25 kt; visibility moderate", "medium"),
            ],
            "Captain absent 2 minutes — what orders do you give first?",
            emergency_steps=[
                "Stabilize vessel and crew safety",
                "Communicate distress/position",
                "Contain — fire/flood MOB recovery as applicable",
                "Prepare abandon-ship if threshold crossed",
            ],
            foresight_prompts=["What worsens in 10 minutes if you delay?"],
            critical_thinking_prompts=["What is reversible vs point-of-no-return?"],
            debrief_rubric=["Crew safety first", "Position communicated", "Containment attempted"],
            skills=["maritime", "emergency-procedures", "leadership"],
        )


# --------------------------------------------------------------------------- #
# Cybersecurity
# --------------------------------------------------------------------------- #
_CYBER_EVENTS = [
    ("ransomware", "Ransomware spreading", "File shares encrypting"),
    ("phishing", "CEO fraud wire", "Urgent payment email"),
    ("data_breach", "Data exfiltration", "Unusual outbound traffic"),
    ("insider", "Insider threat", "Privileged account odd hours"),
    ("ddos", "DDoS outage", "Customer site unreachable"),
]


def gen_cybersecurity() -> Iterator[ScenarioDefinition]:
    sectors = ["hospital", "school district", "retail chain", "municipality", "startup"]
    for (code, label, detail), sector in product(_CYBER_EVENTS, sectors):
        sid = _slug("cyber", code, sector)
        yield _scenario(
            sid,
            f"{label} — {sector}",
            ScenarioDomain.CYBERSECURITY,
            f"{sector.title()} IR team: {detail}. You have 60 seconds to set initial response.",
            [
                _cue("indicator", detail, "critical"),
                _cue("scope", "Unknown number of hosts affected", "high"),
                _cue("backup", "Backups last ran 18h ago", "medium"),
                _cue("comms", "PR asking for statement in 30 min", "medium"),
            ],
            "First containment and communication moves?",
            emergency_steps=[
                "Identify and isolate affected systems",
                "Preserve evidence — avoid destructive cleanup",
                "Escalate to leadership and legal",
                "Communicate facts only — no speculation",
            ],
            foresight_prompts=["What spreads if you wait 15 minutes?"],
            critical_thinking_prompts=["What must you verify before shutdown?"],
            debrief_rubric=["Isolated spread", "Evidence preserved", "Stakeholders notified"],
            skills=["cybersecurity", "incident-response", "critical-thinking"],
        )


# --------------------------------------------------------------------------- #
# Industrial
# --------------------------------------------------------------------------- #
_INDUSTRIAL_EVENTS = [
    ("chemical_spill", "Chemical spill", "Solvent leak near spark source"),
    ("lockout", "Lockout failure", "Machine energizes during maintenance"),
    ("conveyor", "Conveyor entrapment", "Worker caught at pinch point"),
    ("gas_leak", "Gas leak", "H2S alarm intermittent"),
    ("crane", "Crane load swing", "Load shifts over occupied area"),
]


def gen_industrial() -> Iterator[ScenarioDefinition]:
    plants = ["refinery unit", "food plant", "automotive line", "warehouse DC", "pharma cleanroom"]
    for (code, label, detail), plant in product(_INDUSTRIAL_EVENTS, plants):
        sid = _slug("industrial", code, plant)
        yield _scenario(
            sid,
            f"{label} — {plant}",
            ScenarioDomain.INDUSTRIAL,
            f"{plant.title()}: {detail}. Supervisor unreachable. Act in 60 seconds.",
            [
                _cue("hazard", detail, "critical"),
                _cue("ppe", "PPE station 20m away", "medium"),
                _cue("evac", "Muster point upwind", "high"),
                _cue("permits", "Hot work permit active nearby", "medium"),
            ],
            "Immediate actions to protect people?",
            emergency_steps=[
                "Stop work — activate alarm if needed",
                "Isolate energy/source if trained",
                "Evacuate non-essential personnel",
                "Account at muster; brief incoming responders",
            ],
            foresight_prompts=["Secondary ignition/exposure risk?"],
            critical_thinking_prompts=["When is heroic entry wrong?"],
            debrief_rubric=["People protected", "Source isolated", "Headcount complete"],
            skills=["industrial-safety", "hazard-control"],
        )


# --------------------------------------------------------------------------- #
# Transport
# --------------------------------------------------------------------------- #
_TRANSPORT_EVENTS = [
    ("hydroplane", "Hydroplaning", "Heavy rain; loss of steering"),
    ("pedestrian", "Pedestrian conflict", "Child enters crosswalk"),
    ("tire_blowout", "Tire blowout", "Front tire at highway speed"),
    ("bus_medical", "Bus passenger collapse", "Rider unresponsive"),
    ("rail_trespass", "Rail trespass", "Person on tracks ahead"),
]


def gen_transport() -> Iterator[ScenarioDefinition]:
    modes = ["city bus", "delivery van", "commuter train cab", "rideshare sedan", "school bus"]
    for (code, label, detail), mode in product(_TRANSPORT_EVENTS, modes):
        sid = _slug("transport", code, mode)
        yield _scenario(
            sid,
            f"{label} — {mode}",
            ScenarioDomain.TRANSPORT,
            f"Operating a {mode}. {detail}. Decide in the moment.",
            [
                _cue("event", detail, "critical"),
                _cue("traffic", "Surrounding traffic dense", "medium"),
                _cue("passengers", "Passengers present and alarmed", "medium"),
            ],
            "What do you do in the next 30-60 seconds?",
            emergency_steps=[
                "Control vehicle — brake/steer smoothly",
                "Warn occupants and surrounding traffic",
                "Stop safely; secure scene",
                "Call emergency services",
            ],
            foresight_prompts=["What if you brake too hard?"],
            critical_thinking_prompts=["Tradeoffs between speed and safety?"],
            debrief_rubric=["Maintained control", "Minimized harm", "Secured scene"],
            skills=["transport-safety", "quick-decision"],
        )


# --------------------------------------------------------------------------- #
# Weather / natural disasters
# --------------------------------------------------------------------------- #
_WEATHER_EVENTS = [
    ("tornado", "Tornado warning", "Funnel reported 3 miles west"),
    ("flash_flood", "Flash flood", "Water rising on road"),
    ("earthquake", "Earthquake", "Strong shaking; fixtures falling"),
    ("wildfire", "Wildfire approach", "Smoke column; embers falling"),
    ("blizzard", "Blizzard whiteout", "Visibility near zero; stranded"),
]


def gen_weather() -> Iterator[ScenarioDefinition]:
    locales = ["suburban neighborhood", "rural highway", "campus", "retail strip", "coastal town"]
    for (code, label, detail), locale in product(_WEATHER_EVENTS, locales):
        sid = _slug("weather", code, locale)
        yield _scenario(
            sid,
            f"{label} — {locale}",
            ScenarioDomain.WEATHER,
            f"{locale.title()}: {detail}. Lead others if needed.",
            [
                _cue("threat", detail, "critical"),
                _cue("shelter", "Sturdy structure within 200m", "high"),
                _cue("crowd", "Civilians unsure where to go", "medium"),
            ],
            "Where do you go and what do you tell others?",
            emergency_steps=[
                "Seek appropriate shelter immediately",
                "Communicate clear instructions",
                "Account for group members",
                "Stay put until official all-clear",
            ],
            foresight_prompts=["What if shelter is occupied/over capacity?"],
            critical_thinking_prompts=["Which myths are dangerous here?"],
            debrief_rubric=["Shelter choice sound", "Clear communication", "Group accounted"],
            skills=["weather-safety", "situational-analysis"],
        )


# --------------------------------------------------------------------------- #
# Security
# --------------------------------------------------------------------------- #
_SECURITY_EVENTS = [
    ("active_threat", "Active threat", "Reports of armed individual"),
    ("bomb_threat", "Bomb threat", "Anonymous call; bag unattended"),
    ("protest", "Protest escalation", "Crowd blocking egress"),
    ("tailgating", "Tailgating breach", "Unknown person through secure door"),
    ("hostage", "Hostage hint", "Shouts from secured room"),
]


def gen_security() -> Iterator[ScenarioDefinition]:
    sites = ["office tower", "stadium gate", "hospital ER", "school", "transit hub"]
    for (code, label, detail), site in product(_SECURITY_EVENTS, sites):
        sid = _slug("security", code, site)
        yield _scenario(
            sid,
            f"{label} — {site}",
            ScenarioDomain.SECURITY,
            f"{site.title()}: {detail}. Follow run-hide-fight principles.",
            [
                _cue("threat", detail, "critical"),
                _cue("exits", "Two exits; one may be compromised", "high"),
                _cue("comms", "911/ security dispatch available", "medium"),
            ],
            "First 60 seconds: run, hide, or fight — justify.",
            emergency_steps=[
                "Run — evacuate if safe path exists",
                "Hide — barricade; silence phones",
                "Fight — only as last resort",
                "Communicate location when safe",
            ],
            foresight_prompts=["How do you know threat location?"],
            critical_thinking_prompts=["When is evacuation wrong?"],
            debrief_rubric=["Chose defensible action", "Communicated when safe"],
            skills=["security", "crisis-response"],
        )


# --------------------------------------------------------------------------- #
# Leadership / crisis management
# --------------------------------------------------------------------------- #
_LEADERSHIP_CRISES = [
    ("product_recall", "Product recall", "Safety defect discovered"),
    ("strike", "Labor strike", "Walkout during peak season"),
    ("pr_crisis", "PR crisis", "Executive misconduct trending"),
    ("outage", "Service outage", "Core platform down 2 hours"),
    ("merger", "Merger shock", "Layoff rumors spreading"),
]


def gen_leadership() -> Iterator[ScenarioDefinition]:
    orgs = ["tech company", "nonprofit", "hospital admin", "franchise HQ", "government agency"]
    for (code, label, detail), org in product(_LEADERSHIP_CRISES, orgs):
        sid = _slug("leadership", code, org)
        yield _scenario(
            sid,
            f"{label} — {org}",
            ScenarioDomain.LEADERSHIP,
            f"You lead a {org}. {detail}. Board wants a plan in one hour.",
            [
                _cue("crisis", detail, "critical"),
                _cue("stakeholders", "Employees/customers anxious", "high"),
                _cue("facts", "Incomplete information", "medium"),
            ],
            "What do you communicate in the first 15 minutes?",
            foresight_prompts=["What rumor fills the vacuum if you stay silent?"],
            critical_thinking_prompts=["What is fact vs speculation to share?"],
            debrief_rubric=["Transparent facts", "Clear next step", "Assigned owners"],
            skills=["leadership", "crisis-communication"],
        )


# --------------------------------------------------------------------------- #
# Education
# --------------------------------------------------------------------------- #
_EDU_EVENTS = [
    ("lockdown", "Lockdown", "Possible threat in building"),
    ("medical_student", "Student medical", "Student collapses in class"),
    ("fight", "Fight escalation", "Altercation spilling into hallway"),
    ("weather_dismissal", "Weather dismissal", "Tornado watch during pickup"),
    ("online_harassment", "Online harassment", "Live class disrupted"),
]


def gen_education() -> Iterator[ScenarioDefinition]:
    levels = ["elementary", "middle school", "high school", "university lecture", "training lab"]
    for (code, label, detail), level in product(_EDU_EVENTS, levels):
        sid = _slug("education", code, level)
        yield _scenario(
            sid,
            f"{label} — {level}",
            ScenarioDomain.EDUCATION,
            f"{level.title()}: {detail}. You are the adult in charge.",
            [
                _cue("event", detail, "critical"),
                _cue("students", "20-30 students present", "high"),
                _cue("protocol", "District protocol posted but vague", "medium"),
            ],
            "First actions in 60 seconds?",
            emergency_steps=[
                "Follow lockdown/medical protocol",
                "Account for all students",
                "Contact admin/emergency services",
                "Keep calm authoritative tone",
            ],
            debrief_rubric=["Student safety first", "Protocol followed", "Accurate headcount"],
            skills=["education-safety", "classroom-management"],
        )


# --------------------------------------------------------------------------- #
# Hospitality
# --------------------------------------------------------------------------- #
def gen_hospitality() -> Iterator[ScenarioDefinition]:
    events = [
        ("kitchen_fire", "Kitchen fire", "Grease fire during dinner rush"),
        ("guest_medical", "Guest medical", "Patron chest pain in dining room"),
        ("elevator", "Elevator entrapment", "Guests stuck between floors"),
        ("food_allergy", "Severe allergy", "Anaphylaxis after meal"),
        ("overbooking", "Overbooking riot", "Angry guests at front desk"),
    ]
    venues = ["hotel", "restaurant", "resort", "conference center", "cruise ship cabin deck"]
    for (code, label, detail), venue in product(events, venues):
        sid = _slug("hospitality", code, venue)
        yield _scenario(
            sid,
            f"{label} — {venue}",
            ScenarioDomain.HOSPITALITY,
            f"{venue.title()}: {detail}. Manager unavailable.",
            [_cue("event", detail, "critical"), _cue("guests", "Public area crowded", "medium")],
            "Priority actions in 60 seconds?",
            skills=["hospitality", "guest-safety"],
            debrief_rubric=["Guest safety", "Staff directed", "Services notified"],
        )


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #
def gen_construction() -> Iterator[ScenarioDefinition]:
    events = [
        ("trench", "Trench collapse", "Worker buried to waist"),
        ("scaffold", "Scaffold failure", "Plank slips; worker dangling"),
        ("electrical", "Electrical contact", "Worker frozen to live conductor"),
        ("fall", "Fall from height", "Worker fallen two stories"),
        ("collapse", "Partial collapse", "Formwork giving way"),
    ]
    sites = ["high-rise", "highway bridge", "residential", "industrial pad", "tunnel"]
    for (code, label, detail), site in product(events, sites):
        sid = _slug("construction", code, site)
        yield _scenario(
            sid,
            f"{label} — {site} site",
            ScenarioDomain.CONSTRUCTION,
            f"{site.title()} construction: {detail}.",
            [_cue("injury", detail, "critical"), _cue("rescue", "Do not become second victim", "high")],
            "First 60 seconds on site?",
            emergency_steps=["Stop work", "Secure area", "Call 911", "Rescue only if trained"],
            skills=["construction-safety"],
            debrief_rubric=["Scene secured", "No secondary victims", "EMS activated"],
        )


# --------------------------------------------------------------------------- #
# Agriculture
# --------------------------------------------------------------------------- #
def gen_agriculture() -> Iterator[ScenarioDefinition]:
    events = [
        ("pto", "PTO entanglement", "Loose clothing near PTO shaft"),
        ("grain_bin", "Grain bin engulfment", "Worker sinking in grain"),
        ("chemical", "Pesticide exposure", "Drift during windy application"),
        ("heat", "Heat illness", "Harvester operator confused"),
        ("animal", "Livestock charge", "Bull in pen with injured handler"),
    ]
    farms = ["dairy", "row-crop", "orchard", "cattle ranch", "poultry"]
    for (code, label, detail), farm in product(events, farms):
        sid = _slug("agriculture", code, farm)
        yield _scenario(
            sid,
            f"{label} — {farm} farm",
            ScenarioDomain.AGRICULTURE,
            f"{farm.title()} operation: {detail}.",
            [_cue("hazard", detail, "critical")],
            "Immediate actions?",
            skills=["agriculture-safety"],
            debrief_rubric=["Power isolated if applicable", "EMS called", "Scene safe"],
        )


# --------------------------------------------------------------------------- #
# Tactical / first responder
# --------------------------------------------------------------------------- #
def gen_tactical() -> Iterator[ScenarioDefinition]:
    events = [
        ("room_clear", "Room clearing", "Unknown occupancy; door ajar"),
        ("ied", "Suspected IED", "Odd package at checkpoint"),
        ("down_officer", "Officer down", "Partner hit; threat direction unclear"),
        ("crowd_control", "Crowd surge", "Barrier failing at event"),
        ("hostage_negotiation", "Hostage call", "Caller claims explosives"),
    ]
    roles = ["patrol", "campus security", "corrections", "search team", "event detail"]
    for (code, label, detail), role in product(events, roles):
        sid = _slug("tactical", code, role)
        yield _scenario(
            sid,
            f"{label} — {role}",
            ScenarioDomain.TACTICAL,
            f"{role.title()} context: {detail}.",
            [_cue("threat", detail, "critical")],
            "Tactical priorities in 60 seconds?",
            skills=["tactical", "force-protection"],
            debrief_rubric=["Threat assessed", "Communicated", "Minimized exposure"],
        )


# --------------------------------------------------------------------------- #
# Finance / fraud
# --------------------------------------------------------------------------- #
def gen_finance() -> Iterator[ScenarioDefinition]:
    events = [
        ("wire_fraud", "Wire fraud", "Vendor bank details changed"),
        ("insider_trading", "Insider tip", "Material nonpublic information"),
        ("run_bank", "Bank run rumor", "Social media panic"),
        ("audit_finding", "Audit finding", "Major control failure"),
        ("crypto_scam", "Crypto scam", "Client pressured to transfer"),
    ]
    contexts = ["retail bank", "brokerage", "credit union", "fintech app", "family office"]
    for (code, label, detail), ctx in product(events, contexts):
        sid = _slug("finance", code, ctx)
        yield _scenario(
            sid,
            f"{label} — {ctx}",
            ScenarioDomain.FINANCE,
            f"{ctx.title()}: {detail}. Decision in minutes.",
            [_cue("risk", detail, "critical")],
            "Hold, verify, or escalate?",
            skills=["finance", "fraud-prevention", "critical-thinking"],
            debrief_rubric=["Verified identity", "Escalated appropriately", "Documented"],
        )


# --------------------------------------------------------------------------- #
# Media literacy
# --------------------------------------------------------------------------- #
def gen_media_literacy() -> Iterator[ScenarioDefinition]:
    claims = [
        ("health_cure", "Miracle cure post", "Supplement cures chronic illness"),
        ("election", "Election fraud meme", "Miscaptioned video viral"),
        ("disaster", "Disaster footage", "Old clip reposted as current"),
        ("science", "Anti-vax study", "Predatory journal citation"),
        ("finance_tip", "Guaranteed returns", "Influencer pump scheme"),
    ]
    audiences = ["workplace chat", "classroom", "family group", "newsroom", "community page"]
    legacy_pinned = False
    for (code, label, detail), aud in product(claims, audiences):
        if not legacy_pinned and code == "health_cure" and aud == "workplace chat":
            sid = "media_claim_verification"
            legacy_pinned = True
        else:
            sid = _slug("media", code, aud)
        yield _scenario(
            sid,
            f"{label} — {aud}",
            ScenarioDomain.MEDIA_LITERACY,
            f"{aud.title()}: viral {detail}. Share, hold, or investigate?",
            [
                _cue("claim", detail, "critical"),
                _cue("source", "Anonymous or unverified source", "high"),
            ],
            "Decision and reasoning in 60 seconds?",
            skills=["media-literacy", "critical-thinking"],
            debrief_rubric=["Separated claim from evidence", "Named verification step"],
        )


# --------------------------------------------------------------------------- #
# Child safety
# --------------------------------------------------------------------------- #
def gen_child_safety() -> Iterator[ScenarioDefinition]:
    events = [
        ("pool", "Pool incident", "Child missing near pool"),
        ("stranger", "Stranger approach", "Adult asking child to leave"),
        ("choking_child", "Child choking", "Toddler silent distress"),
        ("hot_car", "Hot car", "Child left in vehicle"),
        ("online_predator", "Online grooming", "Secret chat with unknown adult"),
    ]
    places = ["playground", "mall", "home", "school pickup", "park"]
    for (code, label, detail), place in product(events, places):
        sid = _slug("child", code, place)
        yield _scenario(
            sid,
            f"{label} — {place}",
            ScenarioDomain.CHILD_SAFETY,
            f"{place.title()}: {detail}.",
            [_cue("child", detail, "critical")],
            "First 60 seconds?",
            skills=["child-safety", "quick-decision"],
            debrief_rubric=["Child located/safe", "Authorities notified if needed"],
        )


# --------------------------------------------------------------------------- #
# Mental health / de-escalation
# --------------------------------------------------------------------------- #
def gen_mental_health() -> Iterator[ScenarioDefinition]:
    events = [
        ("suicidal", "Suicidal ideation", "Person states intent near ledge"),
        ("psychosis", "Psychotic episode", "Bystander hearing commands"),
        ("aggressive", "Aggressive patron", "Yelling; throwing objects"),
        ("panic", "Panic attack", "Hyperventilating in crowd"),
        ("substance", "Substance crisis", "Confused person in traffic"),
    ]
    settings = ["bridge", "clinic waiting room", "retail store", "transit platform", "residence"]
    for (code, label, detail), setting in product(events, settings):
        sid = _slug("mental", code, setting)
        yield _scenario(
            sid,
            f"{label} — {setting}",
            ScenarioDomain.MENTAL_HEALTH,
            f"{setting.title()}: {detail}. De-escalate safely.",
            [_cue("person", detail, "critical"), _cue("safety", "Your exit path clear", "high")],
            "De-escalation approach in 60 seconds?",
            skills=["mental-health", "de-escalation"],
            debrief_rubric=["Safety maintained", "Empathy used", "Professional help engaged"],
        )


# --------------------------------------------------------------------------- #
# Sports / coaching
# --------------------------------------------------------------------------- #
def gen_sports() -> Iterator[ScenarioDefinition]:
    events = [
        ("concussion", "Suspected concussion", "Player slow to rise"),
        ("heat_athlete", "Heat exhaustion", "Athlete cramping, confused"),
        ("lightning", "Lightning risk", "Storm approaching field"),
        ("spinal", "Spinal precaution", "Awkward fall; neck pain"),
        ("fan_medical", "Spectator medical", "Fan collapses in stands"),
    ]
    sports = ["soccer", "football", "basketball", "swim meet", "track meet"]
    for (code, label, detail), sport in product(events, sports):
        sid = _slug("sports", code, sport)
        yield _scenario(
            sid,
            f"{label} — {sport}",
            ScenarioDomain.SPORTS,
            f"{sport.title()}: {detail}. Coach/ref must act.",
            [_cue("athlete", detail, "critical")],
            "Immediate sideline decisions?",
            skills=["sports-safety", "first-aid"],
            debrief_rubric=["Play stopped appropriately", "Medical eval arranged"],
        )


# --------------------------------------------------------------------------- #
# General / cross-domain soft skills
# --------------------------------------------------------------------------- #
def gen_general() -> Iterator[ScenarioDefinition]:
  pairs = [
      ("ambiguous_email", "Ambiguous urgent email", "CEO asks for gift cards"),
      ("elevator_pitch", "Elevator stuck", "Stranger panicking"),
      ("lost_child", "Lost child in store", "Child crying alone"),
      ("power_outage", "Power outage", "Dark stairwell evacuation"),
      ("water_main", "Water main break", "Flooding basement"),
  ]
  contexts = ["airport", "library", "museum", "apartment", "campground"]
  for (code, label, detail), ctx in product(pairs, contexts):
      sid = _slug("general", code, ctx)
      yield _scenario(
          sid,
          f"{label} — {ctx}",
          ScenarioDomain.GENERAL,
          f"{ctx.title()}: {detail}.",
          [_cue("situation", detail, "high")],
          "What do you do first?",
          skills=["critical-thinking", "situational-analysis"],
          debrief_rubric=["Assessed safety", "Took verifiable action"],
      )


ALL_GENERATORS = [
    gen_aviation,
    gen_medical,
    gen_fire_safety,
    gen_maritime,
    gen_cybersecurity,
    gen_industrial,
    gen_transport,
    gen_weather,
    gen_security,
    gen_leadership,
    gen_education,
    gen_hospitality,
    gen_construction,
    gen_agriculture,
    gen_tactical,
    gen_finance,
    gen_media_literacy,
    gen_child_safety,
    gen_mental_health,
    gen_sports,
    gen_general,
]


def generate_all_scenarios() -> List[ScenarioDefinition]:
    from .catalog_generators_extended import EXTENDED_GENERATORS
    from .procedural import materialize_samples

    seen: Dict[str, ScenarioDefinition] = {}
    for gen in ALL_GENERATORS + EXTENDED_GENERATORS:
        for scenario in gen():
            if scenario.scenario_id in seen:
                continue
            seen[scenario.scenario_id] = scenario
    for scenario in materialize_samples():
        if scenario.scenario_id in seen:
            continue
        seen[scenario.scenario_id] = scenario
    return list(seen.values())
