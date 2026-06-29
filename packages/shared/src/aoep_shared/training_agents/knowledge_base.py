"""Real, authoritative safety knowledge base.

Every entry is a real, citable fact, procedure, regulation, or published
statistic from a recognized authority (FAA, NHTSA, FMCSA, FRA, USCG, IMO/COLREGs,
AHA, NFPA, DHS/CISA, PHMSA, NWS, CDC, etc.). Scenarios are grounded in this base
so each drill references genuine guidance rather than invented content.

This is the seed corpus; the harvester can append more vetted entries over time.
All facts here reflect well-established public safety guidance; the ``source`` and
``reference`` fields attribute each to its issuing authority/document.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import ReferenceFact


def _kf(
    fact: str,
    source: str,
    reference: str,
    category: str,
    *,
    domains: tuple,
    keywords: tuple = (),
) -> dict:
    return {
        "fact": fact,
        "source": source,
        "reference": reference,
        "category": category,
        "domains": domains,
        "keywords": keywords,
    }


# --------------------------------------------------------------------------- #
# The corpus (real authoritative safety knowledge)
# --------------------------------------------------------------------------- #
_RAW: List[dict] = [
    # ---------------- Aviation ----------------
    _kf("The pilot in command is directly responsible for, and is the final authority "
        "as to, the operation of the aircraft, and may deviate from rules in an in-flight "
        "emergency to the extent required to meet it.",
        "FAA", "14 CFR 91.3", "regulation",
        domains=("aviation", "aviation_ifr"), keywords=("emergency", "pic", "authority")),
    _kf("Set the transponder to 7700 for a general emergency, 7600 for lost communications, "
        "and 7500 for unlawful interference (hijack).",
        "FAA", "AIM 6-2-2 / 4-1-20", "procedure",
        domains=("aviation", "aviation_ifr"), keywords=("transponder", "squawk", "comm", "radio")),
    _kf("Manage emergencies in priority order: Aviate, Navigate, Communicate.",
        "FAA", "Airplane Flying Handbook FAA-H-8083-3", "procedure",
        domains=("aviation", "aviation_ifr"), keywords=("engine", "control", "emergency")),
    _kf("On engine failure, immediately establish best glide speed and select a suitable "
        "landing area before troubleshooting.",
        "FAA", "Airplane Flying Handbook FAA-H-8083-3 (Ch. 18)", "procedure",
        domains=("aviation", "aviation_ifr"), keywords=("engine", "glide", "landing", "power")),
    _kf("Spatial disorientation is a leading cause of fatal general-aviation accidents when "
        "VFR pilots enter instrument conditions; trust the instruments, not bodily sensations.",
        "FAA", "AIM 8-1-5", "guideline",
        domains=("aviation", "aviation_ifr"), keywords=("imc", "disorient", "instrument", "icing")),
    _kf("Apply carburetor heat at the first sign of carburetor icing (unexplained RPM/MP loss "
        "in susceptible conditions).",
        "FAA", "Airplane Flying Handbook FAA-H-8083-3", "procedure",
        domains=("aviation", "aviation_ifr"), keywords=("carb", "ice", "rpm")),
    _kf("Use 'MAYDAY' (spoken three times) for distress and 'PAN-PAN' for urgency on the "
        "radio when declaring an emergency.",
        "ICAO / FAA", "AIM 6-3-1", "procedure",
        domains=("aviation", "aviation_ifr"), keywords=("declare", "mayday", "distress")),

    # ---------------- Road (general driving) ----------------
    _kf("Maintain at least a 3-second following distance, and increase it in rain, fog, or at "
        "night.",
        "NHTSA", "Defensive Driving guidance", "guideline",
        domains=("road", "transport"), keywords=("following", "tailgate", "distance", "rain", "fog")),
    _kf("Seat belts reduce the risk of fatal injury to front-seat car occupants by about 45% "
        "(and by about 60% in light trucks).",
        "NHTSA", "Occupant Protection facts", "statistic",
        domains=("road", "transport"), keywords=("seat belt", "occupant", "child")),
    _kf("In a skid, ease off the accelerator and look and steer in the direction you want the "
        "vehicle to go; do not slam the brakes.",
        "NHTSA", "Winter Driving guidance", "procedure",
        domains=("road", "transport"), keywords=("skid", "ice", "snow", "slippery")),
    _kf("During a tire blowout, hold the wheel firmly, keep the vehicle straight, ease off the "
        "accelerator, and slow gradually — do not brake hard.",
        "NHTSA", "TireWise", "procedure",
        domains=("road", "transport"), keywords=("tire", "blowout")),
    _kf("If hydroplaning, ease off the accelerator, keep the wheel steady, and avoid hard "
        "braking until the tires regain contact.",
        "NHTSA / FHWA", "Wet Weather Driving", "procedure",
        domains=("road", "transport"), keywords=("hydroplane", "water", "rain", "flood")),
    _kf("Sending or reading a text at 55 mph takes your eyes off the road long enough to cover "
        "the length of a football field.",
        "NHTSA", "Distracted Driving", "statistic",
        domains=("road", "transport"), keywords=("phone", "distraction", "text", "gps")),
    _kf("Move Over laws require drivers to slow down and, when safe, change lanes away from "
        "stopped emergency and service vehicles.",
        "AAMVA", "Move Over law summary", "regulation",
        domains=("road", "transport", "police"), keywords=("stopped", "emergency vehicle", "move over")),
    _kf("Never stop on railroad tracks. If your vehicle stalls on a crossing, get everyone out "
        "and away immediately, then call the emergency number posted at the crossing or 911.",
        "FRA / Operation Lifesaver", "Highway-Rail Crossing Safety", "procedure",
        domains=("road", "rail", "transport"), keywords=("crossing", "track", "stall", "train")),

    _kf("If your brakes fail, pump the pedal to try to build pressure, downshift to a lower "
        "gear, and apply the parking brake gradually while steering to a safe runoff.",
        "NHTSA", "Driver education guidance", "procedure",
        domains=("road",), keywords=("brake", "fail", "soft", "pedal")),
    _kf("For a vehicle engine fire, pull over, turn off the engine, get everyone out and well "
        "away, and call 911 — do not open the hood into the flames.",
        "U.S. Fire Administration / NFPA", "Vehicle Fire Safety", "procedure",
        domains=("road",), keywords=("fire", "engine", "smoke", "hood")),
    _kf("Never drive into floodwater of unknown depth; turn around — water can hide washed-out "
        "road and sweep a vehicle away.",
        "NWS / FHWA", "Flood driving safety", "guideline",
        domains=("road",), keywords=("flood", "water", "road")),
    # ---------------- Motorcycle ----------------
    _kf("Use the SEE strategy — Search, Evaluate, Execute — to manage risk while riding.",
        "Motorcycle Safety Foundation", "MSF Rider Course", "procedure",
        domains=("road",), keywords=("motorcycle", "rider", "see")),
    _kf("At speed, counter-steer: press forward on the handgrip in the direction you want to "
        "turn or swerve.",
        "Motorcycle Safety Foundation", "MSF Rider Course", "procedure",
        domains=("road",), keywords=("counter-steer", "corner", "swerve", "gravel")),
    _kf("A common car/motorcycle collision is an oncoming vehicle turning left across the "
        "rider's path; anticipate it at intersections.",
        "NHTSA", "Motorcycle Safety facts", "statistic",
        domains=("road",), keywords=("left", "turn", "car", "intersection")),
    _kf("DOT-compliant helmets are estimated to be about 37% effective in preventing fatal "
        "injuries to motorcycle riders.",
        "NHTSA", "Motorcycle Helmet Use", "statistic",
        domains=("road",), keywords=("helmet",)),

    # ---------------- Commercial truck ----------------
    _kf("A fully loaded tractor-trailer at 65 mph can need roughly 525+ feet to stop — far more "
        "than a passenger car; brake early.",
        "FMCSA", "CDL Manual / Large Truck stopping", "statistic",
        domains=("road",), keywords=("truck", "stop", "brake", "semi")),
    _kf("On long downgrades use a lower gear and engine/auxiliary brakes to avoid brake fade "
        "from overheating.",
        "FMCSA", "CDL Manual (Mountain Driving)", "procedure",
        domains=("road",), keywords=("grade", "downhill", "fade", "brake")),
    _kf("Avoid hard braking in a turn; abrupt braking can cause the trailer to swing and "
        "jackknife.",
        "FMCSA", "CDL Manual (Skid Control)", "procedure",
        domains=("road",), keywords=("jackknife", "trailer", "skid")),

    # ---------------- Rail ----------------
    _kf("A freight train traveling at typical speeds can take a mile or more to stop, even in "
        "an emergency.",
        "Operation Lifesaver / FRA", "Rail Safety Education", "statistic",
        domains=("rail",), keywords=("train", "stop", "brake")),
    _kf("Trains always have the right of way; never drive or walk around lowered crossing gates.",
        "Operation Lifesaver", "Grade Crossing Safety", "guideline",
        domains=("rail", "road", "pedestrian"), keywords=("crossing", "gate", "track")),
    _kf("Blue signal protection: workers on, under, or between rolling equipment are protected "
        "by blue signals that only they may remove.",
        "FRA", "49 CFR 218 Subpart B", "regulation",
        domains=("rail",), keywords=("worker", "equipment", "blue", "yard")),
    _kf("On station platforms, stay behind the tactile/yellow edge line until the train stops "
        "and doors open.",
        "Transit safety standard", "Platform edge safety", "guideline",
        domains=("rail",), keywords=("platform", "edge", "station")),

    # ---------------- Bicycle ----------------
    _kf("Ride in the same direction as traffic; bicyclists fare best when they act as, and are "
        "treated as, drivers of vehicles.",
        "League of American Bicyclists / Uniform Vehicle Code", "Smart Cycling", "guideline",
        domains=("micromobility",), keywords=("bike", "traffic", "lane", "direction")),
    _kf("Use a white front light and a red rear light/reflector when riding at night, as "
        "required by law in most states.",
        "NHTSA / CPSC", "Bicycle Safety", "regulation",
        domains=("micromobility",), keywords=("night", "light", "dark", "visibility")),
    _kf("Wearing a bicycle helmet substantially reduces the risk of head and brain injury in a "
        "crash.",
        "CDC", "Bicycle Safety", "statistic",
        domains=("micromobility",), keywords=("helmet", "head")),
    _kf("Avoid the 'door zone' — ride about a door's width away from parked cars to avoid being "
        "struck by an opening door.",
        "League of American Bicyclists", "Smart Cycling", "guideline",
        domains=("micromobility",), keywords=("door", "parked", "dooring")),

    # ---------------- Scooter / micromobility ----------------
    _kf("Ride an e-scooter solo (one rider) and wear a helmet; doubling up degrades balance and "
        "braking.",
        "CPSC", "Micromobility safety", "guideline",
        domains=("micromobility",), keywords=("scooter", "helmet", "two", "rider")),
    _kf("Small scooter wheels are easily upset by potholes, curbs, and tram grooves — slow down "
        "and cross hazards at a square angle.",
        "CPSC", "Micromobility safety", "guideline",
        domains=("micromobility",), keywords=("pothole", "curb", "tram", "groove")),

    # ---------------- Marine / water ----------------
    _kf("COLREGs Rule 5: every vessel shall at all times maintain a proper lookout by sight and "
        "hearing.",
        "IMO / USCG", "COLREGs Rule 5", "regulation",
        domains=("marine", "maritime"), keywords=("lookout", "collision", "watch")),
    _kf("COLREGs Rule 6: every vessel shall proceed at a safe speed appropriate to conditions.",
        "IMO / USCG", "COLREGs Rule 6", "regulation",
        domains=("marine", "maritime"), keywords=("speed", "collision")),
    _kf("COLREGs Rule 7: use all available means to determine if risk of collision exists; if in "
        "doubt, assume it does.",
        "IMO / USCG", "COLREGs Rule 7", "regulation",
        domains=("marine", "maritime"), keywords=("collision", "risk")),
    _kf("Most boating-fatality drowning victims were not wearing a life jacket; wear a properly "
        "fitted PFD.",
        "USCG", "Recreational Boating Statistics", "statistic",
        domains=("marine", "water_safety", "maritime"), keywords=("life jacket", "pfd", "overboard", "drown")),
    _kf("Cold-water immersion triggers an involuntary gasp and rapid loss of function; expect "
        "cold-shock and protect the airway.",
        "USCG / National Center for Cold Water Safety", "Cold Water Safety", "guideline",
        domains=("marine", "water_safety"), keywords=("cold", "hypothermia", "immersion", "capsize")),
    _kf("Man overboard: assign a dedicated spotter to point continuously, throw flotation, and "
        "maneuver back to the person.",
        "US Sailing / USCG", "MOB procedure", "procedure",
        domains=("marine", "water_safety", "maritime"), keywords=("overboard", "mob", "person")),
    _kf("Caught in a rip current, don't fight it — swim parallel to shore to escape, then angle "
        "back in.",
        "NOAA / USLA", "Rip Current Safety", "procedure",
        domains=("water_safety", "marine"), keywords=("rip", "current", "swim", "beach")),

    # ---------------- Pedestrian ----------------
    _kf("Cross at marked crosswalks or intersections, and make eye contact with drivers before "
        "stepping out.",
        "NHTSA", "Pedestrian Safety", "guideline",
        domains=("pedestrian",), keywords=("crosswalk", "cross", "driver")),
    _kf("The large majority of pedestrian fatalities occur after dark; increase caution and "
        "visibility at night.",
        "NHTSA / IIHS", "Pedestrian fatality data", "statistic",
        domains=("pedestrian",), keywords=("night", "dark", "visibility")),
    _kf("Be visible at night: wear light-colored or reflective clothing and carry a light.",
        "NHTSA", "Pedestrian Safety", "guideline",
        domains=("pedestrian",), keywords=("visible", "reflective", "night")),
    _kf("Watch for turning and reversing vehicles, especially quiet electric/hybrid cars that "
        "are hard to hear.",
        "NHTSA", "Pedestrian Safety / Quiet Vehicles", "guideline",
        domains=("pedestrian",), keywords=("turning", "ev", "backing", "silent")),

    # ---------------- Police / public safety ----------------
    _kf("De-escalation uses time, distance, and cover to create options and slow a situation "
        "whenever feasible.",
        "PERF / IACP", "ICAT De-escalation Training", "guideline",
        domains=("police", "security", "conflict"), keywords=("de-escalate", "distance", "crisis")),
    _kf("For behavioral-health crises, Crisis Intervention Team (CIT) approaches emphasize "
        "communication and connecting the person to care.",
        "CIT International / IACP", "Crisis Intervention Team model", "guideline",
        domains=("police", "mental_health"), keywords=("mental", "crisis", "cit", "psych")),
    _kf("Use of force by police must be 'objectively reasonable' under the totality of the "
        "circumstances.",
        "U.S. Supreme Court", "Graham v. Connor (1989)", "regulation",
        domains=("police",), keywords=("force", "reasonable")),
    _kf("Active listening and rapport-building are core to crisis negotiation and gaining "
        "voluntary compliance.",
        "FBI / IACP", "Crisis Negotiation", "guideline",
        domains=("police", "conflict"), keywords=("negotiate", "listen", "rapport")),

    # ---------------- School safety (student + teacher) ----------------
    _kf("For an active-shooter event, follow Run, Hide, Fight: evacuate if you can, hide and "
        "barricade if you cannot, and fight only as a last resort.",
        "DHS / CISA", "Active Shooter Preparedness", "procedure",
        domains=("school_safety", "education", "security"),
        keywords=("active", "shooter", "threat", "lockdown", "weapon")),
    _kf("The Standard Response Protocol defines five actions: Lockout, Lockdown, Evacuate, "
        "Shelter, and Hold.",
        "I Love U Guys Foundation", "Standard Response Protocol", "procedure",
        domains=("school_safety", "education"), keywords=("lockdown", "evacuate", "shelter", "hold")),
    _kf("Teachers and school staff are mandated reporters and must report suspected child abuse "
        "or neglect (specifics vary by state).",
        "Child Welfare Information Gateway", "Mandatory Reporting laws", "regulation",
        domains=("school_safety", "education", "child_safety", "social_work"),
        keywords=("disclosure", "abuse", "report", "neglect")),
    _kf("For a tornado, move to the lowest interior room away from windows and protect your head "
        "and neck.",
        "NWS / FEMA", "Tornado Safety", "procedure",
        domains=("school_safety", "weather", "education"), keywords=("tornado", "weather", "shelter")),
    _kf("Account for every student during any emergency using current rosters; report anyone "
        "unaccounted for to responders.",
        "REMS TA Center (US Dept. of Education)", "School Emergency Planning", "procedure",
        domains=("school_safety", "education"), keywords=("account", "roster", "missing", "evacuate")),
    _kf("If approached by a stranger, children should keep distance, not accept rides or gifts, "
        "and go to a trusted adult right away.",
        "National Center for Missing & Exploited Children", "Personal Safety", "guideline",
        domains=("school_safety", "child_safety"), keywords=("stranger", "ride", "online")),

    # ---------------- Medical / first aid ----------------
    _kf("High-quality CPR: push hard and fast in the center of the chest at 100–120 compressions "
        "per minute, at least 2 inches (5 cm) deep for adults, allowing full recoil.",
        "American Heart Association", "ECC/CPR Guidelines", "procedure",
        domains=("medical", "nursing"), keywords=("cpr", "cardiac", "compression", "unresponsive", "arrest")),
    _kf("Apply an AED as soon as it is available and follow the voice prompts; early "
        "defibrillation greatly improves survival.",
        "American Heart Association", "ECC Guidelines", "procedure",
        domains=("medical", "nursing"), keywords=("aed", "cardiac", "defibrillator")),
    _kf("Recognize stroke with BE-FAST: Balance, Eyes, Face drooping, Arm weakness, Speech "
        "difficulty, Time to call emergency services.",
        "AHA / American Stroke Association", "Stroke warning signs", "procedure",
        domains=("medical", "nursing"), keywords=("stroke", "face", "speech", "arm")),
    _kf("Anaphylaxis is treated first-line with intramuscular epinephrine; give it without delay "
        "and call EMS.",
        "AAAAI / WAO", "Anaphylaxis guidelines", "procedure",
        domains=("medical", "nursing"), keywords=("anaphylaxis", "allergy", "epinephrine", "allergic")),
    _kf("Control severe bleeding (Stop the Bleed): apply firm direct pressure, pack the wound, "
        "and use a tourniquet 'high and tight' if pressure fails.",
        "American College of Surgeons", "Stop the Bleed", "procedure",
        domains=("medical", "nursing"), keywords=("bleeding", "hemorrhage", "tourniquet", "amputation")),
    _kf("For severe choking in a responsive adult, give abdominal thrusts (Heimlich) until the "
        "object clears or the person becomes unresponsive.",
        "AHA / American Red Cross", "Choking first aid", "procedure",
        domains=("medical", "nursing", "child_safety"), keywords=("choking", "airway", "heimlich")),
    _kf("For suspected opioid overdose, give naloxone, call EMS, and support breathing; naloxone "
        "can be repeated if no response.",
        "SAMHSA / CDC", "Naloxone guidance", "procedure",
        domains=("medical", "nursing", "mental_health"), keywords=("overdose", "naloxone", "opioid")),
    _kf("START triage sorts casualties by RPM — Respirations, Perfusion, and Mental status — into "
        "Immediate, Delayed, Minor, and Expectant.",
        "START Triage (Hoag/Newport Beach Fire)", "START Triage", "procedure",
        domains=("medical", "nursing"), keywords=("triage", "casualty", "victim", "mass")),

    # ---------------- Fire ----------------
    _kf("Occupant fire response (RACE): Rescue anyone in danger, Alarm/activate, Confine the "
        "fire by closing doors, then Extinguish or Evacuate.",
        "NFPA", "RACE protocol", "procedure",
        domains=("fire_safety", "hospitality"), keywords=("fire", "alarm", "smoke", "race")),
    _kf("Operate a fire extinguisher with PASS: Pull the pin, Aim at the base, Squeeze the "
        "handle, Sweep side to side.",
        "NFPA", "Portable Extinguisher use", "procedure",
        domains=("fire_safety", "hospitality", "industrial"), keywords=("extinguisher", "pass")),
    _kf("Never use elevators during a fire; use the stairs.",
        "NFPA", "Fire evacuation guidance", "guideline",
        domains=("fire_safety",), keywords=("elevator", "stair", "evacuate")),
    _kf("Working smoke alarms cut the risk of dying in a reported home fire roughly in half.",
        "NFPA", "Smoke Alarm research", "statistic",
        domains=("fire_safety",), keywords=("smoke alarm", "detector")),
    _kf("Before opening a door during a fire, check it with the back of your hand; if hot, use "
        "another exit.",
        "NFPA", "Home fire escape", "procedure",
        domains=("fire_safety",), keywords=("door", "heat", "exit")),

    # ---------------- Hazmat ----------------
    _kf("Use the Emergency Response Guidebook (ERG) to find initial isolation and protective "
        "action distances for a released material.",
        "PHMSA", "Emergency Response Guidebook", "procedure",
        domains=("hazmat", "industrial"), keywords=("chemical", "spill", "gas", "hazmat", "leak")),
    _kf("Approach a hazardous release from uphill, upwind, and upstream, and stay clear of "
        "vapors and runoff.",
        "PHMSA / NFPA", "Hazmat response", "guideline",
        domains=("hazmat", "industrial"), keywords=("upwind", "vapor", "cloud", "spill")),
    _kf("Identify placards and UN/NA numbers from a safe distance to determine the hazard class "
        "before approaching.",
        "PHMSA", "Hazmat placarding", "procedure",
        domains=("hazmat", "industrial", "road"), keywords=("placard", "tank", "un")),

    # ---------------- Wilderness / weather / SAR ----------------
    _kf("For hypothermia, move the person out of the cold, remove wet clothing, insulate, and "
        "rewarm the core gently; handle them carefully.",
        "Wilderness Medical Society", "Hypothermia guidelines", "procedure",
        domains=("wilderness", "water_safety", "search_rescue"), keywords=("hypothermia", "cold")),
    _kf("Lightning safety: When thunder roars, go indoors. Follow the 30-30 rule and wait 30 "
        "minutes after the last thunder before resuming outdoor activity.",
        "NWS / NOAA", "Lightning Safety", "guideline",
        domains=("weather", "wilderness", "sports", "search_rescue"), keywords=("lightning", "storm", "thunder")),
    _kf("If lost outdoors, STOP: Stop, Think, Observe, Plan — staying put often aids rescue.",
        "National SAR / US Forest Service", "Lost-person guidance", "procedure",
        domains=("wilderness", "search_rescue"), keywords=("lost", "hiker", "trail")),
    _kf("Turn Around, Don't Drown: six inches of moving water can knock you down and twelve "
        "inches can float many vehicles.",
        "NWS / NOAA", "Flood Safety", "statistic",
        domains=("weather", "water_safety", "road"), keywords=("flood", "water", "road", "drive")),

    # ---------------- Security / workplace ----------------
    _kf("Report unattended or suspicious items and do not touch them — 'If You See Something, Say "
        "Something.'",
        "DHS", "See Something Say Something", "guideline",
        domains=("security", "tactical", "rail"), keywords=("suspicious", "bag", "unattended", "package")),

    # ---------------- Cybersecurity ----------------
    _kf("Verify unusual payment or wire-transfer requests through a separate, trusted channel "
        "before acting (business email compromise defense).",
        "FBI IC3", "BEC guidance", "guideline",
        domains=("cybersecurity", "finance", "telecom"), keywords=("wire", "fraud", "phishing", "payment")),
    _kf("For ransomware, isolate affected systems, preserve evidence, and report to CISA/FBI; "
        "paying ransom does not guarantee recovery.",
        "CISA", "StopRansomware guidance", "procedure",
        domains=("cybersecurity", "telecom"), keywords=("ransomware", "isolate", "breach")),
    _kf("Multi-factor authentication blocks the large majority of automated account-compromise "
        "attacks; enable it everywhere feasible.",
        "CISA", "MFA guidance", "statistic",
        domains=("cybersecurity", "telecom"), keywords=("mfa", "account", "password", "login")),

    # ---------------- Critical thinking / media literacy ----------------
    _kf("Practice lateral reading: leave the page and check what independent, reputable sources "
        "say about a claim or website before trusting it.",
        "Stanford History Education Group", "Civic Online Reasoning", "guideline",
        domains=("media_literacy", "general", "legal", "finance"),
        keywords=("claim", "verify", "source", "evidence")),
    _kf("Correlation does not imply causation; look for confounders and plausible mechanisms "
        "before concluding cause and effect.",
        "Scientific method (widely taught)", "Critical reasoning", "guideline",
        domains=("media_literacy", "general"), keywords=("cause", "correlation", "evidence")),

    # ---------------- General emergency / ICS ----------------
    _kf("In any emergency, ensure scene safety first — do not become a second victim.",
        "OSHA / NFPA", "Emergency response basics", "guideline",
        domains=("general", "industrial", "construction", "medical", "agriculture", "mining", "energy"),
        keywords=("scene", "safety", "rescue", "victim")),
    _kf("The Incident Command System (ICS) provides a standard, scalable structure for managing "
        "emergencies and coordinating responders.",
        "FEMA", "ICS (NIMS)", "procedure",
        domains=("disaster_recovery", "general", "leadership", "fire_safety"),
        keywords=("command", "coordinate", "incident", "responder")),
]


# Bump when the corpus schema/seeding logic changes; combined with the fact
# count it forms a signature the embedded DB uses to detect a stale cache.
KNOWLEDGE_CORPUS_VERSION = "1"


KNOWLEDGE: List[ReferenceFact] = [
    ReferenceFact(
        fact=e["fact"], source=e["source"], reference=e["reference"], category=e["category"],
    )
    for e in _RAW
]

# Parallel metadata for matching (domains + keywords), aligned by index.
_META: List[dict] = [{"domains": e["domains"], "keywords": e["keywords"]} for e in _RAW]


# Built-in corpus paired with its matching metadata.
_BUILTIN_WITH_META = [
    (fact, tuple(meta["domains"]), tuple(meta["keywords"]))
    for fact, meta in zip(KNOWLEDGE, _META)
]

# Lazily combined (built-in + data packs); refreshed when packs change.
_COMBINED_CACHE: dict = {"fingerprint": None, "data": None}


def _pack_records():
    from ..content_packs import load_records, pack_fingerprint

    return pack_fingerprint("knowledge"), load_records("knowledge")


def _facts_with_meta() -> list:
    """Built-in facts + facts merged from knowledge data packs."""
    fingerprint, records = _pack_records()
    if _COMBINED_CACHE["fingerprint"] == fingerprint and _COMBINED_CACHE["data"] is not None:
        return _COMBINED_CACHE["data"]
    combined = list(_BUILTIN_WITH_META)
    for rec in records:
        fact_text = rec.get("fact")
        source = rec.get("source")
        reference = rec.get("reference")
        if not (fact_text and source and reference):
            continue
        fact = ReferenceFact(
            fact=str(fact_text),
            source=str(source),
            reference=str(reference),
            category=str(rec.get("category", "guideline")),
            url=str(rec.get("url", "")),
        )
        domains = tuple(rec.get("domains", ()) or ())
        keywords = tuple(rec.get("keywords", ()) or ())
        combined.append((fact, domains, keywords))
    _COMBINED_CACHE["fingerprint"] = fingerprint
    _COMBINED_CACHE["data"] = combined
    return combined


def corpus_signature() -> str:
    """Identifies the exact corpus content for cache-staleness detection."""
    data = _facts_with_meta()
    pack_fp, _ = _pack_records()
    return f"{KNOWLEDGE_CORPUS_VERSION}:{len(data)}:{pack_fp}"


def iter_facts_with_meta():
    """Yield (ReferenceFact, domains tuple, keywords tuple) for persistence."""
    for fact, domains, keywords in _facts_with_meta():
        yield fact, domains, keywords


def all_facts() -> List[ReferenceFact]:
    return [fact for fact, _, _ in _facts_with_meta()]


def fact_to_dict(f: ReferenceFact) -> dict:
    return {
        "fact": f.fact,
        "source": f.source,
        "reference": f.reference,
        "category": f.category,
        "url": f.url,
    }


def facts_for(domain: str, text: str = "", *, limit: int = 6) -> List[ReferenceFact]:
    """Return real references relevant to a scenario domain (and text keywords)."""
    text_l = (text or "").lower()
    keyword_hits: List[ReferenceFact] = []
    domain_general: List[ReferenceFact] = []
    for fact, domains, keywords in _facts_with_meta():
        in_domain = domain in domains
        kw_match = any(kw in text_l for kw in keywords) if text_l else False
        if in_domain and kw_match:
            keyword_hits.append(fact)
        elif in_domain:
            domain_general.append(fact)
    ordered = keyword_hits + domain_general
    # De-duplicate while preserving order.
    seen = set()
    out: List[ReferenceFact] = []
    for f in ordered:
        key = (f.source, f.reference, f.fact)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
        if len(out) >= limit:
            break
    return out


def attach_references(scenario, *, limit: int = 6):
    """Populate a scenario's ``references`` from the real knowledge base."""
    if scenario is None:
        return scenario
    scenario.references = facts_for(
        scenario.domain.value,
        text=f"{scenario.title} {scenario.briefing}",
        limit=limit,
    )
    return scenario


def search_facts(
    *,
    q: Optional[str] = None,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    offset: int = 0,
    limit: Optional[int] = 50,
) -> List[ReferenceFact]:
    results: List[ReferenceFact] = []
    ql = (q or "").lower()
    for fact, domains, keywords in _facts_with_meta():
        if domain and domain not in domains:
            continue
        if category and fact.category != category:
            continue
        if source and source.lower() not in fact.source.lower():
            continue
        if ql and ql not in fact.fact.lower() and ql not in fact.source.lower() \
                and ql not in fact.reference.lower() \
                and not any(ql in kw for kw in keywords):
            continue
        results.append(fact)
    if offset:
        results = results[offset:]
    if limit is not None:
        results = results[:limit]
    return results


def count_facts(
    *,
    q: Optional[str] = None,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
) -> int:
    return len(search_facts(q=q, domain=domain, category=category, source=source,
                            offset=0, limit=None))


def knowledge_sources() -> List[Dict[str, object]]:
    counts: Dict[str, int] = {}
    for fact, _, _ in _facts_with_meta():
        counts[fact.source] = counts.get(fact.source, 0) + 1
    return [
        {"source": s, "count": n}
        for s, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    ]


def knowledge_meta() -> dict:
    categories: Dict[str, int] = {}
    domains: Dict[str, int] = {}
    data = _facts_with_meta()
    for fact, doms, _ in data:
        categories[fact.category] = categories.get(fact.category, 0) + 1
        for d in doms:
            domains[d] = domains.get(d, 0) + 1
    from ..content_packs import pack_record_count

    return {
        "count": len(data),
        "builtin": len(_BUILTIN_WITH_META),
        "from_packs": pack_record_count("knowledge"),
        "sources": len(knowledge_sources()),
        "categories": categories,
        "domains": domains,
    }
