"""Procedural scenario engine — millions of addressable safety situations.

Each ProceduralFamily defines several independent AXES (event, subject, setting,
condition, time, severity). The total number of unique scenarios in a family is
the product of its axis sizes — typically hundreds of thousands to millions.
A scenario is addressed deterministically by ``(family_id, index)`` via
mixed-radix decomposition, so any of the millions can be generated on demand
without storing them on disk. Scenario ids have the form ``<family_id>__<index>``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import prod
from typing import Dict, List, Optional, Sequence, Tuple

from .models import ScenarioCue, ScenarioDefinition, ScenarioDomain

# An axis option is (code, descriptive text). Events carry an extra detail field.
Event = Tuple[str, str, str]   # (code, label, detail)
Option = Tuple[str, str]       # (code, description)

_PRIORITY_BY_SEVERITY = {
    "routine": "medium",
    "urgent": "high",
    "critical": "critical",
    "catastrophic": "critical",
}

_TIME_LIMIT_BY_SEVERITY = {
    "routine": 90,
    "urgent": 60,
    "critical": 45,
    "catastrophic": 30,
}


@dataclass(frozen=True)
class ProceduralFamily:
    family_id: str
    title: str
    domain: ScenarioDomain
    events: Sequence[Event]
    subjects: Sequence[Option]
    settings: Sequence[Option]
    conditions: Sequence[Option]
    times: Sequence[Option]
    severities: Sequence[Option]
    emergency_steps: Sequence[str] = field(default_factory=tuple)
    foresight_prompts: Sequence[str] = field(default_factory=tuple)
    critical_thinking_prompts: Sequence[str] = field(default_factory=tuple)
    debrief_rubric: Sequence[str] = field(default_factory=tuple)
    skills: Sequence[str] = field(default_factory=tuple)

    @property
    def radices(self) -> List[int]:
        return [
            len(self.events),
            len(self.subjects),
            len(self.settings),
            len(self.conditions),
            len(self.times),
            len(self.severities),
        ]

    @property
    def capacity(self) -> int:
        return prod(self.radices)


def _decompose(index: int, radices: Sequence[int]) -> List[int]:
    """Mixed-radix decomposition — unique choice tuple for each index."""
    out: List[int] = []
    for r in reversed(radices):
        out.append(index % r)
        index //= r
    return list(reversed(out))


# --------------------------------------------------------------------------- #
# Shared axis libraries (reused across families)
# --------------------------------------------------------------------------- #
_CONDITIONS = [
    ("clear", "clear and dry"),
    ("rain", "heavy rain"),
    ("fog", "dense fog"),
    ("snow", "snow and ice"),
    ("wind", "strong gusting wind"),
    ("glare", "low-sun glare"),
    ("dark", "poor lighting"),
    ("wet", "wet slippery surface"),
    ("crowded", "crowded surroundings"),
    ("construction", "active construction zone"),
]

_TIMES = [
    ("dawn", "at dawn"),
    ("morning", "during morning rush"),
    ("midday", "at midday"),
    ("evening", "during evening rush"),
    ("night", "at night"),
    ("late", "in the early hours"),
]

_SEVERITIES = [
    ("routine", "a developing situation"),
    ("urgent", "an urgent situation"),
    ("critical", "a critical emergency"),
    ("catastrophic", "a catastrophic, fast-moving emergency"),
]

_FORESIGHT = [
    "What early warning sign would you brief before this happens?",
    "If your first action fails, what is your backup?",
    "What hazard remains after the immediate threat passes?",
]

_CRITICAL = [
    "What is the single highest-risk factor right now — and why?",
    "What assumption are you making that could be wrong?",
    "What information is missing that would change your decision?",
]


def _family(
    family_id: str,
    title: str,
    domain: ScenarioDomain,
    *,
    events: Sequence[Event],
    subjects: Sequence[Option],
    settings: Sequence[Option],
    emergency_steps: Sequence[str],
    skills: Sequence[str],
    debrief_rubric: Sequence[str],
    conditions: Sequence[Option] = tuple(_CONDITIONS),
    times: Sequence[Option] = tuple(_TIMES),
    severities: Sequence[Option] = tuple(_SEVERITIES),
) -> ProceduralFamily:
    return ProceduralFamily(
        family_id=family_id,
        title=title,
        domain=domain,
        events=events,
        subjects=subjects,
        settings=settings,
        conditions=conditions,
        times=times,
        severities=severities,
        emergency_steps=emergency_steps,
        foresight_prompts=tuple(_FORESIGHT),
        critical_thinking_prompts=tuple(_CRITICAL),
        debrief_rubric=debrief_rubric,
        skills=skills,
    )


# --------------------------------------------------------------------------- #
# Family definitions — vehicles, transport, public & personal safety
# --------------------------------------------------------------------------- #
FAMILIES: Dict[str, ProceduralFamily] = {}


def _register(fam: ProceduralFamily) -> None:
    FAMILIES[fam.family_id] = fam


_register(_family(
    "road_car", "Car driving emergency", ScenarioDomain.ROAD,
    events=[
        ("brake_fail", "Brake failure", "brakes go soft with no stopping power"),
        ("tire_blowout", "Tire blowout", "a front tire blows at speed"),
        ("hydroplane", "Hydroplaning", "the car loses grip on standing water"),
        ("pedestrian", "Pedestrian darts out", "someone steps into your path"),
        ("animal", "Animal in road", "a large animal appears ahead"),
        ("skid", "Skid on ice", "the rear breaks loose on a curve"),
        ("stuck_accel", "Stuck accelerator", "the throttle sticks open"),
        ("blind_merge", "Blind merge conflict", "a vehicle merges into you unseen"),
        ("wrong_way", "Wrong-way driver", "headlights approach in your lane"),
        ("tailgater", "Aggressive tailgater", "a driver tailgates and brake-checks"),
        ("hood_up", "Hood flies up", "the hood unlatches and blocks vision"),
        ("medical_driver", "Driver medical event", "you feel faint at the wheel"),
        ("fire_engine", "Engine fire", "smoke rises from under the hood"),
        ("debris", "Road debris", "an object falls off the truck ahead"),
        ("flood_road", "Flooded road", "water covers the road ahead"),
        ("door_child", "Child unbuckles", "a child unbuckles in traffic"),
        ("gps_wrong", "Bad GPS route", "navigation points into a closed road"),
        ("phone_temptation", "Phone distraction", "an urgent call arrives while driving"),
        ("stall_crossing", "Stall on crossing", "the car stalls on a rail crossing"),
        ("road_rage", "Road rage confrontation", "another driver exits to confront you"),
    ],
    subjects=[
        ("sedan", "a compact sedan"), ("suv", "a loaded SUV"), ("ev", "an electric car"),
        ("minivan", "a family minivan"), ("sports", "a sports car"),
        ("rental", "an unfamiliar rental"), ("pickup", "a pickup truck"),
        ("hybrid", "a hybrid"), ("old_car", "an older car with worn tires"),
        ("teen_driver", "a car driven by a new teen driver"),
        ("rideshare", "a rideshare with passengers"),
        ("towing", "a car towing a small trailer"),
    ],
    settings=[
        ("highway", "on a busy highway"), ("city", "on a city street"),
        ("residential", "in a residential neighborhood"), ("mountain", "on a mountain road"),
        ("bridge", "on a bridge"), ("parking", "in a crowded parking lot"),
        ("rural", "on a rural two-lane road"), ("tunnel", "inside a tunnel"),
        ("intersection", "at a busy intersection"), ("school_zone", "in a school zone"),
        ("onramp", "on a freeway on-ramp"), ("roundabout", "in a roundabout"),
    ],
    emergency_steps=[
        "Control — ease off power, steer smoothly, avoid hard braking",
        "Signal — warn others; hazard lights and horn",
        "Position — guide the vehicle to the safest available space",
        "Stop & secure — park, set brake, exit to a safe side",
        "Call — alert emergency services with location",
    ],
    skills=["road-safety", "defensive-driving", "quick-decision"],
    debrief_rubric=[
        "Maintained vehicle control", "Warned others", "Chose safe stopping spot",
        "Protected occupants", "Called for help",
    ],
))

_register(_family(
    "road_motorcycle", "Motorcycle riding emergency", ScenarioDomain.ROAD,
    events=[
        ("gravel", "Gravel in corner", "loose gravel appears mid-corner"),
        ("car_left", "Car turns left", "an oncoming car turns across your path"),
        ("door", "Dooring hazard", "a parked car opens its door"),
        ("wobble", "Speed wobble", "the bars begin to oscillate"),
        ("front_lock", "Front-wheel lock", "the front brake locks under panic"),
        ("blind_spot", "Blind-spot merge", "a car drifts into your lane"),
        ("pothole", "Pothole at speed", "a deep pothole looms ahead"),
        ("wet_paint", "Slippery markings", "wet road paint reduces grip"),
        ("tar_snake", "Tar snakes", "melted tar lines in a curve"),
        ("debris_road", "Debris strike", "an object bounces toward you"),
        ("wind_gust", "Cross-wind gust", "a gust pushes you toward the line"),
        ("animal_dart", "Animal crossing", "a deer bounds onto the road"),
        ("rear_approach", "Fast rear approach", "a car closes fast from behind"),
        ("fuel_starve", "Fuel starvation", "the engine cuts in traffic"),
        ("chain", "Chain failure", "the chain jumps under power"),
        ("visor_fog", "Visor fog", "your visor fogs suddenly"),
    ],
    subjects=[
        ("sport", "a sport bike"), ("cruiser", "a heavy cruiser"),
        ("adv", "an adventure bike"), ("scooter_moto", "a 150cc scooter"),
        ("touring", "a loaded touring bike with passenger"),
        ("dirt", "a dual-sport"), ("electric_moto", "an electric motorcycle"),
        ("learner", "a learner-permit rider"), ("commuter", "a daily commuter bike"),
        ("vintage", "a vintage bike with drum brakes"),
    ],
    settings=[
        ("highway", "on the highway"), ("canyon", "on a twisty canyon road"),
        ("city", "in dense city traffic"), ("intersection", "at an intersection"),
        ("rural", "on a rural road"), ("wet_street", "on a wet street"),
        ("lane_split", "while lane-splitting"), ("parking", "in a parking area"),
    ],
    emergency_steps=[
        "Look — eyes to escape path, not the hazard",
        "Smooth inputs — progressive brakes, no panic grab",
        "Body — counter-steer and stabilize",
        "Escape — take the gap; protect the body",
        "Recover — stop safely; assess injuries",
    ],
    skills=["motorcycle-safety", "defensive-riding", "quick-decision"],
    debrief_rubric=[
        "Looked to escape path", "Used smooth braking", "Counter-steered",
        "Protected self", "Recovered safely",
    ],
))

_register(_family(
    "road_truck", "Commercial truck emergency", ScenarioDomain.ROAD,
    events=[
        ("jackknife", "Jackknife risk", "the trailer begins to swing"),
        ("brake_fade", "Brake fade", "brakes fade on a long grade"),
        ("load_shift", "Load shift", "cargo shifts in a curve"),
        ("rollover", "Rollover risk", "high center of gravity in a ramp"),
        ("blowout_steer", "Steer-tire blowout", "a front tire blows"),
        ("low_bridge", "Low clearance", "a low bridge appears ahead"),
        ("runaway", "Runaway downhill", "speed builds beyond control"),
        ("coupling", "Coupling failure", "the trailer warning sounds"),
        ("wind_high", "High-wind push", "wind shoves the empty trailer"),
        ("fog_convoy", "Fog pileup risk", "brake lights vanish in fog"),
        ("wide_turn", "Wide-turn conflict", "a car slips up your right side"),
        ("hazmat_leak", "Cargo leak", "a placarded load may be leaking"),
        ("fatigue", "Driver fatigue", "you catch yourself drifting"),
        ("merge_block", "Merge blocked", "traffic boxes you in at a ramp"),
    ],
    subjects=[
        ("semi", "a loaded semi"), ("tanker", "a fuel tanker"),
        ("flatbed", "a flatbed with strapped cargo"), ("box", "a box truck"),
        ("doubles", "a doubles trailer"), ("reefer", "a refrigerated trailer"),
        ("dump", "a dump truck"), ("car_hauler", "a car hauler"),
        ("empty", "an empty trailer"), ("oversize", "an oversize load"),
    ],
    settings=[
        ("interstate", "on the interstate"), ("grade", "on a steep mountain grade"),
        ("ramp", "on a cloverleaf ramp"), ("city", "in tight city streets"),
        ("dock", "near a loading dock"), ("rural", "on a rural highway"),
        ("weigh", "approaching a weigh station"), ("workzone", "in a work zone"),
    ],
    emergency_steps=[
        "Reduce speed early — engine/jake brake, gear down",
        "Stabilize — gentle steering, avoid trailer swing",
        "Communicate — hazards, CB/radio, warn traffic",
        "Choose runoff — ramp, shoulder, escape lane",
        "Secure — stop, chock, protect scene; call dispatch/911",
    ],
    skills=["commercial-driving", "load-safety", "quick-decision"],
    debrief_rubric=[
        "Slowed early", "Avoided jackknife", "Warned traffic",
        "Used safe runoff", "Secured scene",
    ],
))

_register(_family(
    "road_bus", "Bus driver emergency", ScenarioDomain.ROAD,
    events=[
        ("passenger_fall", "Passenger fall", "a standing rider falls"),
        ("medical_rider", "Rider medical", "a passenger collapses"),
        ("fight", "Onboard altercation", "two riders begin fighting"),
        ("door_drag", "Door drag", "a bag catches in the closing door"),
        ("brake_soft", "Soft brakes", "pedal goes low approaching a stop"),
        ("fire_smell", "Electrical smell", "smoke odor in the cabin"),
        ("evac", "Sudden evacuation", "a hazard forces immediate egress"),
        ("child_left", "Child left aboard", "a sleeping child remains at terminus"),
        ("road_block", "Sudden road block", "an obstacle blocks the lane"),
        ("aggressive", "Aggressive boarder", "a rider refuses fare and threatens"),
        ("flood_route", "Flooded route", "water rises across the route"),
        ("stuck_seatbelt", "Wheelchair securement", "a securement fails in transit"),
    ],
    subjects=[
        ("city_bus", "a packed city bus"), ("school_bus", "a school bus of children"),
        ("coach", "an intercity coach"), ("articulated", "an articulated bus"),
        ("shuttle", "an airport shuttle"), ("minibus", "a paratransit minibus"),
        ("electric_bus", "an electric bus"), ("double_decker", "a double-decker"),
    ],
    settings=[
        ("downtown", "downtown"), ("highway", "on the highway"),
        ("school_route", "on a school route"), ("terminal", "near a terminal"),
        ("stop", "at a crowded stop"), ("rural", "on a rural route"),
    ],
    emergency_steps=[
        "Stabilize the vehicle and stop safely",
        "Protect riders — calm, clear instructions",
        "Assist — medical or evacuation as needed",
        "Communicate with dispatch and 911",
        "Account for all passengers",
    ],
    skills=["transit-safety", "passenger-care", "de-escalation"],
    debrief_rubric=[
        "Stopped safely", "Protected riders", "Gave clear instructions",
        "Coordinated help", "Accounted for passengers",
    ],
))

_register(_family(
    "rail_train", "Train operator emergency", ScenarioDomain.RAIL,
    events=[
        ("trespasser", "Trespasser on track", "a person is on the line ahead"),
        ("signal_pass", "Signal at danger", "a red signal appears late"),
        ("obstruction", "Track obstruction", "debris blocks the rail"),
        ("brake_loss", "Brake pressure loss", "train brake pressure drops"),
        ("fire_car", "Onboard fire", "smoke reported in a carriage"),
        ("medical_pax", "Passenger medical", "a passenger collapses onboard"),
        ("level_crossing", "Crossing vehicle", "a car is stuck on the crossing"),
        ("overrun", "Platform overrun risk", "you may overrun the platform"),
        ("flood_track", "Flooded track", "water covers the rails ahead"),
        ("door_fault", "Door fault", "a door shows unsafe in motion"),
        ("buckled_rail", "Heat buckle", "a rail buckle is reported ahead"),
        ("comm_loss", "Comms loss", "radio to control fails"),
    ],
    subjects=[
        ("commuter", "a packed commuter train"), ("freight", "a long freight train"),
        ("metro", "a metro train"), ("highspeed", "a high-speed trainset"),
        ("light_rail", "a light-rail vehicle"), ("regional", "a regional service"),
        ("night_freight", "a night freight"), ("tram", "a street tram"),
    ],
    settings=[
        ("mainline", "on the mainline"), ("station", "approaching a station"),
        ("tunnel", "in a tunnel"), ("bridge", "on a viaduct"),
        ("yard", "in the yard"), ("crossing", "near a level crossing"),
        ("urban", "on urban tracks"), ("grade", "on a descending grade"),
    ],
    emergency_steps=[
        "Apply appropriate braking for the hazard",
        "Sound horn; warn and protect the line",
        "Notify control immediately with location",
        "Protect passengers; manage evacuation if ordered",
        "Do not move until authorized",
    ],
    skills=["rail-safety", "emergency-procedures"],
    debrief_rubric=[
        "Correct braking", "Warned and protected line", "Notified control",
        "Protected passengers", "Followed authority",
    ],
))

_register(_family(
    "rail_transit", "Subway & passenger rail safety", ScenarioDomain.RAIL,
    events=[
        ("person_track", "Person on tracks", "someone falls onto the tracks"),
        ("smoke_tunnel", "Smoke in tunnel", "smoke fills a stopped train"),
        ("crush", "Platform crush", "the platform is dangerously crowded"),
        ("medical_platform", "Medical on platform", "a rider collapses"),
        ("stuck_train", "Stalled in tunnel", "the train stops between stations"),
        ("aggressor", "Aggressive rider", "a rider threatens others"),
        ("door_trap", "Caught in doors", "a person is caught in closing doors"),
        ("power_loss", "Power loss", "lights and ventilation fail"),
        ("unattended_bag", "Unattended bag", "a suspicious bag is found"),
        ("flood_station", "Station flooding", "water enters the station"),
    ],
    subjects=[
        ("rider", "you as a commuter"), ("staff", "you as station staff"),
        ("guard", "you as a train guard"), ("parent", "you as a parent with a child"),
        ("tourist", "you as a tourist unfamiliar with the system"),
        ("mobility", "you assisting a mobility-impaired rider"),
    ],
    settings=[
        ("platform", "on the platform"), ("train", "inside the train"),
        ("concourse", "in the concourse"), ("escalator", "on the escalators"),
        ("tunnel", "in the tunnel section"), ("turnstile", "at the turnstiles"),
    ],
    emergency_steps=[
        "Alert staff/emergency intercom immediately",
        "Keep clear of the platform edge and tracks",
        "Help others without entering danger",
        "Follow staff and signage to safe exits",
        "Report what you saw accurately",
    ],
    skills=["transit-safety", "situational-analysis"],
    debrief_rubric=[
        "Alerted staff", "Stayed clear of danger", "Helped safely",
        "Used correct exits", "Reported accurately",
    ],
))

_register(_family(
    "bicycle", "Bicycle safety", ScenarioDomain.MICROMOBILITY,
    events=[
        ("dooring", "Dooring", "a parked car opens its door"),
        ("right_hook", "Right hook", "a car turns right across you"),
        ("left_cross", "Left cross", "an oncoming car turns into you"),
        ("pothole", "Pothole", "a deep pothole appears late"),
        ("car_pass", "Close pass", "a car passes far too close"),
        ("pedestrian_step", "Pedestrian steps out", "a walker enters the lane"),
        ("rail_groove", "Rail groove", "your wheel nears a track groove"),
        ("brake_grab", "Brake grab", "the front brake grabs on a descent"),
        ("dog", "Loose dog", "a dog charges into your path"),
        ("gravel_corner", "Gravel corner", "loose gravel mid-corner"),
        ("wet_metal", "Wet metal plate", "a slick steel plate ahead"),
        ("group_brake", "Group sudden brake", "the rider ahead brakes hard"),
        ("blind_drive", "Blind driveway", "a car emerges from a driveway"),
        ("chain_drop", "Chain drop", "the chain drops in traffic"),
    ],
    subjects=[
        ("commuter", "a commuter cyclist"), ("child_bike", "a child on a bike"),
        ("ebike", "an e-bike rider"), ("roadie", "a road cyclist in a group"),
        ("cargo", "a cargo-bike rider with a child"), ("courier", "a delivery courier"),
        ("tourer", "a loaded touring cyclist"), ("beginner", "a nervous beginner"),
        ("mtb", "a mountain biker on a path"), ("senior", "an older recreational rider"),
    ],
    settings=[
        ("bike_lane", "in a painted bike lane"), ("shared_road", "sharing a busy road"),
        ("intersection", "at an intersection"), ("path", "on a mixed-use path"),
        ("downhill", "on a fast descent"), ("roundabout", "in a roundabout"),
        ("school_zone", "in a school zone"), ("bridge", "on a narrow bridge"),
    ],
    emergency_steps=[
        "Scan and predict — assume you are unseen",
        "Brake controlled — rear-bias, no front grab",
        "Steer to escape — take the safe line",
        "Signal and communicate presence",
        "Stop safely; check yourself and others",
    ],
    skills=["cycling-safety", "situational-awareness", "quick-decision"],
    debrief_rubric=[
        "Anticipated the hazard", "Braked under control", "Took safe line",
        "Communicated presence", "Recovered safely",
    ],
))

_register(_family(
    "scooter", "E-scooter & kick-scooter safety", ScenarioDomain.MICROMOBILITY,
    events=[
        ("curb", "Curb catch", "a curb edge catches the small wheel"),
        ("brake_lockup", "Brake lockup", "the regen brake locks suddenly"),
        ("ped_path", "Pedestrian on path", "a walker steps in front"),
        ("car_door", "Car door", "a door opens beside you"),
        ("wet_grip", "Wet grip loss", "the deck slips in the rain"),
        ("pothole", "Pothole jolt", "a pothole jolts the bars"),
        ("speed_wobble", "Speed wobble", "the bars shimmy at speed"),
        ("battery_cut", "Power cut", "the motor cuts mid-ride"),
        ("crowd", "Crowded sidewalk", "you enter a dense crowd"),
        ("tram_track", "Tram track", "a wheel nears a rail groove"),
        ("dark_rider", "Unlit at night", "you ride with poor lighting"),
        ("two_up", "Two riders", "a friend hops on, unbalancing you"),
    ],
    subjects=[
        ("commuter", "a commuter on a rental scooter"),
        ("teen", "a teen rider"), ("tourist", "a tourist exploring"),
        ("delivery", "a delivery rider"), ("first_time", "a first-time rider"),
        ("kick", "a kid on a kick-scooter"), ("senior", "an older rider"),
        ("helmetless", "a rider without a helmet"),
    ],
    settings=[
        ("sidewalk", "on a busy sidewalk"), ("bike_lane", "in a bike lane"),
        ("road", "on a city road"), ("campus", "on a campus path"),
        ("plaza", "in a pedestrian plaza"), ("crossing", "at a crossing"),
    ],
    emergency_steps=[
        "Slow early — small wheels punish surprises",
        "Both feet ready; lower center of gravity",
        "Steer to open space; protect head",
        "Dismount safely if control is lost",
        "Move clear and check for injury",
    ],
    skills=["micromobility-safety", "quick-decision"],
    debrief_rubric=[
        "Slowed for conditions", "Stayed balanced", "Avoided pedestrians",
        "Protected head", "Recovered safely",
    ],
))

_register(_family(
    "boat", "Boating & marine safety", ScenarioDomain.MARINE,
    events=[
        ("mob", "Person overboard", "someone falls into the water"),
        ("capsize", "Capsize risk", "a wake threatens to roll the boat"),
        ("engine_out", "Engine failure", "the motor dies in current"),
        ("grounding", "Grounding", "the depth shallows fast"),
        ("fire_bilge", "Bilge fire", "smoke rises from the engine well"),
        ("collision", "Collision course", "another vessel closes fast"),
        ("storm", "Squall line", "a squall approaches quickly"),
        ("flood_hull", "Hull flooding", "water enters the hull"),
        ("anchor_drag", "Anchor drag", "the anchor drags toward rocks"),
        ("hypothermia", "Cold water exposure", "a swimmer is going cold"),
        ("fuel_leak", "Fuel leak", "fuel smell with passengers aboard"),
        ("lost_power_night", "Night power loss", "power and lights fail at night"),
    ],
    subjects=[
        ("runabout", "a small runabout"), ("pontoon", "a loaded pontoon"),
        ("sailboat", "a sailboat"), ("fishing", "a fishing boat"),
        ("kayak", "a kayak"), ("canoe", "a canoe"), ("jetboat", "a jet boat"),
        ("dinghy", "an inflatable dinghy"), ("cabin", "a cabin cruiser with family"),
    ],
    settings=[
        ("lake", "on a busy lake"), ("river", "on a moving river"),
        ("coastal", "in coastal waters"), ("harbor", "in a crowded harbor"),
        ("open", "in open water"), ("rapids", "near rapids"),
        ("marina", "in a marina"), ("bay", "in a tidal bay"),
    ],
    emergency_steps=[
        "Account for everyone; PFDs on",
        "Reduce way; stabilize the vessel",
        "Communicate — VHF 16/mayday with position",
        "Contain — recover MOB / stop flooding / fight fire",
        "Prepare contingencies; protect lives over property",
    ],
    skills=["marine-safety", "water-rescue", "quick-decision"],
    debrief_rubric=[
        "Counted/protected people", "Stabilized vessel", "Communicated position",
        "Contained the threat", "Prioritized lives",
    ],
))

_register(_family(
    "watercraft", "Personal watercraft & paddle safety", ScenarioDomain.MARINE,
    events=[
        ("ejection", "Rider ejection", "a rider is thrown from the craft"),
        ("rip_current", "Rip current", "the current pulls you offshore"),
        ("collision_pwc", "Near collision", "another craft cuts across"),
        ("flip", "Paddle flip", "the kayak flips in chop"),
        ("entrapment", "Foot entrapment", "a foot snags underwater"),
        ("cold_shock", "Cold shock", "sudden immersion in cold water"),
        ("offshore_wind", "Offshore wind", "wind pushes you from shore"),
        ("swimmer_distress", "Swimmer distress", "a swimmer waves for help"),
        ("dam_below", "Below low-head dam", "you drift toward a dam boil"),
        ("tow_failure", "Tow line failure", "a towed tube line snaps"),
    ],
    subjects=[
        ("jetski", "a jet ski rider"), ("kayaker", "a sea kayaker"),
        ("paddleboard", "a paddleboarder"), ("canoeist", "a canoeist"),
        ("tuber", "a towed tuber"), ("snorkeler", "a snorkeler"),
        ("beginner_paddle", "a first-time paddler"), ("family_paddle", "a family paddling together"),
    ],
    settings=[
        ("beach", "off a public beach"), ("lake", "on a lake"),
        ("river", "on a river"), ("surf", "in the surf zone"),
        ("estuary", "in an estuary"), ("reservoir", "on a reservoir"),
    ],
    emergency_steps=[
        "Stay with the craft if able; signal for help",
        "Conserve energy; do not fight a rip directly",
        "Keep airway clear; assist others without endangering self",
        "Use whistle/visual signals; call for rescue",
        "Get to shore or stable flotation",
    ],
    skills=["water-safety", "self-rescue"],
    debrief_rubric=[
        "Stayed with flotation", "Signaled help", "Conserved energy",
        "Assisted safely", "Reached safety",
    ],
))

_register(_family(
    "pedestrian", "Pedestrian safety", ScenarioDomain.PEDESTRIAN,
    events=[
        ("turning_car", "Turning car", "a car turns into the crosswalk"),
        ("backing", "Backing vehicle", "a car reverses out of a space"),
        ("ev_silent", "Silent EV", "a quiet EV approaches unheard"),
        ("phone_walk", "Distracted walking", "you step out while looking down"),
        ("runner_bike", "Fast cyclist", "a cyclist speeds on the path"),
        ("ice_walk", "Icy sidewalk", "the walkway is sheet ice"),
        ("jaywalk_pressure", "Jaywalk pressure", "the crowd jaywalks midblock"),
        ("low_visibility", "Low visibility", "drivers cannot see you at night"),
        ("child_dart", "Child runs ahead", "a child bolts toward the curb"),
        ("scooter_path", "Scooter on walk", "a scooter weaves through walkers"),
        ("construction_detour", "Sidewalk closed", "a closure forces you into the road"),
        ("rail_crossing_walk", "Pedestrian crossing", "gates lower as you cross tracks"),
    ],
    subjects=[
        ("commuter", "you as a commuter"), ("parent_stroller", "you pushing a stroller"),
        ("senior", "you as an older pedestrian"), ("child_walk", "you guiding a young child"),
        ("wheelchair", "you using a wheelchair"), ("group", "you leading a group"),
        ("tourist", "you as a tourist"), ("runner", "you out for a run"),
        ("vision_impaired", "you with low vision"), ("dog_walker", "you walking a dog"),
    ],
    settings=[
        ("crosswalk", "at a marked crosswalk"), ("midblock", "midblock"),
        ("parking_lot", "in a parking lot"), ("transit_stop", "at a transit stop"),
        ("school_zone", "in a school zone"), ("downtown", "downtown"),
        ("rural_road", "on a road without sidewalks"), ("trail", "on a shared trail"),
    ],
    emergency_steps=[
        "Stop and assess — never assume you are seen",
        "Make eye contact; confirm drivers yield",
        "Choose the safest path and timing",
        "Move predictably; protect children and others",
        "Reach a safe area before continuing",
    ],
    skills=["pedestrian-safety", "situational-awareness"],
    debrief_rubric=[
        "Assessed before stepping", "Confirmed driver intent", "Chose safe timing",
        "Protected others", "Reached safety",
    ],
))

_register(_family(
    "police", "Police & public-safety officer scenarios", ScenarioDomain.POLICE,
    events=[
        ("traffic_stop", "High-risk stop", "the stopped driver reaches from view"),
        ("welfare", "Welfare check", "no answer at a home with signs of distress"),
        ("crowd", "Crowd tension", "a gathering grows hostile"),
        ("mh_crisis", "Mental-health crisis", "a person in crisis holds an object"),
        ("domestic", "Domestic call", "shouting and a child present inside"),
        ("foot_pursuit", "Foot pursuit choice", "a suspect flees into a crowd"),
        ("found_weapon", "Found weapon", "a weapon is reported in a park"),
        ("dui", "Impaired driver", "a driver weaves and won't stop"),
        ("missing_child", "Missing child", "a child is reported lost at an event"),
        ("active_threat", "Active threat report", "shots reported nearby"),
        ("medical_scene", "Medical at scene", "a subject becomes unresponsive"),
        ("deescalation", "De-escalation moment", "an upset person can still be talked down"),
    ],
    subjects=[
        ("patrol", "a solo patrol officer"), ("two_officer", "a two-officer unit"),
        ("campus_pd", "a campus officer"), ("transit_pd", "a transit officer"),
        ("rural_deputy", "a rural deputy far from backup"),
        ("community", "a community resource officer"),
        ("rookie", "a field-training rookie"), ("supervisor", "a shift supervisor"),
    ],
    settings=[
        ("roadside", "on a roadside"), ("residence", "at a residence"),
        ("park", "in a public park"), ("downtown", "downtown"),
        ("school", "near a school"), ("transit", "at a transit hub"),
        ("event", "at a public event"), ("apartment", "in an apartment complex"),
    ],
    emergency_steps=[
        "Assess threat and request resources early",
        "Create distance/time; prioritize de-escalation",
        "Communicate clearly; coordinate with partners",
        "Protect bystanders and the subject's safety",
        "Act within policy; document and request medical",
    ],
    skills=["public-safety", "de-escalation", "crisis-response"],
    debrief_rubric=[
        "Assessed and called resources", "Used distance/de-escalation",
        "Coordinated communication", "Protected all parties", "Acted within policy",
    ],
))

_register(_family(
    "school_student", "Student safety", ScenarioDomain.SCHOOL_SAFETY,
    events=[
        ("bully", "Bullying", "a peer is being harassed"),
        ("stranger", "Stranger contact", "an unknown adult offers a ride"),
        ("online_grooming", "Online contact", "a stranger messages you online"),
        ("fight_hall", "Hallway fight", "a fight breaks out nearby"),
        ("lockdown", "Lockdown", "a lockdown is announced"),
        ("fire_drill", "Fire alarm", "the fire alarm sounds in class"),
        ("medical_peer", "Peer medical", "a classmate collapses"),
        ("weapon_seen", "Weapon seen", "you spot a weapon in a bag"),
        ("cyberbully", "Cyberbullying", "cruel posts target a classmate"),
        ("lost_young", "Lost younger child", "a little kid is alone and crying"),
        ("substance", "Substance offer", "someone offers you a vape/pill"),
        ("walk_home", "Unsafe walk home", "a car follows you walking home"),
    ],
    subjects=[
        ("elementary", "an elementary student"), ("middle", "a middle-schooler"),
        ("high", "a high-schooler"), ("new_student", "a new student"),
        ("bus_rider", "a bus rider"), ("after_school", "a student after hours"),
        ("special_needs", "a student needing extra support"),
        ("bystander", "a student bystander"),
    ],
    settings=[
        ("classroom", "in the classroom"), ("hallway", "in the hallway"),
        ("playground", "on the playground"), ("bus", "on the school bus"),
        ("cafeteria", "in the cafeteria"), ("online", "online at home"),
        ("walk", "walking to/from school"), ("restroom", "near the restrooms"),
    ],
    emergency_steps=[
        "Get to safety; trust your instincts",
        "Tell a trusted adult immediately",
        "Do not confront danger alone",
        "Follow drill procedures exactly",
        "Report clearly what happened",
    ],
    skills=["student-safety", "situational-awareness"],
    debrief_rubric=[
        "Moved to safety", "Told a trusted adult", "Avoided confronting danger",
        "Followed procedure", "Reported clearly",
    ],
))

_register(_family(
    "school_teacher", "Teacher & staff safety leadership", ScenarioDomain.SCHOOL_SAFETY,
    events=[
        ("lockdown_lead", "Lead lockdown", "a lockdown begins during class"),
        ("medical_student", "Student medical", "a student has a seizure"),
        ("intruder", "Unknown adult", "a stranger enters the wing"),
        ("evacuate", "Evacuation", "an alarm forces evacuation"),
        ("fight_break", "Break up a fight", "two students fight in your room"),
        ("threat_note", "Threat discovered", "a threatening note is found"),
        ("allergic", "Allergic reaction", "a student reacts to food"),
        ("weather_shelter", "Severe weather", "a tornado warning sounds"),
        ("disclosure", "Abuse disclosure", "a student discloses harm at home"),
        ("missing_count", "Missing student", "a student is unaccounted for"),
        ("online_class_breach", "Virtual class breach", "an intruder enters the video class"),
        ("field_trip", "Field-trip emergency", "a student wanders off on a trip"),
    ],
    subjects=[
        ("elementary_teacher", "an elementary teacher"),
        ("hs_teacher", "a high-school teacher"), ("sub", "a substitute teacher"),
        ("aide", "a classroom aide"), ("coach_staff", "a coach"),
        ("counselor", "a counselor"), ("librarian", "a librarian"),
        ("specialist", "a special-education specialist"),
    ],
    settings=[
        ("classroom", "in the classroom"), ("gym", "in the gym"),
        ("lab", "in a science lab"), ("hallway", "in the hallway"),
        ("playground", "on the playground"), ("bus_duty", "on bus duty"),
        ("field_trip", "on a field trip"), ("virtual", "in a virtual class"),
    ],
    emergency_steps=[
        "Account for every student first",
        "Follow the safety protocol precisely",
        "Communicate with admin/emergency services",
        "Keep a calm, authoritative tone",
        "Document and follow up (including reporting duties)",
    ],
    skills=["teacher-safety", "classroom-management", "crisis-response"],
    debrief_rubric=[
        "Accounted for students", "Followed protocol", "Communicated clearly",
        "Stayed calm", "Completed reporting",
    ],
))


def list_families() -> List[ProceduralFamily]:
    return list(FAMILIES.values())


def get_family(family_id: str) -> Optional[ProceduralFamily]:
    return FAMILIES.get(family_id)


def total_capacity() -> int:
    return sum(f.capacity for f in FAMILIES.values())


def capacity_by_family() -> Dict[str, int]:
    return {fid: f.capacity for fid, f in FAMILIES.items()}


def _priority(severity_code: str) -> str:
    return _PRIORITY_BY_SEVERITY.get(severity_code, "high")


def generate(family_id: str, index: int) -> Optional[ScenarioDefinition]:
    """Deterministically build the scenario at ``index`` within a family."""
    fam = FAMILIES.get(family_id)
    if fam is None:
        return None
    cap = fam.capacity
    if cap == 0:
        return None
    index = index % cap
    ei, sui, sei, ci, ti, vi = _decompose(index, fam.radices)
    ev_code, ev_label, ev_detail = fam.events[ei]
    su_code, su_desc = fam.subjects[sui]
    se_code, se_desc = fam.settings[sei]
    co_code, co_desc = fam.conditions[ci]
    tm_code, tm_desc = fam.times[ti]
    sv_code, sv_desc = fam.severities[vi]

    scenario_id = f"{family_id}__{index}"
    title = f"{ev_label} — {su_desc} {se_desc}"
    briefing = (
        f"You are {su_desc} {se_desc} {tm_desc}, in {co_desc} conditions. "
        f"Suddenly {ev_detail} — {sv_desc}. Train calm, aware decision-making "
        "under pressure; this is about judgment, not memorized answers."
    )
    prio = _priority(sv_code)
    cues = [
        ScenarioCue(cue_id="event", text=ev_detail, priority=prio),
        ScenarioCue(cue_id="setting", text=f"You are {se_desc}", priority="medium"),
        ScenarioCue(cue_id="conditions", text=f"Conditions: {co_desc}", priority="high"
                    if co_code in ("fog", "snow", "dark", "wet", "rain") else "medium"),
        ScenarioCue(cue_id="timing", text=f"Timing: {tm_desc}", priority="low"),
        ScenarioCue(cue_id="severity", text=f"Severity: {sv_desc}", priority=prio),
    ]
    return ScenarioDefinition(
        scenario_id=scenario_id,
        title=title,
        domain=fam.domain,
        briefing=briefing,
        cues=cues,
        decision_prompt=(
            "State your FIRST action sequence and your priorities — not every detail."
        ),
        decision_time_limit_s=_TIME_LIMIT_BY_SEVERITY.get(sv_code, 60),
        emergency_steps=list(fam.emergency_steps),
        foresight_prompts=list(fam.foresight_prompts),
        critical_thinking_prompts=list(fam.critical_thinking_prompts),
        debrief_rubric=list(fam.debrief_rubric),
        skills=list(fam.skills),
    )


def resolve_procedural(scenario_id: str) -> Optional[ScenarioDefinition]:
    """Resolve a ``<family_id>__<index>`` id to a generated scenario."""
    if "__" not in scenario_id:
        return None
    family_id, _, idx = scenario_id.rpartition("__")
    if family_id not in FAMILIES:
        return None
    try:
        index = int(idx)
    except ValueError:
        return None
    return generate(family_id, index)


def materialize_samples(per_family: int = 120) -> List[ScenarioDefinition]:
    """A browsable subset of the procedural space for the committed catalog."""
    out: List[ScenarioDefinition] = []
    for fid, fam in FAMILIES.items():
        n = min(per_family, fam.capacity)
        # Spread indices across the family's capacity for variety.
        step = max(1, fam.capacity // n)
        for k in range(n):
            scenario = generate(fid, (k * step) % fam.capacity)
            if scenario is not None:
                out.append(scenario)
    return out
