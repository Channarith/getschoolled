"""Extended scenario generators — additional domains and deep incident libraries."""

from __future__ import annotations

from typing import Iterator, List

from .catalog_template import _cue, gen_cross_product
from .models import ScenarioDefinition, ScenarioDomain

# Shared step libraries reused across domains.
_FIRST_RESPONDER_STEPS = [
    "Scene safety — protect self and bystanders",
    "Primary threat survey — life over limb",
    "Activate help — call or delegate early",
    "Intervene within training scope",
    "Reassess — conditions evolve",
]

_CRISIS_COMMS_STEPS = [
    "Gather verified facts only",
    "Identify stakeholders and harms",
    "Communicate what is known and unknown",
    "Assign owners and next checkpoint",
    "Document decisions",
]


def gen_nursing() -> Iterator[ScenarioDefinition]:
    events = [
        ("fall_risk", "Patient fall", "Elderly patient found on floor, confused"),
        ("med_error", "Medication error", "Wrong dose prepared at bedside"),
        ("rapid_response", "Rapid response", "SpO2 dropping; altered mental status"),
        ("sepsis", "Sepsis suspicion", "Fever, tachycardia, hypotension trend"),
        ("elopement", "Patient elopement", "Psychiatric patient missing from unit"),
        ("iv_infiltration", "IV infiltration", "Swelling and pain at IV site"),
        ("code_blue", "Code blue", "Unresponsive patient in hallway"),
        ("family_conflict", "Family conflict", "Family blocking care decisions"),
        ("isolation_breach", "Isolation breach", "PPE breach in contact isolation room"),
        ("equipment_alarm", "Alarm fatigue", "Multiple false alarms; real event unclear"),
    ]
    settings = [
        ("med_surg", "medical-surgical floor"),
        ("icu", "ICU bedside"),
        ("ed", "emergency department bay"),
        ("l_and_d", "labor and delivery"),
        ("psych", "psychiatric unit"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.NURSING,
        id_prefix="nursing",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: (
            f"{st.title()}: {det}. You are the nurse at bedside. Act in 60 seconds."
        ),
        cues_fn=lambda code, det, st: [
            _cue("event", det, "critical"),
            _cue("setting", st, "medium"),
            _cue("orders", "Recent orders may be incomplete", "medium"),
        ],
        emergency_steps=_FIRST_RESPONDER_STEPS,
        skills=["nursing", "clinical-judgment", "patient-safety"],
        debrief_rubric=["Patient safety first", "Escalated appropriately", "Documented actions"],
    )


def gen_hazmat() -> Iterator[ScenarioDefinition]:
    events = [
        ("chlorine", "Chlorine release", "Greenish cloud; respiratory irritation reported"),
        ("acid_spill", "Acid spill", "Corrosive liquid spreading toward drain"),
        ("unknown_powder", "Unknown powder", "White powder package ruptured in mailroom"),
        ("gas_odor", "Gas odor", "Rotten egg smell near utility vault"),
        ("radiation", "Radiation alarm", "Portal monitor alarm; source unknown"),
        ("chemical_mix", "Incompatible mix", "Two cleaners mixed; heat and fumes"),
        ("tank_leak", "Tank leak", "DOT tank valve weeping in yard"),
        ("lab_solvent", "Lab solvent", "Flammable solvent spill in fume hood failure"),
    ]
    settings = [
        ("plant", "chemical plant"),
        ("warehouse", "distribution warehouse"),
        ("lab", "research laboratory"),
        ("highway", "highway spill site"),
        ("campus", "university campus"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.HAZMAT,
        id_prefix="hazmat",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Identify zone and actions.",
        cues_fn=lambda c, d, s: [_cue("hazard", d, "critical"), _cue("wind", "Wind from west", "high")],
        emergency_steps=[
            "Isolate — establish hot/warm/cold zones",
            "Notify — hazmat and fire dispatch",
            "Protect — upwind and uphill positioning",
            "Identify — do not guess chemical properties",
            "Decontaminate — only when protocol clear",
        ],
        skills=["hazmat", "emergency-procedures"],
    )


def gen_energy() -> Iterator[ScenarioDefinition]:
    events = [
        ("substation", "Substation arc", "Loud arc flash; worker down"),
        ("gas_leak", "Gas line rupture", "Excavation hit gas service"),
        ("downed_line", "Downed power line", "Line on vehicle with occupant"),
        ("transformer", "Transformer fire", "Oil fire at pad mount"),
        ("wind_turbine", "Wind turbine fault", "Technician stranded in nacelle"),
        ("solar_arc", "Solar array arc", "DC arc during maintenance"),
        ("dam_spill", "Dam spillway", "Unusual flow; public downstream"),
        ("nuclear_alarm", "Plant alarm", "Non-routine alarm; media calling"),
    ]
    settings = [
        ("utility", "electric utility yard"),
        ("substation", "transmission substation"),
        ("residential", "residential neighborhood"),
        ("wind_farm", "wind farm"),
        ("hydro", "hydroelectric facility"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.ENERGY,
        id_prefix="energy",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Utility safety protocols apply.",
        cues_fn=lambda c, d, s: [_cue("hazard", d, "critical")],
        emergency_steps=[
            "De-energize if trained and safe",
            "Establish exclusion zone",
            "Account for all personnel",
            "Notify control center and responders",
        ],
        skills=["energy", "utility-safety"],
    )


def gen_search_rescue() -> Iterator[ScenarioDefinition]:
    events = [
        ("lost_hiker", "Lost hiker", "Last seen off trail; weather worsening"),
        ("avalanche", "Avalanche burial", "Beacon signal; limited probe time"),
        ("cliff", "Cliff rescue", "Injured climber two pitches up"),
        ("flood_rescue", "Flood rescue", "Vehicle in rising water"),
        ("cave", "Cave incident", "Cavers overdue; air quality unknown"),
        ("urban_collapse", "Collapse search", "Void space tap heard"),
        ("k9_track", "K9 track lost", "Scent trail ends at roadway"),
        ("drone_sighting", "Drone sighting", "Heat signature in brush"),
    ]
    settings = [
        ("mountain", "mountain county"),
        ("desert", "desert county"),
        ("coastal", "coastal bluffs"),
        ("urban", "urban disaster zone"),
        ("forest", "national forest"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.SEARCH_RESCUE,
        id_prefix="sar",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()} SAR: {det}.",
        skills=["search-rescue", "wilderness"],
    )


def gen_legal() -> Iterator[ScenarioDefinition]:
    events = [
        ("client_intake", "Urgent intake", "Client claims imminent harm"),
        ("evidence", "Evidence chain", "Possible spoliation discovered"),
        ("conflict", "Conflict check", "Opposing party is family member"),
        ("deadline", "Filing deadline", "Court closes in 2 hours; missing signature"),
        ("privilege", "Privilege call", "Client discusses crime on open line"),
        ("settlement", "Settlement pressure", "Client wants to accept harmful terms"),
        ("witness", "Witness coaching", "Client asks you to tell them what to say"),
        ("media", "Media contact", "Reporter calls about active case"),
    ]
    settings = [
        ("criminal", "criminal defense"),
        ("family", "family law"),
        ("corporate", "corporate counsel"),
        ("legal_aid", "legal aid clinic"),
        ("immigration", "immigration practice"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.LEGAL,
        id_prefix="legal",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Ethical judgment required.",
        decision_prompt="What is your ethical and procedural response in 60 seconds?",
        skills=["legal-ethics", "critical-thinking"],
    )


def gen_parenting() -> Iterator[ScenarioDefinition]:
    events = [
        ("tantrum", "Public tantrum", "Child melting down in store"),
        ("bully", "Bullying report", "Child reports ongoing bullying"),
        ("screen_time", "Screen conflict", "Teen refuses limits; homework due"),
        ("choking_home", "Choking at home", "Toddler coughing silently"),
        ("stranger_door", "Stranger at door", "Child home alone; doorbell"),
        ("pool_home", "Pool gate open", "Neighbor pool gate left open"),
        ("online_chat", "Secret online chat", "Unknown contact on child's tablet"),
        ("car_seat", "Car seat error", "Seat installed incorrectly before trip"),
    ]
    settings = [
        ("home", "family home"),
        ("school_pickup", "school pickup line"),
        ("park", "neighborhood park"),
        ("travel", "family road trip"),
        ("relatives", "relative's house"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.PARENTING,
        id_prefix="parenting",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Parent/caregiver decision.",
        skills=["parenting", "child-safety"],
    )


def gen_conflict() -> Iterator[ScenarioDefinition]:
    events = [
        ("neighbor", "Neighbor dispute", "Property line argument escalating"),
        ("coworker", "Coworker conflict", "Shouting match in open office"),
        ("customer", "Angry customer", "Customer threatening staff"),
        ("roommate", "Roommate conflict", "Utilities unpaid; locks changed"),
        ("traffic", "Road rage", "Driver exits vehicle aggressively"),
        ("online", "Online pile-on", "Viral post targeting your organization"),
        ("meeting", "Meeting derail", "Two leaders arguing in all-hands"),
        ("service", "Service refusal", "Staff refusing to serve patron"),
    ]
    settings = [
        ("workplace", "workplace"),
        ("retail", "retail floor"),
        ("community", "community meeting"),
        ("home", "residential"),
        ("online", "virtual meeting"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.CONFLICT,
        id_prefix="conflict",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. De-escalate safely.",
        skills=["de-escalation", "conflict-resolution"],
    )


def gen_disaster_recovery() -> Iterator[ScenarioDefinition]:
    events = [
        ("datacenter", "Datacenter flood", "Water in server row"),
        ("supply_chain", "Supply chain break", "Critical part unavailable 6 weeks"),
        ("staffing", "Staffing collapse", "40% staff unreachable post-storm"),
        ("donations", "Donation surge", "Unsorted goods blocking operations"),
        ("misinfo", "Recovery misinfo", "False reopening rumor spreading"),
        ("generator", "Generator failure", "Shelter loses power in cold"),
        ("cyber_after", "Post-disaster cyber", "Phishing targeting victims"),
        ("housing", "Housing crunch", "Displaced families exceed shelter beds"),
    ]
    settings = [
        ("city", "municipal EOC"),
        ("ngo", "NGO field office"),
        ("hospital", "hospital continuity"),
        ("school", "school district"),
        ("small_biz", "small business owner"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.DISASTER_RECOVERY,
        id_prefix="recovery",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Recovery leadership.",
        skills=["disaster-recovery", "leadership"],
    )


def gen_aviation_ifr() -> Iterator[ScenarioDefinition]:
    events = [
        ("imc_loss", "IMC spatial disorientation", "Unexpected IMC on VFR flight"),
        ("approach_break", "Approach break-out", "Minimums with runway not in sight"),
        ("ice_approach", "Icing on approach", "Ice accretion during hold"),
        ("nav_failure", "Navigation failure", "GPS anomaly; partial panel"),
        ("comm_failure", "Comm failure", "Lost comm in Class C"),
        ("thunderstorm", "Thunderstorm embed", "Buildup ahead on IFR route"),
        ("missed_approach", "Missed approach fuel", "Low fuel after missed approach"),
        ("autopilot", "Autopilot disconnect", "Hard disconnect in IMC"),
        ("pressurization", "Pressurization loss", "Cabin altitude warning"),
        ("terrain", "Terrain warning", "GPWS/TAWS alert on approach"),
    ]
    settings = [
        ("jet", "light jet"),
        ("turboprop", "turboprop"),
        ("ifr_train", "IFR trainer"),
        ("airline_reg", "regional airliner"),
        ("cargo", "cargo IFR"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.AVIATION_IFR,
        id_prefix="ifr",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: (
            f"IFR {st}: {det}. Fly instruments; think ahead."
        ),
        emergency_steps=[
            "Aviate — trust instruments; control aircraft",
            "Navigate — safe altitude and heading",
            "Communicate — declare; get vectors/help",
            "Manage — fuel, ice, systems methodically",
        ],
        skills=["aviation", "ifr", "emergency-procedures"],
    )


def gen_wilderness() -> Iterator[ScenarioDefinition]:
    events = [
        ("snake", "Snake bite", "Puncture marks; swelling spreading"),
        ("hypothermia", "Hypothermia", "Shivering stopped; confusion"),
        ("water_crossing", "Water crossing", "Flashy stream blocking return"),
        ("bear", "Bear encounter", "Bear with cubs on trail"),
        ("lost", "Lost overnight", "No shelter; temp dropping"),
        ("altitude", "Altitude illness", "HAPE symptoms in partner"),
        ("lightning", "Lightning exposure", "Hair standing; storm overhead"),
        ("injury_pack", "Injury remote", "Ankle fracture 8 miles from trailhead"),
    ]
    settings = [
        ("backcountry", "backcountry trail"),
        ("desert", "desert canyon"),
        ("alpine", "alpine zone"),
        ("coastal", "coastal wilderness"),
        ("jungle", "tropical trail"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.WILDERNESS,
        id_prefix="wilderness",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Limited resources.",
        skills=["wilderness", "survival"],
    )


def gen_water_safety() -> Iterator[ScenarioDefinition]:
    events = [
        ("rip_current", "Rip current", "Swimmer drifting offshore"),
        ("drowning", "Active drowning", "Vertical bobbing; not waving"),
        ("boat_capsize", "Capsize", "Small boat overturned"),
        ("dam_release", "Dam release", "Water rising below dam"),
        ("ice_rescue", "Ice rescue", "Person on thin ice"),
        ("diving", "Diving emergency", "Diver surfaced confused"),
        ("flood_drive", "Flood driving", "Water over road"),
        ("pool_drain", "Pool entrapment", "Hair caught in drain"),
    ]
    settings = [
        ("beach", "public beach"),
        ("lake", "inland lake"),
        ("river", "river park"),
        ("pool", "community pool"),
        ("marina", "marina dock"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.WATER_SAFETY,
        id_prefix="water",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Water rescue judgment.",
        skills=["water-safety", "lifesaving"],
    )


def gen_food_safety() -> Iterator[ScenarioDefinition]:
    events = [
        ("outbreak", "Outbreak signal", "Multiple vomiting reports same menu"),
        ("allergen", "Undeclared allergen", "Peanut in mislabeled batch"),
        ("temp_abuse", "Temperature abuse", "Walk-in at 55°F during rush"),
        ("foreign_object", "Foreign object", "Metal in prepared food"),
        ("recall", "Supplier recall", "Recalled lot already served"),
        ("pest", "Pest infestation", "Rodent sighting in prep area"),
        ("chemical", "Sanitizer mix-up", "Chemical smell on utensils"),
        ("power_out", "Power outage", "Refrigeration down 3 hours"),
    ]
    settings = [
        ("restaurant", "full-service restaurant"),
        ("catering", "catering kitchen"),
        ("plant", "food processing plant"),
        ("school_cafe", "school cafeteria"),
        ("food_truck", "food truck"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.FOOD_SAFETY,
        id_prefix="food",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Food safety lead.",
        skills=["food-safety", "public-health"],
    )


def gen_retail() -> Iterator[ScenarioDefinition]:
    events = [
        ("shoplift", "Shoplifting confrontation", "Confrontation at exit"),
        ("slip_fall", "Slip and fall", "Customer down; wet floor nearby"),
        ("robbery", "Robbery hint", "Note passed; cashier panicking"),
        ("flash_mob", "Flash mob theft", "Coordinated grab-and-run"),
        ("price_error", "Pricing outrage", "Angry crowd at checkout"),
        ("child_lost", "Lost child", "Child at service desk crying"),
        ("product_recall", "Shelf recall", "Recalled product still on shelf"),
        ("power_outage", "Blackout", "Dark store; customers in aisles"),
    ]
    settings = [
        ("grocery", "grocery store"),
        ("mall", "mall anchor store"),
        ("pharmacy", "pharmacy counter"),
        ("big_box", "big-box retailer"),
        ("convenience", "convenience store"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.RETAIL,
        id_prefix="retail",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Floor supervisor.",
        skills=["retail", "customer-safety"],
    )


def gen_mining() -> Iterator[ScenarioDefinition]:
    events = [
        ("roof_fall", "Roof fall", "Roof bolt pattern failed"),
        ("methane", "Methane alarm", "Elevated readings at face"),
        ("haul_truck", "Haul truck brake", "Grade runaway load"),
        ("confined", "Confined space", "Worker unresponsive in vessel"),
        ("explosive", "Misfire", "Undetonated charge after blast"),
        ("dust", "Dust explosion risk", "Visible dust cloud near ignition"),
        ("rescue", "Underground rescue", "Personnel missing after bump"),
        ("surface", "Tailings leak", "Tailings water overtopping"),
    ]
    settings = [
        ("underground", "underground coal"),
        ("open_pit", "open-pit mine"),
        ("quarry", "aggregate quarry"),
        ("metals", "hard-rock mine"),
        ("salt", "salt mine"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.MINING,
        id_prefix="mining",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Mine safety.",
        skills=["mining", "industrial-safety"],
    )


def gen_pharma() -> Iterator[ScenarioDefinition]:
    events = [
        ("batch_deviation", "Batch deviation", "OOS result on critical batch"),
        ("cold_chain", "Cold chain break", "Vaccine storage excursion"),
        ("counterfeit", "Suspect counterfeit", "Packaging anomaly on shipment"),
        ("adverse_event", "Adverse event", "Cluster of unexpected reactions"),
        ("data_integrity", "Data integrity", "Audit trail gap discovered"),
        ("recall_decision", "Recall decision", "Possible contamination signal"),
        ("clinical_hold", "Clinical hold", "Serious event in trial"),
        ("compounding", "Compounding error", "Wrong concentration prepared"),
    ]
    settings = [
        ("manufacturing", "manufacturing suite"),
        ("clinical", "clinical site"),
        ("pharmacy", "hospital pharmacy"),
        ("distribution", "distribution center"),
        ("qc_lab", "QC laboratory"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.PHARMA,
        id_prefix="pharma",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. GxP judgment.",
        skills=["pharma", "quality", "critical-thinking"],
    )


def gen_social_work() -> Iterator[ScenarioDefinition]:
    events = [
        ("mandated_report", "Mandated report", "Child discloses abuse"),
        ("safety_plan", "Safety plan", "DV survivor returns to abuser"),
        ("boundaries", "Boundary test", "Client offers large gift"),
        ("home_visit", "Unsafe home visit", "Hostile family member present"),
        ("substance", "Substance crisis", "Client intoxicated with infant present"),
        ("housing", "Housing denial", "Client facing eviction tonight"),
        ("self_harm", "Self-harm disclosure", "Client states plan"),
        ("confidentiality", "Confidentiality clash", "Police request records"),
    ]
    settings = [
        ("office", "field office"),
        ("school", "school social work"),
        ("hospital", "hospital discharge planning"),
        ("shelter", "family shelter"),
        ("mobile", "mobile crisis unit"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.SOCIAL_WORK,
        id_prefix="social",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Ethical field judgment.",
        skills=["social-work", "ethics", "de-escalation"],
    )


def gen_telecom() -> Iterator[ScenarioDefinition]:
    events = [
        ("fiber_cut", "Fiber cut", "Backbone cut; region degrading"),
        ("ransom_router", "Router compromise", "Config changes from unknown IP"),
        ("911_outage", "911 outage", "PSAP reports failures"),
        ("tower", "Tower climber emergency", "Climber distress on tower"),
        ("billing_crisis", "Billing system down", "Cannot provision emergency services"),
        ("satellite", "Satellite link loss", "Remote sites isolated"),
        ("ddos_isp", "DDoS on ISP", "Core link saturated"),
        ("misconfig", "Routing misconfig", "Traffic blackholing continent"),
    ]
    settings = [
        ("noc", "network operations center"),
        ("field", "field technician"),
        ("mobile_core", "mobile core"),
        ("rural", "rural exchange"),
        ("data_center", "telco data center"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.TELECOM,
        id_prefix="telecom",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. Network continuity.",
        skills=["telecom", "incident-response"],
    )


def gen_aviation_expanded() -> Iterator[ScenarioDefinition]:
    """Additional aviation incidents beyond base catalog."""
    events = [
        ("dual_failure", "Dual comm failure", "Radio and transponder failure"),
        ("door_open", "Door unsecured", "Door warning at low altitude"),
        ("carb_ice", "Carb ice", "RPM drop in humid conditions"),
        ("vacuum", "Vacuum failure", "Attitude indicator unreliable"),
        ("alternator", "Alternator failure", "Electrical bus degrading"),
        ("runway_short", "Short runway", "Landing long with obstacle"),
        ("microburst", "Microburst", "Airspeed drop on final"),
        ("fuel_contam", "Fuel contamination", "Engine sputter after refuel"),
        ("tcas", "TCAS RA", "Resolution advisory in busy airspace"),
        ("medical_pax", "Passenger medical", "Unresponsive passenger"),
    ]
    settings = [
        ("C172", "Cessna 172"),
        ("PA44", "Piper Seminole"),
        ("B737", "B737 sim session"),
        ("helicopter", "R44 helicopter"),
        ("glider", "glider tow"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.AVIATION,
        id_prefix="aviation_x",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st} — {det}. PIC decisions.",
        emergency_steps=[
            "Aviate", "Navigate", "Communicate", "Checklist", "Land",
        ],
        skills=["aviation", "emergency-procedures"],
    )


def gen_medical_expanded() -> Iterator[ScenarioDefinition]:
    events = [
        ("drowning", "Near drowning", "Pulse weak; foam at mouth"),
        ("electrocution", "Electrocution", "Burns; possible arrhythmia"),
        ("amputation", "Amputation", "Traumatic amputation with tourniquet need"),
        ("preg_complication", "Pregnancy complication", "Heavy bleeding; 32 weeks"),
        ("diabetic", "Diabetic emergency", "Altered; glucose unknown"),
        ("allergic_child", "Pediatric anaphylaxis", "Wheeze after snack"),
        ("spinal", "Spinal precaution", "Diving injury on shore"),
        ("mass_shooting", "Mass casualty", "Multiple gunshot victims"),
        ("chemical_exposure", "Chemical exposure", "Tearing eyes; lung irritation"),
        ("psych_crisis", "Psychiatric crisis", "Suicidal ideation with means"),
    ]
    settings = [
        ("arena", "sports arena"),
        ("festival", "music festival"),
        ("worksite", "construction site"),
        ("transit", "transit station"),
        ("rural", "rural highway"),
    ]
    yield from gen_cross_product(
        domain=ScenarioDomain.MEDICAL,
        id_prefix="medical_x",
        events=events,
        settings=settings,
        briefing_fn=lambda lbl, det, st: f"{st.title()}: {det}. First responder triage.",
        emergency_steps=_FIRST_RESPONDER_STEPS,
        skills=["medical-triage", "emergency-procedures"],
    )


EXTENDED_GENERATORS = [
    gen_nursing,
    gen_hazmat,
    gen_energy,
    gen_search_rescue,
    gen_legal,
    gen_parenting,
    gen_conflict,
    gen_disaster_recovery,
    gen_aviation_ifr,
    gen_wilderness,
    gen_water_safety,
    gen_food_safety,
    gen_retail,
    gen_mining,
    gen_pharma,
    gen_social_work,
    gen_telecom,
    gen_aviation_expanded,
    gen_medical_expanded,
]
