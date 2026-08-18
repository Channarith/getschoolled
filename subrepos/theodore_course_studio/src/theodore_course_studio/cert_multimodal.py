"""Multimodal learning kits for each certification-prep segment.

Every cert page ships text + picture + motion video already. This module adds
friendly examples, a curated multiple-choice check, and a game challenge so
learners who prefer images, text, video, quizzes, or games each have a path.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from .engagement import GameChallenge, GameKind
from .assessment import QuizQuestion
from .knowledge import LearningObjective
from .types import CourseSlide


CERT_MODALITIES = (
    "text",
    "image",
    "video",
    "examples",
    "activity",
    "quiz",
    "game",
)


@dataclass(frozen=True)
class SegmentKit:
    """One complete multimodal packet for a lesson segment (page)."""

    examples: tuple[str, ...]
    quiz_prompt: str
    quiz_choices: tuple[str, str, str, str]
    quiz_correct_index: int
    quiz_explanation: str
    game_kind: str = "match_term"
    game_prompt: str = ""
    game_options: tuple[str, ...] = ()
    game_correct_index: int = 0
    game_steps: tuple[str, ...] = ()


def _kit(
    examples: tuple[str, ...],
    prompt: str,
    choices: tuple[str, str, str, str],
    correct: int,
    explanation: str,
    *,
    game_kind: str = "match_term",
    game_prompt: str = "",
    game_options: tuple[str, ...] = (),
    game_correct: int = 0,
    game_steps: tuple[str, ...] = (),
) -> SegmentKit:
    opts = game_options or (choices[correct], choices[(correct + 1) % 4], choices[(correct + 2) % 4])
    return SegmentKit(
        examples=examples,
        quiz_prompt=prompt,
        quiz_choices=choices,
        quiz_correct_index=correct,
        quiz_explanation=explanation,
        game_kind=game_kind,
        game_prompt=game_prompt or prompt,
        game_options=opts,
        game_correct_index=game_correct if game_options else 0,
        game_steps=game_steps,
    )


# Curated kits keyed by slide title (unique across cert tracks).
_KITS: dict[str, SegmentKit] = {
    "Prep, not a DMV course": _kit(
        (
            "You use this studio to review ideas before reading the official handbook.",
            "A friend says “this replaces DMV school” — you correct them: it does not.",
            "Before your exam, you still take free practice tests on dmv.ca.gov.",
        ),
        "What is this lesson?",
        (
            "A study aid — not a DMV-approved driver education course",
            "An official DMV license class",
            "A substitute for the California Driver's Handbook",
            "A court-ordered traffic school",
        ),
        0,
        "Always treat the current California Driver's Handbook as the authority.",
    ),
    "California learner's permit": _kit(
        (
            "You are 16, finish the application steps, pass vision and knowledge tests.",
            "You confirm age and education rules on dmv.ca.gov before you go.",
            "You bring required ID documents — not just a phone screenshot of grades.",
        ),
        "What do you typically need for a California provisional instruction permit?",
        (
            "Vision exam, knowledge test, and required application steps",
            "Only a written note from a parent",
            "A full driver’s license from another country",
            "Proof you already own a car",
        ),
        0,
        "Confirm current DMV rules — they can change.",
        game_steps=("Check dmv.ca.gov requirements", "Pass vision and knowledge tests", "Complete the application steps"),
        game_kind="order_steps",
        game_prompt="Order the usual permit path",
    ),
    "Right-of-way at stops": _kit(
        (
            "You arrive first at a four-way stop — you go when clear.",
            "You and another car arrive together — you yield to the driver on your right.",
            "An ambulance approaches with lights and sirens — everyone yields.",
        ),
        "At a four-way stop, if two cars arrive together, who goes first?",
        (
            "The driver on the right",
            "Whoever honks first",
            "The larger vehicle",
            "The driver turning left always",
        ),
        0,
        "First to arrive goes first; if tied, yield to the right. Always yield to pedestrians and emergency vehicles.",
    ),
    "California speed basics": _kit(
        (
            "Rain is heavy — you drive below the posted limit because conditions demand it.",
            "A residential street is posted 25 mph unless another limit is posted.",
            "A clear freeway shows a higher posted limit — you still obey Basic Speed Law.",
        ),
        "California’s Basic Speed Law means:",
        (
            "Never drive faster than is safe for conditions, even below the posted limit",
            "You may exceed the limit if no police are visible",
            "Posted limits do not apply in rain",
            "Only freeways have speed rules",
        ),
        0,
        "Safe for conditions always beats “the number on the sign.”",
    ),
    "Following distance": _kit(
        (
            "In dry daylight you pick a fixed landmark and count three seconds behind a car.",
            "Fog rolls in — you increase the gap beyond three seconds.",
            "You follow a motorcycle — you leave extra space.",
        ),
        "In good conditions, what following gap should you aim for?",
        (
            "At least three seconds",
            "One car length only",
            "Half a second if you are late",
            "Whatever the car behind you uses",
        ),
        0,
        "Increase space in rain, fog, night, traffic, or near large trucks.",
    ),
    "Signals and lane changes": _kit(
        (
            "Before changing lanes: mirrors, signal, shoulder check, then move smoothly.",
            "You decide not to change lanes inside an intersection.",
            "You signal early so others can predict your turn.",
        ),
        "Correct lane-change order is closest to:",
        (
            "Check mirrors, signal, check blind spot, then move",
            "Move first, then signal if someone honks",
            "Signal only after you are in the new lane",
            "Close your eyes and hope",
        ),
        0,
        "Never change lanes in an intersection.",
        game_steps=("Check mirrors", "Signal", "Check blind spot", "Move smoothly"),
        game_kind="order_steps",
        game_prompt="Order a safe lane change",
    ),
    "Turning and red lights": _kit(
        (
            "Right on red after a full stop is usually OK unless a sign bans it — you still yield.",
            "You stop completely behind the line before turning right on red.",
            "Left on red is only from one-way onto one-way when allowed — you verify.",
        ),
        "In California, a right turn on red generally requires:",
        (
            "A complete stop, then yield to pedestrians and cross traffic (unless prohibited)",
            "Rolling through if the way looks empty",
            "Honking instead of stopping",
            "Turning only after the light turns green",
        ),
        0,
        "Signs can prohibit right on red — always look.",
    ),
    "School buses in California": _kit(
        (
            "Undivided road, bus has red lights + stop arm — traffic both ways stops.",
            "Divided highway — only same-direction traffic must stop.",
            "Lights stop and arm withdraws — you proceed when safe.",
        ),
        "On an undivided roadway, who must stop for a school bus with flashing red lights and stop arm?",
        (
            "Traffic in both directions",
            "Only cars behind the bus",
            "Only cars coming from the left",
            "Nobody if you are late for work",
        ),
        0,
        "On divided highways, only same-direction traffic must stop.",
    ),
    "Seat belts and phones": _kit(
        (
            "Everyone buckles up before you shift into drive.",
            "You need to text — you pull over safely instead of holding the phone.",
            "Hands-free is used only when legal and still attention stays on the road.",
        ),
        "While driving in California, handheld phone use is:",
        (
            "Restricted — use hands-free or pull over safely",
            "Allowed anytime under 25 mph",
            "Required for navigation screens",
            "Fine if you keep one hand on the wheel",
        ),
        0,
        "Seat belts are required; put the phone away.",
    ),
    "DUI limits (California)": _kit(
        (
            "You are 22 and plan to drink — you arrange a ride home, not a “I’ll be fine.”",
            "A friend under 21 learns zero-tolerance applies to them.",
            "Commercial drivers remember their BAC limit is lower.",
        ),
        "For drivers 21+, California’s BAC limit is generally:",
        (
            "0.08%",
            "0.15%",
            "0.00% for all ages with no exceptions listed elsewhere",
            "1.0%",
        ),
        0,
        "Under 21: zero tolerance. Never drive impaired.",
    ),
    "What to do after a crash": _kit(
        (
            "If safe, you move out of traffic and turn on hazards.",
            "Someone is hurt — you call 911.",
            "You exchange license, contact, and insurance info without arguing fault.",
        ),
        "After a crash, a safe first priority is often:",
        (
            "Move out of traffic if safe, hazards on, help injured, exchange info",
            "Leave immediately to avoid paperwork",
            "Argue about who is at fault at the scene",
            "Post the crash on social media first",
        ),
        0,
        "Do not argue fault at the scene; report as required.",
        game_steps=("Move to safety if possible", "Call 911 for injuries", "Exchange required information"),
        game_kind="order_steps",
        game_prompt="Order post-crash priorities",
    ),
    "Study next": _kit(
        (
            "You schedule signs next, then sharing the road.",
            "You take short practice quizzes after each 15–20 minute block.",
            "You avoid cramming the night before the exam alone.",
        ),
        "A good next study habit is:",
        (
            "Short lessons plus official CA DMV practice tests",
            "Skipping the handbook entirely",
            "Only watching viral driving videos",
            "Memorizing one friend’s wrong answers",
        ),
        0,
        "Spaced practice beats marathon cramming.",
    ),
    "Regulatory signs": _kit(
        (
            "A red octagon always means STOP.",
            "A white rectangle sets a speed limit you must obey.",
            "Do Not Enter / One Way / No U-Turn tell you what you must not do.",
        ),
        "A red octagon sign means:",
        ("STOP", "YIELD", "Caution only", "Hospital ahead"),
        0,
        "Regulatory signs tell you what you must or must not do.",
    ),
    "Yield and stop": _kit(
        (
            "Red-and-white triangle: slow, give way, proceed when clear.",
            "Stop sign: full stop behind the limit line or crosswalk.",
            "You do not treat yield as “optional slow-roll.”",
        ),
        "A red-and-white triangle sign means:",
        ("YIELD — slow and give way", "STOP completely always", "No parking", "End of freeway"),
        0,
        "Stop requires a complete stop; yield means give way.",
    ),
    "Warning signs": _kit(
        (
            "Yellow diamond warns of a curve — you slow and prepare.",
            "Pedestrian or school warning — you scan and reduce speed.",
            "You know warning signs rarely demand a full stop by themselves.",
        ),
        "Yellow diamond signs usually:",
        (
            "Warn of hazards ahead — slow and prepare",
            "Give mandatory parking rules",
            "Replace stop signs",
            "Mark bike shops only",
        ),
        0,
        "Warnings prepare you; they are not always full stops.",
    ),
    "Guide and service signs": _kit(
        (
            "Green signs guide routes and exits.",
            "Blue signs mark services like fuel and food.",
            "Brown signs mark parks and recreation.",
        ),
        "Blue highway signs typically mark:",
        ("Services such as fuel, food, lodging", "Stop ahead", "School zones", "Lane ends only"),
        0,
        "Green = guidance, blue = services, brown = recreation.",
    ),
    "Traffic signals": _kit(
        (
            "Flashing red = treat like a stop sign.",
            "Flashing yellow = proceed with caution.",
            "Steady red = stop; green = go if clear.",
        ),
        "A flashing red traffic signal means:",
        ("Stop — same idea as a stop sign", "Speed up through the intersection", "Yield only to trucks", "Ignore if turning right"),
        0,
        "Yellow means prepare to stop if safe; do not enter on red.",
    ),
    "Pavement markings": _kit(
        (
            "Yellow lines separate opposite directions.",
            "White lines separate same-direction lanes.",
            "A solid line on your side means do not cross to pass.",
        ),
        "Yellow center lines generally separate:",
        ("Opposite directions of traffic", "Parking stalls only", "Bike lanes from sidewalks", "School zones from parks"),
        0,
        "Solid line on your side: do not pass/change across it.",
    ),
    "Railroad crossings": _kit(
        (
            "Lights flash — you stop at least 15 feet from the nearest rail.",
            "Gates lower — you never drive around them.",
            "Stalled on tracks — exit and move away at an angle toward the oncoming train.",
        ),
        "If railroad lights are flashing, you should:",
        (
            "Stop at least 15 feet from the nearest rail",
            "Weave around the gate if no train is visible",
            "Stop on the tracks to look both ways",
            "Speed across before the gate drops",
        ),
        0,
        "Never cross when lights flash or gates lower.",
        game_steps=("See lights or gates", "Stop well before the rail", "Proceed only when clear and signals stop"),
        game_kind="order_steps",
        game_prompt="Order safe railroad crossing behavior",
    ),
    "Roundabouts": _kit(
        (
            "You yield to traffic already in the circle.",
            "You enter when there is a gap, then signal when exiting.",
            "You do not stop in the circulating roadway without cause.",
        ),
        "When entering a roundabout you should:",
        (
            "Yield to traffic already in the circle, then enter when clear",
            "Stop in the middle to choose an exit",
            "Accelerate to beat circulating traffic",
            "Always turn left from the right lane",
        ),
        0,
        "Signal when exiting; keep moving with the flow when safe.",
    ),
    "Parking clearances": _kit(
        (
            "You leave space near hydrants and crosswalks.",
            "Red curb means no parking — you choose another spot.",
            "You check posted signs before leaving the car.",
        ),
        "Colored curb zones in California cities:",
        (
            "Often restrict parking — read signs and local rules",
            "Are only decorative",
            "Always allow free all-day parking",
            "Apply only to trucks",
        ),
        0,
        "Do not park too close to hydrants, crosswalks, or stop signs.",
    ),
    "Night headlights": _kit(
        (
            "30 minutes after sunset you turn headlights on.",
            "Fog — you use low beams, not high beams that bounce back.",
            "Oncoming car — you dim high beams.",
        ),
        "Use headlights from roughly:",
        (
            "30 minutes after sunset to 30 minutes before sunrise (and in poor visibility)",
            "Only on freeways",
            "Only when streetlights are out",
            "Never with daytime running lights present",
        ),
        0,
        "Dim high beams for oncoming traffic and when following closely.",
    ),
    "Pedestrians and bikes": _kit(
        (
            "A person steps into a crosswalk — you yield.",
            "You give a cyclist a wide berth when passing.",
            "Stopped at red, your bumper is not blocking the crosswalk.",
        ),
        "You must yield to pedestrians:",
        (
            "In marked or unmarked crosswalks",
            "Only if they make eye contact",
            "Only on weekends",
            "Never if you have a green light",
        ),
        0,
        "Watch bike lanes and intersections; never block a crosswalk.",
    ),
    "Motorcycle awareness": _kit(
        (
            "Before a lane change you double-check the blind spot for a motorcycle.",
            "You leave a full lane and extra following distance.",
            "A motorcycle is ahead in rain — you increase space further.",
        ),
        "Motorcycles are easy to miss, so you should:",
        (
            "Give them a full lane and extra following distance",
            "Share a lane tightly to save space",
            "Tailgate so they speed up",
            "Honk continuously when near them",
        ),
        0,
        "Double-check blind spots before lane changes.",
    ),
    "Large truck no-zones": _kit(
        (
            "You avoid lingering beside a truck’s cab where the driver cannot see you.",
            "You do not cut in and brake hard in front of a truck.",
            "A truck swings wide right — you give room for the turn.",
        ),
        "Around large trucks, a key safety idea is:",
        (
            "Stay out of blind “no-zones” and avoid cutting in front",
            "Draft inches behind to save fuel",
            "Pass on the right while they turn",
            "Assume they can stop as quickly as a car",
        ),
        0,
        "Trucks need long stopping distance and wide turns.",
    ),
    "Freeway merging": _kit(
        (
            "On-ramp: you accelerate to match traffic, signal, and merge into a gap.",
            "After passing, you return to the right when safe.",
            "You do not stop on the ramp to “wait forever” if traffic is moving.",
        ),
        "A solid freeway merge habit is:",
        (
            "Match speed, signal, merge into a safe gap",
            "Enter at walking speed and hope others stop",
            "Always stop at the end of every ramp",
            "Use the left lane for cruising only",
        ),
        0,
        "Left lane is for passing — return right when safe.",
        game_steps=("Accelerate on the ramp", "Signal and find a gap", "Merge smoothly", "Return right after passing"),
        game_kind="order_steps",
        game_prompt="Order a freeway merge",
    ),
    "Weather and hydroplaning": _kit(
        (
            "Rain starts — you slow down and increase following distance.",
            "Fog — low beams on.",
            "Hydroplane — ease off gas, steer straight, avoid sudden braking.",
        ),
        "If you hydroplane you should:",
        (
            "Ease off the gas and steer straight until tires grip",
            "Slam the brakes and yank the wheel",
            "Accelerate to “get through it”",
            "Close your eyes",
        ),
        0,
        "Slow in rain and fog; use low beams in fog.",
    ),
    "Emergency vehicles": _kit(
        (
            "Sirens behind you — pull to the right and stop.",
            "You do not block the intersection.",
            "You move over for stopped emergency or tow vehicles when required.",
        ),
        "When an emergency vehicle uses lights and sirens, you should:",
        (
            "Pull to the right and stop, clearing the path",
            "Speed up to clear the lane ahead",
            "Stop in the middle of the intersection",
            "Follow closely behind them",
        ),
        0,
        "Yield completely; never block intersections.",
    ),
    "Work zones": _kit(
        (
            "You obey the reduced work-zone speed even if the road looks empty.",
            "A flagger signals stop — you stop.",
            "You expect lane shifts and workers near traffic.",
        ),
        "In work zones, fines often:",
        ("Double", "Disappear", "Apply only to trucks", "Are optional if cones are tipped over"),
        0,
        "Obey flaggers and reduced speeds.",
    ),
    "Before you drive": _kit(
        (
            "Walk-around: tires, lights, obvious leaks.",
            "Inside: adjust mirrors and seat before moving.",
            "A warning light is on — you address it, not ignore it.",
        ),
        "Before moving the car you should:",
        (
            "Check brakes/lights/tires/mirrors and adjust your seat",
            "Start driving then fix mirrors at 40 mph",
            "Disable all warning lights with tape",
            "Skip checks if you drove yesterday",
        ),
        0,
        "Fix warning lights promptly.",
        game_steps=("Check tires and lights", "Adjust mirrors and seat", "Confirm brakes feel normal", "Then move"),
        game_kind="order_steps",
        game_prompt="Order a pre-drive check",
    ),
    "Handbook checkpoint": _kit(
        (
            "You re-open the handbook sections on signs and sharing the road.",
            "You trust official wording over a social-media tip.",
            "You note one section to review again tomorrow.",
        ),
        "The best authority for CA driving rules is:",
        (
            "The current California Driver's Handbook",
            "A random comment thread",
            "This studio track alone",
            "Outdated photocopies from 1998",
        ),
        0,
        "Official wording beats any study aid.",
    ),
    "Practice test habit": _kit(
        (
            "After a 15–20 minute block you take a short practice quiz.",
            "You come back later instead of cramming four hours straight.",
            "Missed items become tomorrow’s focus.",
        ),
        "A strong study pattern is:",
        (
            "Short blocks + practice quizzes + come back later",
            "One all-nighter before the exam only",
            "Skipping practice tests entirely",
            "Only reading road-sign memes",
        ),
        0,
        "Spaced practice beats marathon cramming.",
    ),
    "Prep card, not accreditation": _kit(
        (
            "You tell a coworker this studio is practice, not county-accredited training.",
            "You still complete your employer’s approved food handler course.",
            "You check Alameda Environmental Health guidance for local rules.",
        ),
        "This food-handler studio track is:",
        (
            "Practice only — not Alameda-accredited training",
            "Your official county card by itself",
            "A replacement for employer training",
            "A health inspection certificate",
        ),
        0,
        "Follow approved courses and county guidance.",
    ),
    "Why food handler cards matter": _kit(
        (
            "Many CA food employees must hold a valid food handler card.",
            "Inspectors check safe practices during visits.",
            "Your card shows you learned core safety habits.",
        ),
        "Food handler cards matter because:",
        (
            "California requires many food employees to hold a valid card; inspectors enforce practices",
            "They replace all cooking skills tests",
            "They let you ignore temperature rules",
            "They are optional artwork",
        ),
        0,
        "Local environmental health enforces safe practices.",
    ),
    "Handwashing that works": _kit(
        (
            "After the restroom you wash 20+ seconds with soap before returning to food.",
            "You handled raw chicken — wash again before salad prep.",
            "Sanitizer alone is not your substitute for washing.",
        ),
        "Effective handwashing is at least:",
        (
            "20 seconds with soap and warm water at the right times",
            "A quick rinse with cold water",
            "Sanitizer spray only",
            "Wiping hands on an apron",
        ),
        0,
        "Wash before food work, after restroom/raw meat/face/garbage, and when switching tasks.",
        game_steps=("Wet hands", "Soap 20+ seconds", "Rinse", "Dry with clean towel"),
        game_kind="order_steps",
        game_prompt="Order proper handwashing",
    ),
    "Gloves done right": _kit(
        (
            "Gloves tear — you change them and wash hands first.",
            "After raw protein you change gloves before ready-to-eat food.",
            "You never wash gloves instead of replacing them.",
        ),
        "Before putting on a new pair of gloves you should:",
        ("Wash your hands", "Rinse the old gloves and reuse them", "Sanitize dirty gloves in place", "Skip washing if you are busy"),
        0,
        "Change gloves when torn, dirty, after raw proteins, and before RTE foods.",
    ),
    "Illness reporting": _kit(
        (
            "You have diarrhea — you call out and tell your manager before your shift.",
            "Jaundice appears — you stay off food handling until cleared.",
            "Diagnosed norovirus — exclusion rules apply; you follow management.",
        ),
        "Before working you must report symptoms like:",
        (
            "Vomiting, diarrhea, jaundice, or sore throat with fever",
            "Mild boredom",
            "Hungry only",
            "Wanting a break",
        ),
        0,
        "Some diagnoses require exclusion — managers must follow the rules.",
    ),
    "Personal cleanliness": _kit(
        (
            "Hair restrained, clean apron, short clean nails.",
            "You take drinks only in the designated area, not over the make line.",
            "You remove jewelry that can trap soil.",
        ),
        "On the food line you should:",
        (
            "Wear clean clothes/apron, restrain hair, keep nails clean, avoid jewelry that traps soil",
            "Eat over open food when hungry",
            "Smoke in the prep area if near a window",
            "Skip hair restraints for short shifts",
        ),
        0,
        "Designated spots only for eating/drinking/smoking.",
    ),
    "Ready-to-eat foods": _kit(
        (
            "Sandwich assembly — you use gloves or tongs, not bare hands.",
            "You change gloves between raw prep and plating salad.",
            "Deli paper becomes your barrier when trained that way.",
        ),
        "Ready-to-eat foods usually require:",
        (
            "Barriers like gloves, tongs, or deli paper — not bare hands where rules require",
            "Bare hands for better feel",
            "No handwashing if gloves are nearby",
            "Only chef tasting fingers",
        ),
        0,
        "Follow your site’s bare-hand contact rules.",
    ),
    "Cuts and bandages": _kit(
        (
            "Finger cut — clean bandage, then glove over it.",
            "You cannot cover the wound properly — you stay off the line.",
            "Bandage gets wet — you replace it.",
        ),
        "A hand wound on the line should be:",
        (
            "Covered with a clean bandage and a glove over it",
            "Left open to “air out” near food",
            "Hidden under a towel",
            "Ignored if small",
        ),
        0,
        "Protect food from contamination — or step off the line.",
    ),
    "Customer allergen basics": _kit(
        (
            "Guest asks about sesame — you verify with the kitchen, never guess.",
            "You prevent cross-contact on shared utensils.",
            "You know the FDA Big 9 includes sesame.",
        ),
        "If a guest asks about allergens you should:",
        (
            "Check with the kitchen — never guess ingredients",
            "Say “probably fine” to keep them happy",
            "Ignore sesame because it is rare",
            "Offer a discount instead of answering",
        ),
        0,
        "Prevent cross-contact; accuracy matters.",
    ),
    "Your next short block": _kit(
        (
            "Next you study temperatures in another 15–20 minute session.",
            "You space contamination prevention across days.",
            "You return later instead of cramming tonight.",
        ),
        "Best way to continue food-handler prep:",
        (
            "Short spaced sessions on temps and contamination",
            "One 8-hour cram with no breaks",
            "Skip temperature control",
            "Only memorize quiz apps with no practice",
        ),
        0,
        "Spaced practice beats marathon cramming.",
    ),
    "Temperature danger zone": _kit(
        (
            "Food sits at 70°F on a counter — you know that is inside the danger zone.",
            "You limit time between 41°F and 135°F.",
            "You move TCS food through the zone quickly during prep.",
        ),
        "The temperature danger zone is generally:",
        ("41°F to 135°F", "0°F to 32°F", "140°F to 200°F only", "Room temperature is always safe"),
        0,
        "Bacteria grow fast in the danger zone — limit time there.",
    ),
    "Cold holding": _kit(
        (
            "Walk-in reads 38°F — cold TCS food is in range.",
            "Raw chicken stored below ready-to-eat salads.",
            "You check with a calibrated thermometer, not a guess.",
        ),
        "Cold TCS foods should be held at:",
        ("41°F or below", "55°F or below", "70°F", "135°F"),
        0,
        "Store raw animal foods below ready-to-eat items.",
    ),
    "Hot holding": _kit(
        (
            "Soup in a well holds at 140°F — acceptable hot holding.",
            "You do not use the steam table to reheat leftovers from cold.",
            "You check hot-holding temps during service.",
        ),
        "Hot TCS foods should be held at:",
        ("135°F or above", "41°F or above", "70°F", "Any warm setting"),
        0,
        "Reheat properly first — hot holding is not reheating.",
    ),
    "Safe cooking targets": _kit(
        (
            "Poultry checked in the thickest part hits 165°F.",
            "Ground beef reaches 155°F before service.",
            "You trust a thermometer, not color alone.",
        ),
        "Poultry should reach a minimum internal temperature of:",
        ("165°F", "145°F", "100°F", "41°F"),
        0,
        "Ground meats often 155°F; whole cuts/fish often 145°F with rest where required.",
    ),
    "Cooling cooked food": _kit(
        (
            "Chili cools 135→70°F within 2 hours in shallow pans.",
            "Then to 41°F within 4 more hours (6 total).",
            "You use an ice bath — not a deep stockpot on the counter.",
        ),
        "Cool from 135°F to 70°F within:",
        ("2 hours", "10 minutes", "24 hours", "No limit"),
        0,
        "Then to 41°F within 4 more hours — 6 hours total.",
        game_steps=("135°F to 70°F within 2 hours", "70°F to 41°F within 4 more hours", "Store properly labeled"),
        game_kind="order_steps",
        game_prompt="Order the cooling timeline",
    ),
    "Reheating": _kit(
        (
            "Leftover stew reheats to 165°F within 2 hours before hot holding.",
            "You do not rely on a steam table to reheat from cold.",
            "Microwave reheating is stirred and checked with a thermometer.",
        ),
        "Reheat previously cooked TCS food to:",
        ("165°F within 2 hours before hot holding", "110°F", "41°F", "Any simmer setting"),
        0,
        "Do not use slow cookers/steam tables as the reheat method from cold.",
    ),
    "Thawing safely": _kit(
        (
            "Chicken thaws in the refrigerator overnight.",
            "You use cold running water when needed, not the counter.",
            "Microwave thawing is followed by immediate cooking.",
        ),
        "Never thaw TCS food:",
        (
            "On the counter at room temperature",
            "In a refrigerator",
            "Under cold running water",
            "As part of cooking",
        ),
        0,
        "Fridge, cold water, microwave-then-cook, or cook from frozen.",
    ),
    "Receiving checks": _kit(
        (
            "Delivery arrives warm and damaged — you reject it.",
            "You keep the cold chain from dock to cooler.",
            "You check dates and pest evidence before signing.",
        ),
        "You should reject deliveries that are:",
        (
            "Too warm, damaged, pest-infested, or past safe dating",
            "On time and properly iced",
            "From your usual vendor only",
            "Labeled in English",
        ),
        0,
        "Protect the cold chain end to end.",
    ),
    "Date marking": _kit(
        (
            "Prepared RTE TCS food is labeled; day of prep is day 1.",
            "Typical refrigerated hold is about 7 days unless policy is stricter.",
            "Unlabeled mystery pan gets discarded, not served.",
        ),
        "Date marking for prepared RTE TCS food typically uses:",
        (
            "Day of prep as day 1 and a limited refrigerated hold (often 7 days)",
            "No labels if you remember",
            "Infinite storage if it smells fine",
            "Freezer dates only",
        ),
        0,
        "Follow your code/policy if stricter.",
    ),
    "Thermometer habits": _kit(
        (
            "You calibrate, clean, then probe the thickest part.",
            "You log temps when your site requires logs.",
            "A broken thermometer is replaced — not guessed around.",
        ),
        "When checking cook temps, probe:",
        ("The thickest part of the food", "Only the sauce on top", "The pan edge", "Steam above the food"),
        0,
        "Inspectors look for consistent temperature control.",
    ),
    "Cross-contamination": _kit(
        (
            "Raw chicken board is washed-rinsed-sanitized before cutting lettuce.",
            "Raw juices never drip onto ready-to-eat shelves.",
            "Color-coded boards separate raw and RTE tasks.",
        ),
        "To prevent cross-contamination:",
        (
            "Keep raw proteins separate; wash-rinse-sanitize between uses",
            "Use the same dirty board for everything to save time",
            "Wipe with a dry towel only",
            "Store raw meat above desserts",
        ),
        0,
        "Never let raw juices drip onto other foods.",
        game_steps=("Separate raw and RTE", "Wash with detergent", "Rinse", "Sanitize and air dry"),
        game_kind="order_steps",
        game_prompt="Order contamination control",
    ),
    "Clean then sanitize": _kit(
        (
            "You scrape, wash, rinse, sanitize, then air dry.",
            "Sanitizing a greasy surface without washing fails.",
            "You let items air dry instead of towel-recontaminating.",
        ),
        "Correct sequence is closest to:",
        (
            "Scrape → wash → rinse → sanitize → air dry",
            "Sanitize → wash → rinse",
            "Wipe → serve",
            "Rinse only",
        ),
        0,
        "Sanitizing dirty surfaces does not work.",
        game_steps=("Scrape", "Wash with detergent", "Rinse", "Sanitize", "Air dry"),
        game_kind="order_steps",
        game_prompt="Order clean-then-sanitize",
    ),
    "Sanitizer strength": _kit(
        (
            "You mix quat per label and verify with test strips.",
            "Cloudy weak solution — you replace it.",
            "You never guess concentration by smell.",
        ),
        "Verify sanitizer strength with:",
        ("Test strips (and replace weak/dirty solutions)", "Taste", "Guessing by color only", "Waiting for an inspection"),
        0,
        "Mix chlorine, quat, or iodine per label.",
    ),
    "FIFO stock rotation": _kit(
        (
            "New milk goes behind older milk.",
            "You use the oldest dated product first.",
            "Expired items are removed, not buried.",
        ),
        "FIFO means:",
        ("First In, First Out", "Fast In, Forget Out", "Fill In Freezer Only", "Fry Immediately For Output"),
        0,
        "New stock behind older product.",
    ),
    "Pest prevention": _kit(
        (
            "You seal gaps, store food sealed, and clean spills fast.",
            "Clutter that hides pests is removed.",
            "Licensed pest control handles treatments — you do not spray over food.",
        ),
        "For pests you should:",
        (
            "Seal, clean, store sealed food, and use licensed pest control",
            "Spray random pesticides over prep tables yourself",
            "Leave spills overnight",
            "Store open flour on the floor",
        ),
        0,
        "Do not spray pesticides over food areas yourself.",
    ),
    "Allergen cross-contact": _kit(
        (
            "Shared toaster used for allergen bread gets dedicated handling or deep cleaning.",
            "You communicate menu allergens accurately.",
            "You know cleaning alone may not remove residues.",
        ),
        "Allergen control often needs:",
        (
            "Dedicated handling, clean equipment, accurate communication",
            "A quick dry wipe only",
            "Guessing guest needs",
            "Ignoring sesame",
        ),
        0,
        "Cleaning alone may not remove allergen residues.",
    ),
    "Common pathogens": _kit(
        (
            "Poultry/eggs — Salmonella risk; cook and hygiene matter.",
            "Ground beef/produce — STEC risk awareness.",
            "Deli/RTE — Listeria; norovirus ties to hands/RTE.",
        ),
        "Control common pathogens with:",
        (
            "Hygiene plus proper cooking and holding",
            "Hoping food looks fine",
            "Skipping handwashing if gloves exist nearby",
            "Serving regardless of time/temperature abuse",
        ),
        0,
        "Know high-risk associations and control them.",
    ),
    "Health inspections": _kit(
        (
            "Inspector finds a critical violation — you fix it immediately.",
            "Logs are ready when asked.",
            "You ask a supervisor when unsure instead of guessing.",
        ),
        "During inspections you should:",
        (
            "Keep logs, fix critical problems immediately, ask supervisors when unsure",
            "Hide issues until they leave",
            "Argue medical science with the inspector",
            "Discard all logs",
        ),
        0,
        "Critical violations can cause illness — take them seriously.",
    ),
    "If a guest gets sick": _kit(
        (
            "Guest complains of illness — you notify a manager at once.",
            "You preserve suspected food if instructed.",
            "You cooperate; you do not diagnose or argue.",
        ),
        "If a guest reports illness you should:",
        (
            "Notify a manager, preserve food if told, cooperate with investigators",
            "Argue that the food was fine",
            "Ignore the complaint",
            "Offer only a free dessert and move on silently",
        ),
        0,
        "Do not guess medical causes.",
    ),
    "Finish strong": _kit(
        (
            "You finish your employer’s approved CA food handler course.",
            "You take the official assessment for your card.",
            "You treat this studio as practice only.",
        ),
        "To earn your card you should:",
        (
            "Complete approved training and the official assessment",
            "Only finish this studio track",
            "Skip the assessment if you feel ready",
            "Borrow a coworker’s card",
        ),
        0,
        "This studio track is practice only.",
    ),
    'Two-hour course map': _kit(
        (
            'On the line, you apply “Two-hour course map” before the next ticket leaves the pass.',
            'You coach a new hire: Plan about two hours across six modules: hygiene and illness; temperatures; contamination and allergens; cleaning and fa',
            'An inspector asks about “Two-hour course map” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Two-hour course map”?',
        (
            'Plan about two hours across six modules: hygiene and illness; temperatures; contamination and allergens; cleaning and fa',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Plan about two hours across six modules: hygiene and illness; temperatures; contamination and allergens; cleaning and facilities; pathogens and high-risk guests; receiving, storage, and service.',
    ),
    'Situation: After raw chicken': _kit(
        (
            'On the line, you apply “Situation: After raw chicken” before the next ticket leaves the pass.',
            'You coach a new hire: Example: You bread raw chicken, then need to plate a salad.',
            'An inspector asks about “Situation: After raw chicken” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: After raw chicken”?',
        (
            'Example: You bread raw chicken, then need to plate a salad.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: You bread raw chicken, then need to plate a salad.',
    ),
    'Situation: Back from break': _kit(
        (
            'On the line, you apply “Situation: Back from break” before the next ticket leaves the pass.',
            'You coach a new hire: Example: You return from break after using your phone and the restroom.',
            'An inspector asks about “Situation: Back from break” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Back from break”?',
        (
            'Example: You return from break after using your phone and the restroom.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: You return from break after using your phone and the restroom.',
    ),
    'Situation: Raw then sandwich': _kit(
        (
            'On the line, you apply “Situation: Raw then sandwich” before the next ticket leaves the pass.',
            'You coach a new hire: Example: You portion raw burger patties, then a ticket calls for a cold turkey sandwich.',
            'An inspector asks about “Situation: Raw then sandwich” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Raw then sandwich”?',
        (
            'Example: You portion raw burger patties, then a ticket calls for a cold turkey sandwich.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: You portion raw burger patties, then a ticket calls for a cold turkey sandwich.',
    ),
    'Bare-hand contact rules': _kit(
        (
            'On the line, you apply “Bare-hand contact rules” before the next ticket leaves the pass.',
            'You coach a new hire: Many California food operations restrict bare-hand contact with ready-to-eat foods.',
            'An inspector asks about “Bare-hand contact rules” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Bare-hand contact rules”?',
        (
            'Many California food operations restrict bare-hand contact with ready-to-eat foods.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Many California food operations restrict bare-hand contact with ready-to-eat foods.',
    ),
    'Situation: Morning stomach flu': _kit(
        (
            'On the line, you apply “Situation: Morning stomach flu” before the next ticket leaves the pass.',
            'You coach a new hire: Example: You wake up with diarrhea and feel weak but need the shift.',
            'An inspector asks about “Situation: Morning stomach flu” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Morning stomach flu”?',
        (
            'Example: You wake up with diarrhea and feel weak but need the shift.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: You wake up with diarrhea and feel weak but need the shift.',
    ),
    'Big Six and exclusion': _kit(
        (
            'On the line, you apply “Big Six and exclusion” before the next ticket leaves the pass.',
            'You coach a new hire: Managers follow exclusion and restriction rules for the Big Six: norovirus, hepatitis A, Salmonella Typhi, nontyphoidal ',
            'An inspector asks about “Big Six and exclusion” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Big Six and exclusion”?',
        (
            'Managers follow exclusion and restriction rules for the Big Six: norovirus, hepatitis A, Salmonella Typhi, nontyphoidal ',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Managers follow exclusion and restriction rules for the Big Six: norovirus, hepatitis A, Salmonella Typhi, nontyphoidal Salmonella, Shigella, and Shiga toxin-producing E.',
    ),
    'Hair, nails, and jewelry': _kit(
        (
            'On the line, you apply “Hair, nails, and jewelry” before the next ticket leaves the pass.',
            'You coach a new hire: Hair restraints — hats, nets, or wraps — keep hair out of food.',
            'An inspector asks about “Hair, nails, and jewelry” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Hair, nails, and jewelry”?',
        (
            'Hair restraints — hats, nets, or wraps — keep hair out of food.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Hair restraints — hats, nets, or wraps — keep hair out of food.',
    ),
    'Situation: Cut finger on the line': _kit(
        (
            'On the line, you apply “Situation: Cut finger on the line” before the next ticket leaves the pass.',
            'You coach a new hire: Example: A knife nick bleeds during prep.',
            'An inspector asks about “Situation: Cut finger on the line” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Cut finger on the line”?',
        (
            'Example: A knife nick bleeds during prep.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: A knife nick bleeds during prep.',
    ),
    'Situation: Guest nut allergy': _kit(
        (
            'On the line, you apply “Situation: Guest nut allergy” before the next ticket leaves the pass.',
            'You coach a new hire: Example: A guest says they have a severe tree-nut allergy.',
            'An inspector asks about “Situation: Guest nut allergy” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Guest nut allergy”?',
        (
            'Example: A guest says they have a severe tree-nut allergy.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: A guest says they have a severe tree-nut allergy.',
    ),
    'Module wrap — hygiene': _kit(
        (
            'On the line, you apply “Module wrap — hygiene” before the next ticket leaves the pass.',
            'You coach a new hire: You covered handwashing, gloves, illness reporting, personal cleanliness, wounds, ready-to-eat barriers, and allergens —',
            'An inspector asks about “Module wrap — hygiene” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Module wrap — hygiene”?',
        (
            'You covered handwashing, gloves, illness reporting, personal cleanliness, wounds, ready-to-eat barriers, and allergens —',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'You covered handwashing, gloves, illness reporting, personal cleanliness, wounds, ready-to-eat barriers, and allergens — the foundation of a two-hour food handler prep.',
    ),
    'What counts as TCS food': _kit(
        (
            'On the line, you apply “What counts as TCS food” before the next ticket leaves the pass.',
            'You coach a new hire: TCS foods need time and temperature control: milk and dairy, meat, poultry, seafood, cooked vegetables and grains, cut m',
            'An inspector asks about “What counts as TCS food” — you point to the station and explain the control.',
        ),
        'Which choice best matches “What counts as TCS food”?',
        (
            'TCS foods need time and temperature control: milk and dairy, meat, poultry, seafood, cooked vegetables and grains, cut m',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'TCS foods need time and temperature control: milk and dairy, meat, poultry, seafood, cooked vegetables and grains, cut melons and leafy greens, sprouts, garlic-in-oil, and many leftovers.',
    ),
    'Situation: Walk-in at 48°F': _kit(
        (
            'On the line, you apply “Situation: Walk-in at 48°F” before the next ticket leaves the pass.',
            'You coach a new hire: Example: The walk-in thermometer reads 48°F at open.',
            'An inspector asks about “Situation: Walk-in at 48°F” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Walk-in at 48°F”?',
        (
            'Example: The walk-in thermometer reads 48°F at open.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: The walk-in thermometer reads 48°F at open.',
    ),
    'Situation: Steam table drops': _kit(
        (
            'On the line, you apply “Situation: Steam table drops” before the next ticket leaves the pass.',
            'You coach a new hire: Example: Soup in a steam table reads 128°F.',
            'An inspector asks about “Situation: Steam table drops” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Steam table drops”?',
        (
            'Example: Soup in a steam table reads 128°F.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: Soup in a steam table reads 128°F.',
    ),
    'Cooking poultry to 165°F': _kit(
        (
            'On the line, you apply “Cooking poultry to 165°F” before the next ticket leaves the pass.',
            'You coach a new hire: Poultry — chicken, turkey, duck — and stuffed foods generally need a minimum internal temperature of 165°F.',
            'An inspector asks about “Cooking poultry to 165°F” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Cooking poultry to 165°F”?',
        (
            'Poultry — chicken, turkey, duck — and stuffed foods generally need a minimum internal temperature of 165°F.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Poultry — chicken, turkey, duck — and stuffed foods generally need a minimum internal temperature of 165°F.',
    ),
    'Ground meats to 155°F': _kit(
        (
            'On the line, you apply “Ground meats to 155°F” before the next ticket leaves the pass.',
            'You coach a new hire: Ground meats such as beef, pork, and other comminuted meats commonly require 155°F for a specified time (or hotter for l',
            'An inspector asks about “Ground meats to 155°F” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Ground meats to 155°F”?',
        (
            'Ground meats such as beef, pork, and other comminuted meats commonly require 155°F for a specified time (or hotter for l',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Ground meats such as beef, pork, and other comminuted meats commonly require 155°F for a specified time (or hotter for less time per the code chart).',
    ),
    'Whole cuts and fish 145°F': _kit(
        (
            'On the line, you apply “Whole cuts and fish 145°F” before the next ticket leaves the pass.',
            'You coach a new hire: Whole cuts of beef, pork, lamb, and fish often target 145°F with a rest time where required.',
            'An inspector asks about “Whole cuts and fish 145°F” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Whole cuts and fish 145°F”?',
        (
            'Whole cuts of beef, pork, lamb, and fish often target 145°F with a rest time where required.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Whole cuts of beef, pork, lamb, and fish often target 145°F with a rest time where required.',
    ),
    'Situation: Checking a burger': _kit(
        (
            'On the line, you apply “Situation: Checking a burger” before the next ticket leaves the pass.',
            'You coach a new hire: Example: A guest wants a burger “pink in the middle.” Your restaurant policy and local code decide whether undercooked g',
            'An inspector asks about “Situation: Checking a burger” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Checking a burger”?',
        (
            'Example: A guest wants a burger “pink in the middle.” Your restaurant policy and local code decide whether undercooked g',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: A guest wants a burger “pink in the middle.” Your restaurant policy and local code decide whether undercooked ground beef can be served and what consumer advisory is required.',
    ),
    'Situation: Deep pot of chili': _kit(
        (
            'On the line, you apply “Situation: Deep pot of chili” before the next ticket leaves the pass.',
            'You coach a new hire: Example: A twenty-quart pot of chili sits on a prep table to “cool.” The center stays hot for hours while the danger zon',
            'An inspector asks about “Situation: Deep pot of chili” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Deep pot of chili”?',
        (
            'Example: A twenty-quart pot of chili sits on a prep table to “cool.” The center stays hot for hours while the danger zon',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: A twenty-quart pot of chili sits on a prep table to “cool.” The center stays hot for hours while the danger zone breeds bacteria and toxins.',
    ),
    'Reheating leftovers': _kit(
        (
            'On the line, you apply “Reheating leftovers” before the next ticket leaves the pass.',
            'You coach a new hire: Reheat previously cooked TCS food to 165°F within two hours before hot holding.',
            'An inspector asks about “Reheating leftovers” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Reheating leftovers”?',
        (
            'Reheat previously cooked TCS food to 165°F within two hours before hot holding.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Reheat previously cooked TCS food to 165°F within two hours before hot holding.',
    ),
    'Situation: Chicken on the counter': _kit(
        (
            'On the line, you apply “Situation: Chicken on the counter” before the next ticket leaves the pass.',
            'You coach a new hire: Example: Frozen chicken sits in a bus tub on the prep counter “so it thaws faster.” Stop the practice.',
            'An inspector asks about “Situation: Chicken on the counter” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Chicken on the counter”?',
        (
            'Example: Frozen chicken sits in a bus tub on the prep counter “so it thaws faster.” Stop the practice.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: Frozen chicken sits in a bus tub on the prep counter “so it thaws faster.” Stop the practice.',
    ),
    'Receiving temperature checks': _kit(
        (
            'On the line, you apply “Receiving temperature checks” before the next ticket leaves the pass.',
            'You coach a new hire: Check cold deliveries with a thermometer: refrigerated foods generally 41°F or below, frozen foods solidly frozen.',
            'An inspector asks about “Receiving temperature checks” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Receiving temperature checks”?',
        (
            'Check cold deliveries with a thermometer: refrigerated foods generally 41°F or below, frozen foods solidly frozen.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Check cold deliveries with a thermometer: refrigerated foods generally 41°F or below, frozen foods solidly frozen.',
    ),
    'Time as a public health control': _kit(
        (
            'On the line, you apply “Time as a public health control” before the next ticket leaves the pass.',
            'You coach a new hire: Some operations use time alone for pizza, sushi rice, or buffet items under written procedures — typically up to four ho',
            'An inspector asks about “Time as a public health control” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Time as a public health control”?',
        (
            'Some operations use time alone for pizza, sushi rice, or buffet items under written procedures — typically up to four ho',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Some operations use time alone for pizza, sushi rice, or buffet items under written procedures — typically up to four hours from leaving temperature control, then discard.',
    ),
    'Module wrap — temperatures': _kit(
        (
            'On the line, you apply “Module wrap — temperatures” before the next ticket leaves the pass.',
            'You coach a new hire: You practiced danger zone, TCS, cold and hot holding, cook temps, cooling, reheating, thawing, receiving, date marks, an',
            'An inspector asks about “Module wrap — temperatures” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Module wrap — temperatures”?',
        (
            'You practiced danger zone, TCS, cold and hot holding, cook temps, cooling, reheating, thawing, receiving, date marks, an',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'You practiced danger zone, TCS, cold and hot holding, cook temps, cooling, reheating, thawing, receiving, date marks, and thermometers.',
    ),
    'Cross-contamination basics': _kit(
        (
            'On the line, you apply “Cross-contamination basics” before the next ticket leaves the pass.',
            'You coach a new hire: Cross-contamination spreads pathogens from raw foods, dirty surfaces, cloths, or hands onto ready-to-eat foods.',
            'An inspector asks about “Cross-contamination basics” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Cross-contamination basics”?',
        (
            'Cross-contamination spreads pathogens from raw foods, dirty surfaces, cloths, or hands onto ready-to-eat foods.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Cross-contamination spreads pathogens from raw foods, dirty surfaces, cloths, or hands onto ready-to-eat foods.',
    ),
    'Color-coded boards and tools': _kit(
        (
            'On the line, you apply “Color-coded boards and tools” before the next ticket leaves the pass.',
            'You coach a new hire: Many kitchens use color-coded boards — for example red for raw meat, yellow for raw poultry, green for produce, blue for',
            'An inspector asks about “Color-coded boards and tools” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Color-coded boards and tools”?',
        (
            'Many kitchens use color-coded boards — for example red for raw meat, yellow for raw poultry, green for produce, blue for',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Many kitchens use color-coded boards — for example red for raw meat, yellow for raw poultry, green for produce, blue for seafood, white for dairy or bakery.',
    ),
    'Situation: Same knife raw then RTE': _kit(
        (
            'On the line, you apply “Situation: Same knife raw then RTE” before the next ticket leaves the pass.',
            'You coach a new hire: Example: A cook slices raw chicken, wipes the knife on an apron, and cuts tomatoes for salsa.',
            'An inspector asks about “Situation: Same knife raw then RTE” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Same knife raw then RTE”?',
        (
            'Example: A cook slices raw chicken, wipes the knife on an apron, and cuts tomatoes for salsa.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: A cook slices raw chicken, wipes the knife on an apron, and cuts tomatoes for salsa.',
    ),
    'Sanitizer strength and strips': _kit(
        (
            'On the line, you apply “Sanitizer strength and strips” before the next ticket leaves the pass.',
            'You coach a new hire: Mix sanitizer per label.',
            'An inspector asks about “Sanitizer strength and strips” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Sanitizer strength and strips”?',
        (
            'Mix sanitizer per label.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Mix sanitizer per label.',
    ),
    'Situation: Cloudy sanitizer bucket': _kit(
        (
            'On the line, you apply “Situation: Cloudy sanitizer bucket” before the next ticket leaves the pass.',
            'You coach a new hire: Example: The sanitizer bucket is cloudy with food bits and a strip reads under range.',
            'An inspector asks about “Situation: Cloudy sanitizer bucket” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Cloudy sanitizer bucket”?',
        (
            'Example: The sanitizer bucket is cloudy with food bits and a strip reads under range.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: The sanitizer bucket is cloudy with food bits and a strip reads under range.',
    ),
    'Situation: Droppings in dry storage': _kit(
        (
            'On the line, you apply “Situation: Droppings in dry storage” before the next ticket leaves the pass.',
            'You coach a new hire: Example: You find rodent droppings near flour bags.',
            'An inspector asks about “Situation: Droppings in dry storage” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Droppings in dry storage”?',
        (
            'Example: You find rodent droppings near flour bags.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: You find rodent droppings near flour bags.',
    ),
    'FDA Big 9 list': _kit(
        (
            'On the line, you apply “FDA Big 9 list” before the next ticket leaves the pass.',
            'You coach a new hire: Memorize the Big 9: milk, eggs, fish, Crustacean shellfish, tree nuts, peanuts, wheat, soybeans, and sesame.',
            'An inspector asks about “FDA Big 9 list” — you point to the station and explain the control.',
        ),
        'Which choice best matches “FDA Big 9 list”?',
        (
            'Memorize the Big 9: milk, eggs, fish, Crustacean shellfish, tree nuts, peanuts, wheat, soybeans, and sesame.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Memorize the Big 9: milk, eggs, fish, Crustacean shellfish, tree nuts, peanuts, wheat, soybeans, and sesame.',
    ),
    'Situation: Shared fryer allergen': _kit(
        (
            'On the line, you apply “Situation: Shared fryer allergen” before the next ticket leaves the pass.',
            'You coach a new hire: Example: French fries share oil with breaded shrimp.',
            'An inspector asks about “Situation: Shared fryer allergen” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Shared fryer allergen”?',
        (
            'Example: French fries share oil with breaded shrimp.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: French fries share oil with breaded shrimp.',
    ),
    'Chemical contamination': _kit(
        (
            'On the line, you apply “Chemical contamination” before the next ticket leaves the pass.',
            'You coach a new hire: Store chemicals below and away from food, utensils, and linens.',
            'An inspector asks about “Chemical contamination” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Chemical contamination”?',
        (
            'Store chemicals below and away from food, utensils, and linens.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Store chemicals below and away from food, utensils, and linens.',
    ),
    'Physical hazards': _kit(
        (
            'On the line, you apply “Physical hazards” before the next ticket leaves the pass.',
            'You coach a new hire: Glass, metal shards, bones, plastic, bandages, and jewelry can injure guests.',
            'An inspector asks about “Physical hazards” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Physical hazards”?',
        (
            'Glass, metal shards, bones, plastic, bandages, and jewelry can injure guests.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Glass, metal shards, bones, plastic, bandages, and jewelry can injure guests.',
    ),
    'Common pathogens overview': _kit(
        (
            'On the line, you apply “Common pathogens overview” before the next ticket leaves the pass.',
            'You coach a new hire: Salmonella links to poultry and eggs; STEC to ground beef and produce; Listeria to deli and cold ready-to-eat foods; nor',
            'An inspector asks about “Common pathogens overview” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Common pathogens overview”?',
        (
            'Salmonella links to poultry and eggs; STEC to ground beef and produce; Listeria to deli and cold ready-to-eat foods; nor',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Salmonella links to poultry and eggs; STEC to ground beef and produce; Listeria to deli and cold ready-to-eat foods; norovirus to hands and ready-to-eat foods; Campylobacter to undercooked poultry.',
    ),
    'Produce washing': _kit(
        (
            'On the line, you apply “Produce washing” before the next ticket leaves the pass.',
            'You coach a new hire: Wash fruits and vegetables under running water before cutting, even if you peel them — knives carry surface soil into th',
            'An inspector asks about “Produce washing” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Produce washing”?',
        (
            'Wash fruits and vegetables under running water before cutting, even if you peel them — knives carry surface soil into th',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Wash fruits and vegetables under running water before cutting, even if you peel them — knives carry surface soil into the flesh.',
    ),
    'Situation: Inspector at the door': _kit(
        (
            'On the line, you apply “Situation: Inspector at the door” before the next ticket leaves the pass.',
            'You coach a new hire: Example: An inspector arrives during lunch rush.',
            'An inspector asks about “Situation: Inspector at the door” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Inspector at the door”?',
        (
            'Example: An inspector arrives during lunch rush.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: An inspector arrives during lunch rush.',
    ),
    'Module wrap — contamination': _kit(
        (
            'On the line, you apply “Module wrap — contamination” before the next ticket leaves the pass.',
            'You coach a new hire: You covered cross-contamination, cleaning and sanitizing, FIFO, pests, allergens, chemicals, physical hazards, pathogens',
            'An inspector asks about “Module wrap — contamination” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Module wrap — contamination”?',
        (
            'You covered cross-contamination, cleaning and sanitizing, FIFO, pests, allergens, chemicals, physical hazards, pathogens',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'You covered cross-contamination, cleaning and sanitizing, FIFO, pests, allergens, chemicals, physical hazards, pathogens, produce, and inspections.',
    ),
    'Why cleaning is food safety': _kit(
        (
            'On the line, you apply “Why cleaning is food safety” before the next ticket leaves the pass.',
            'You coach a new hire: Cleaning removes soil; sanitizing reduces pathogens on already clean surfaces.',
            'An inspector asks about “Why cleaning is food safety” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Why cleaning is food safety”?',
        (
            'Cleaning removes soil; sanitizing reduces pathogens on already clean surfaces.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Cleaning removes soil; sanitizing reduces pathogens on already clean surfaces.',
    ),
    'Three-compartment sink': _kit(
        (
            'On the line, you apply “Three-compartment sink” before the next ticket leaves the pass.',
            'You coach a new hire: Typical setup: wash (detergent, hot water), rinse (clean water), sanitize (correct ppm and contact time), then air dry.',
            'An inspector asks about “Three-compartment sink” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Three-compartment sink”?',
        (
            'Typical setup: wash (detergent, hot water), rinse (clean water), sanitize (correct ppm and contact time), then air dry.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Typical setup: wash (detergent, hot water), rinse (clean water), sanitize (correct ppm and contact time), then air dry.',
    ),
    'Dishmachine basics': _kit(
        (
            'On the line, you apply “Dishmachine basics” before the next ticket leaves the pass.',
            'You coach a new hire: Follow the machine’s temperature or chemical sanitizing requirements.',
            'An inspector asks about “Dishmachine basics” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Dishmachine basics”?',
        (
            'Follow the machine’s temperature or chemical sanitizing requirements.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Follow the machine’s temperature or chemical sanitizing requirements.',
    ),
    'Food-contact surfaces': _kit(
        (
            'On the line, you apply “Food-contact surfaces” before the next ticket leaves the pass.',
            'You coach a new hire: Food-contact surfaces — boards, knives, prep tables, slicer parts, thermometer probes — need wash, rinse, sanitize betwe',
            'An inspector asks about “Food-contact surfaces” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Food-contact surfaces”?',
        (
            'Food-contact surfaces — boards, knives, prep tables, slicer parts, thermometer probes — need wash, rinse, sanitize betwe',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Food-contact surfaces — boards, knives, prep tables, slicer parts, thermometer probes — need wash, rinse, sanitize between raw and ready-to-eat uses and on a schedule during continuous use.',
    ),
    'Situation: After raw fish prep': _kit(
        (
            'On the line, you apply “Situation: After raw fish prep” before the next ticket leaves the pass.',
            'You coach a new hire: Example: You finish butchering raw fish on a table that will next hold garnishes.',
            'An inspector asks about “Situation: After raw fish prep” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: After raw fish prep”?',
        (
            'Example: You finish butchering raw fish on a table that will next hold garnishes.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: You finish butchering raw fish on a table that will next hold garnishes.',
    ),
    'Wiping cloths': _kit(
        (
            'On the line, you apply “Wiping cloths” before the next ticket leaves the pass.',
            'You coach a new hire: Store wiping cloths in sanitizer solution between uses.',
            'An inspector asks about “Wiping cloths” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Wiping cloths”?',
        (
            'Store wiping cloths in sanitizer solution between uses.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Store wiping cloths in sanitizer solution between uses.',
    ),
    'Situation: Cloth left overnight': _kit(
        (
            'On the line, you apply “Situation: Cloth left overnight” before the next ticket leaves the pass.',
            'You coach a new hire: Example: A wet towel sits on a cutting board all night.',
            'An inspector asks about “Situation: Cloth left overnight” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Cloth left overnight”?',
        (
            'Example: A wet towel sits on a cutting board all night.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: A wet towel sits on a cutting board all night.',
    ),
    'Handwashing sinks stay dedicated': _kit(
        (
            'On the line, you apply “Handwashing sinks stay dedicated” before the next ticket leaves the pass.',
            'You coach a new hire: Handwashing sinks need soap, towels or dryers, warm water, and clear access.',
            'An inspector asks about “Handwashing sinks stay dedicated” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Handwashing sinks stay dedicated”?',
        (
            'Handwashing sinks need soap, towels or dryers, warm water, and clear access.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Handwashing sinks need soap, towels or dryers, warm water, and clear access.',
    ),
    'Situation: Mop water in hand sink': _kit(
        (
            'On the line, you apply “Situation: Mop water in hand sink” before the next ticket leaves the pass.',
            'You coach a new hire: Example: Someone dumps mop water in the handwashing sink during rush.',
            'An inspector asks about “Situation: Mop water in hand sink” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Mop water in hand sink”?',
        (
            'Example: Someone dumps mop water in the handwashing sink during rush.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: Someone dumps mop water in the handwashing sink during rush.',
    ),
    'Floors, walls, ceilings': _kit(
        (
            'On the line, you apply “Floors, walls, ceilings” before the next ticket leaves the pass.',
            'You coach a new hire: Clean floors regularly so grease and food debris do not attract pests.',
            'An inspector asks about “Floors, walls, ceilings” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Floors, walls, ceilings”?',
        (
            'Clean floors regularly so grease and food debris do not attract pests.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Clean floors regularly so grease and food debris do not attract pests.',
    ),
    'Restroom readiness': _kit(
        (
            'On the line, you apply “Restroom readiness” before the next ticket leaves the pass.',
            'You coach a new hire: Employee and guest restrooms need soap, towels or dryers, hot water, and regular cleaning.',
            'An inspector asks about “Restroom readiness” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Restroom readiness”?',
        (
            'Employee and guest restrooms need soap, towels or dryers, hot water, and regular cleaning.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Employee and guest restrooms need soap, towels or dryers, hot water, and regular cleaning.',
    ),
    'Garbage and grease': _kit(
        (
            'On the line, you apply “Garbage and grease” before the next ticket leaves the pass.',
            'You coach a new hire: Empty garbage before it overflows.',
            'An inspector asks about “Garbage and grease” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Garbage and grease”?',
        (
            'Empty garbage before it overflows.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Empty garbage before it overflows.',
    ),
    'Water and ice safety': _kit(
        (
            'On the line, you apply “Water and ice safety” before the next ticket leaves the pass.',
            'You coach a new hire: Use potable water for food and ice.',
            'An inspector asks about “Water and ice safety” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Water and ice safety”?',
        (
            'Use potable water for food and ice.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Use potable water for food and ice.',
    ),
    'Chemical storage': _kit(
        (
            'On the line, you apply “Chemical storage” before the next ticket leaves the pass.',
            'You coach a new hire: Keep cleaners and sanitizers in labeled bottles, stored away from food and single-use items.',
            'An inspector asks about “Chemical storage” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Chemical storage”?',
        (
            'Keep cleaners and sanitizers in labeled bottles, stored away from food and single-use items.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Keep cleaners and sanitizers in labeled bottles, stored away from food and single-use items.',
    ),
    'Situation: Bleach beside flour': _kit(
        (
            'On the line, you apply “Situation: Bleach beside flour” before the next ticket leaves the pass.',
            'You coach a new hire: Example: A bottle of bleach concentrate sits on a dry-storage shelf beside open flour.',
            'An inspector asks about “Situation: Bleach beside flour” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Bleach beside flour”?',
        (
            'Example: A bottle of bleach concentrate sits on a dry-storage shelf beside open flour.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: A bottle of bleach concentrate sits on a dry-storage shelf beside open flour.',
    ),
    'Clean-in-place equipment': _kit(
        (
            'On the line, you apply “Clean-in-place equipment” before the next ticket leaves the pass.',
            'You coach a new hire: Slicers, mixers, and soft-serve machines need disassembly per manufacturer instructions.',
            'An inspector asks about “Clean-in-place equipment” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Clean-in-place equipment”?',
        (
            'Slicers, mixers, and soft-serve machines need disassembly per manufacturer instructions.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Slicers, mixers, and soft-serve machines need disassembly per manufacturer instructions.',
    ),
    'Closing cleaning checklist': _kit(
        (
            'On the line, you apply “Closing cleaning checklist” before the next ticket leaves the pass.',
            'You coach a new hire: Closing is when many contamination problems start: crumb-filled toasters, dirty pop nozzles, greasy hoods, and uncovered',
            'An inspector asks about “Closing cleaning checklist” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Closing cleaning checklist”?',
        (
            'Closing is when many contamination problems start: crumb-filled toasters, dirty pop nozzles, greasy hoods, and uncovered',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Closing is when many contamination problems start: crumb-filled toasters, dirty pop nozzles, greasy hoods, and uncovered food.',
    ),
    'Who cleans what': _kit(
        (
            'On the line, you apply “Who cleans what” before the next ticket leaves the pass.',
            'You coach a new hire: Line cooks sanitize their stations; dishwashers own warewashing; managers verify chemical strength and machine temps.',
            'An inspector asks about “Who cleans what” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Who cleans what”?',
        (
            'Line cooks sanitize their stations; dishwashers own warewashing; managers verify chemical strength and machine temps.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Line cooks sanitize their stations; dishwashers own warewashing; managers verify chemical strength and machine temps.',
    ),
    'Ventilation and grease': _kit(
        (
            'On the line, you apply “Ventilation and grease” before the next ticket leaves the pass.',
            'You coach a new hire: Grease-laden vapor coats hoods and walls.',
            'An inspector asks about “Ventilation and grease” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Ventilation and grease”?',
        (
            'Grease-laden vapor coats hoods and walls.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Grease-laden vapor coats hoods and walls.',
    ),
    'Module wrap — cleaning': _kit(
        (
            'On the line, you apply “Module wrap — cleaning” before the next ticket leaves the pass.',
            'You coach a new hire: You covered warewashing, food-contact surfaces, cloths, hand sinks, facilities, ice, chemicals, equipment, and closing r',
            'An inspector asks about “Module wrap — cleaning” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Module wrap — cleaning”?',
        (
            'You covered warewashing, food-contact surfaces, cloths, hand sinks, facilities, ice, chemicals, equipment, and closing r',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'You covered warewashing, food-contact surfaces, cloths, hand sinks, facilities, ice, chemicals, equipment, and closing routines.',
    ),
    'How people get sick from food': _kit(
        (
            'On the line, you apply “How people get sick from food” before the next ticket leaves the pass.',
            'You coach a new hire: Foodborne illness comes from biological hazards (bacteria, viruses, parasites), chemical hazards, and physical hazards.',
            'An inspector asks about “How people get sick from food” — you point to the station and explain the control.',
        ),
        'Which choice best matches “How people get sick from food”?',
        (
            'Foodborne illness comes from biological hazards (bacteria, viruses, parasites), chemical hazards, and physical hazards.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Foodborne illness comes from biological hazards (bacteria, viruses, parasites), chemical hazards, and physical hazards.',
    ),
    'Bacteria, viruses, parasites, toxins': _kit(
        (
            'On the line, you apply “Bacteria, viruses, parasites, toxins” before the next ticket leaves the pass.',
            'You coach a new hire: Bacteria can grow in food when FAT TOM conditions allow.',
            'An inspector asks about “Bacteria, viruses, parasites, toxins” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Bacteria, viruses, parasites, toxins”?',
        (
            'Bacteria can grow in food when FAT TOM conditions allow.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Bacteria can grow in food when FAT TOM conditions allow.',
    ),
    'Norovirus deep dive': _kit(
        (
            'On the line, you apply “Norovirus deep dive” before the next ticket leaves the pass.',
            'You coach a new hire: Norovirus is highly contagious and a leading cause of foodborne illness from infected food handlers.',
            'An inspector asks about “Norovirus deep dive” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Norovirus deep dive”?',
        (
            'Norovirus is highly contagious and a leading cause of foodborne illness from infected food handlers.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Norovirus is highly contagious and a leading cause of foodborne illness from infected food handlers.',
    ),
    'Salmonella': _kit(
        (
            'On the line, you apply “Salmonella” before the next ticket leaves the pass.',
            'You coach a new hire: Salmonella is linked to poultry, eggs, and produce.',
            'An inspector asks about “Salmonella” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Salmonella”?',
        (
            'Salmonella is linked to poultry, eggs, and produce.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Salmonella is linked to poultry, eggs, and produce.',
    ),
    'STEC and ground beef': _kit(
        (
            'On the line, you apply “STEC and ground beef” before the next ticket leaves the pass.',
            'You coach a new hire: Shiga toxin-producing E.',
            'An inspector asks about “STEC and ground beef” — you point to the station and explain the control.',
        ),
        'Which choice best matches “STEC and ground beef”?',
        (
            'Shiga toxin-producing E.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Shiga toxin-producing E.',
    ),
    'Listeria and cold RTE foods': _kit(
        (
            'On the line, you apply “Listeria and cold RTE foods” before the next ticket leaves the pass.',
            'You coach a new hire: Listeria monocytogenes can grow at refrigerator temperatures and is linked to deli meats, soft cheeses, and cold ready-t',
            'An inspector asks about “Listeria and cold RTE foods” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Listeria and cold RTE foods”?',
        (
            'Listeria monocytogenes can grow at refrigerator temperatures and is linked to deli meats, soft cheeses, and cold ready-t',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Listeria monocytogenes can grow at refrigerator temperatures and is linked to deli meats, soft cheeses, and cold ready-to-eat foods.',
    ),
    'Hepatitis A': _kit(
        (
            'On the line, you apply “Hepatitis A” before the next ticket leaves the pass.',
            'You coach a new hire: Hepatitis A spreads from infected workers to food, especially ready-to-eat items.',
            'An inspector asks about “Hepatitis A” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Hepatitis A”?',
        (
            'Hepatitis A spreads from infected workers to food, especially ready-to-eat items.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Hepatitis A spreads from infected workers to food, especially ready-to-eat items.',
    ),
    'Clostridium botulinum': _kit(
        (
            'On the line, you apply “Clostridium botulinum” before the next ticket leaves the pass.',
            'You coach a new hire: Botulism links to improper canning, reduced-oxygen packaging, and garlic-in-oil held warm.',
            'An inspector asks about “Clostridium botulinum” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Clostridium botulinum”?',
        (
            'Botulism links to improper canning, reduced-oxygen packaging, and garlic-in-oil held warm.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Botulism links to improper canning, reduced-oxygen packaging, and garlic-in-oil held warm.',
    ),
    'Clostridium perfringens': _kit(
        (
            'On the line, you apply “Clostridium perfringens” before the next ticket leaves the pass.',
            'You coach a new hire: Perfringens thrives when large batches of meat stews and gravies cool too slowly.',
            'An inspector asks about “Clostridium perfringens” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Clostridium perfringens”?',
        (
            'Perfringens thrives when large batches of meat stews and gravies cool too slowly.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Perfringens thrives when large batches of meat stews and gravies cool too slowly.',
    ),
    'Staphylococcus aureus': _kit(
        (
            'On the line, you apply “Staphylococcus aureus” before the next ticket leaves the pass.',
            'You coach a new hire: Staph toxins come from infected cuts and hands; toxin can survive reheating.',
            'An inspector asks about “Staphylococcus aureus” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Staphylococcus aureus”?',
        (
            'Staph toxins come from infected cuts and hands; toxin can survive reheating.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Staph toxins come from infected cuts and hands; toxin can survive reheating.',
    ),
    'High-risk populations': _kit(
        (
            'On the line, you apply “High-risk populations” before the next ticket leaves the pass.',
            'You coach a new hire: Young children, older adults, pregnant people, and immunocompromised guests get sicker from the same pathogens.',
            'An inspector asks about “High-risk populations” — you point to the station and explain the control.',
        ),
        'Which choice best matches “High-risk populations”?',
        (
            'Young children, older adults, pregnant people, and immunocompromised guests get sicker from the same pathogens.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Young children, older adults, pregnant people, and immunocompromised guests get sicker from the same pathogens.',
    ),
    'Situation: Nursing home catering': _kit(
        (
            'On the line, you apply “Situation: Nursing home catering” before the next ticket leaves the pass.',
            'You coach a new hire: Example: Your restaurant caters a nursing home lunch.',
            'An inspector asks about “Situation: Nursing home catering” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Nursing home catering”?',
        (
            'Example: Your restaurant caters a nursing home lunch.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: Your restaurant caters a nursing home lunch.',
    ),
    'Symptoms to take seriously': _kit(
        (
            'On the line, you apply “Symptoms to take seriously” before the next ticket leaves the pass.',
            'You coach a new hire: Vomiting, diarrhea, fever, jaundice, and severe cramps after a meal may signal foodborne illness — but many causes exist',
            'An inspector asks about “Symptoms to take seriously” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Symptoms to take seriously”?',
        (
            'Vomiting, diarrhea, fever, jaundice, and severe cramps after a meal may signal foodborne illness — but many causes exist',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Vomiting, diarrhea, fever, jaundice, and severe cramps after a meal may signal foodborne illness — but many causes exist.',
    ),
    'Outbreak response basics': _kit(
        (
            'On the line, you apply “Outbreak response basics” before the next ticket leaves the pass.',
            'You coach a new hire: If multiple guests report illness, management may preserve samples, pull menu items, deepen cleaning, and cooperate with',
            'An inspector asks about “Outbreak response basics” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Outbreak response basics”?',
        (
            'If multiple guests report illness, management may preserve samples, pull menu items, deepen cleaning, and cooperate with',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'If multiple guests report illness, management may preserve samples, pull menu items, deepen cleaning, and cooperate with environmental health.',
    ),
    'Situation: Three guests report illness': _kit(
        (
            'On the line, you apply “Situation: Three guests report illness” before the next ticket leaves the pass.',
            'You coach a new hire: Example: Three tickets from last night’s banquet call with similar symptoms.',
            'An inspector asks about “Situation: Three guests report illness” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Three guests report illness”?',
        (
            'Example: Three tickets from last night’s banquet call with similar symptoms.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: Three tickets from last night’s banquet call with similar symptoms.',
    ),
    'FAT TOM growth conditions': _kit(
        (
            'On the line, you apply “FAT TOM growth conditions” before the next ticket leaves the pass.',
            'You coach a new hire: Bacteria need Food, Acidity, Time, Temperature, Oxygen, and Moisture (FAT TOM) in the right ranges.',
            'An inspector asks about “FAT TOM growth conditions” — you point to the station and explain the control.',
        ),
        'Which choice best matches “FAT TOM growth conditions”?',
        (
            'Bacteria need Food, Acidity, Time, Temperature, Oxygen, and Moisture (FAT TOM) in the right ranges.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Bacteria need Food, Acidity, Time, Temperature, Oxygen, and Moisture (FAT TOM) in the right ranges.',
    ),
    'Spores and cooling': _kit(
        (
            'On the line, you apply “Spores and cooling” before the next ticket leaves the pass.',
            'You coach a new hire: Some bacteria form spores that survive cooking.',
            'An inspector asks about “Spores and cooling” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Spores and cooling”?',
        (
            'Some bacteria form spores that survive cooking.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Some bacteria form spores that survive cooking.',
    ),
    'Ready-to-eat contamination routes': _kit(
        (
            'On the line, you apply “Ready-to-eat contamination routes” before the next ticket leaves the pass.',
            'You coach a new hire: Ready-to-eat foods get contaminated by hands, raw drip, dirty cloths, pests, and unclean equipment.',
            'An inspector asks about “Ready-to-eat contamination routes” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Ready-to-eat contamination routes”?',
        (
            'Ready-to-eat foods get contaminated by hands, raw drip, dirty cloths, pests, and unclean equipment.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Ready-to-eat foods get contaminated by hands, raw drip, dirty cloths, pests, and unclean equipment.',
    ),
    'Prevention hierarchy': _kit(
        (
            'On the line, you apply “Prevention hierarchy” before the next ticket leaves the pass.',
            'You coach a new hire: Rank controls: keep sick workers off the line, wash hands, cook and hold correctly, cool fast, prevent cross-contaminati',
            'An inspector asks about “Prevention hierarchy” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Prevention hierarchy”?',
        (
            'Rank controls: keep sick workers off the line, wash hands, cook and hold correctly, cool fast, prevent cross-contaminati',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Rank controls: keep sick workers off the line, wash hands, cook and hold correctly, cool fast, prevent cross-contamination, clean and sanitize, control allergens and chemicals.',
    ),
    'Module wrap — pathogens': _kit(
        (
            'On the line, you apply “Module wrap — pathogens” before the next ticket leaves the pass.',
            'You coach a new hire: You studied major pathogens, high-risk guests, outbreak response, and prevention hierarchy.',
            'An inspector asks about “Module wrap — pathogens” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Module wrap — pathogens”?',
        (
            'You studied major pathogens, high-risk guests, outbreak response, and prevention hierarchy.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'You studied major pathogens, high-risk guests, outbreak response, and prevention hierarchy.',
    ),
    'Approved suppliers': _kit(
        (
            'On the line, you apply “Approved suppliers” before the next ticket leaves the pass.',
            'You coach a new hire: Buy from approved reputable suppliers.',
            'An inspector asks about “Approved suppliers” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Approved suppliers”?',
        (
            'Buy from approved reputable suppliers.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Buy from approved reputable suppliers.',
    ),
    'Receiving inspection checklist': _kit(
        (
            'On the line, you apply “Receiving inspection checklist” before the next ticket leaves the pass.',
            'You coach a new hire: Check temperatures, package integrity, dates, pest evidence, and signs of thaw-refreeze.',
            'An inspector asks about “Receiving inspection checklist” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Receiving inspection checklist”?',
        (
            'Check temperatures, package integrity, dates, pest evidence, and signs of thaw-refreeze.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Check temperatures, package integrity, dates, pest evidence, and signs of thaw-refreeze.',
    ),
    'Situation: Warm dairy delivery': _kit(
        (
            'On the line, you apply “Situation: Warm dairy delivery” before the next ticket leaves the pass.',
            'You coach a new hire: Example: Milk arrives at 50°F on a summer afternoon.',
            'An inspector asks about “Situation: Warm dairy delivery” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Warm dairy delivery”?',
        (
            'Example: Milk arrives at 50°F on a summer afternoon.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: Milk arrives at 50°F on a summer afternoon.',
    ),
    'Dry storage rules': _kit(
        (
            'On the line, you apply “Dry storage rules” before the next ticket leaves the pass.',
            'You coach a new hire: Keep dry goods six inches off the floor, away from walls enough to clean, and under 50–70°F when possible per policy.',
            'An inspector asks about “Dry storage rules” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Dry storage rules”?',
        (
            'Keep dry goods six inches off the floor, away from walls enough to clean, and under 50–70°F when possible per policy.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Keep dry goods six inches off the floor, away from walls enough to clean, and under 50–70°F when possible per policy.',
    ),
    'Cold storage organization': _kit(
        (
            'On the line, you apply “Cold storage organization” before the next ticket leaves the pass.',
            'You coach a new hire: Top to bottom typically: ready-to-eat, seafood, whole cuts, ground meats, poultry — so raw juices drip downward onto low',
            'An inspector asks about “Cold storage organization” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Cold storage organization”?',
        (
            'Top to bottom typically: ready-to-eat, seafood, whole cuts, ground meats, poultry — so raw juices drip downward onto low',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Top to bottom typically: ready-to-eat, seafood, whole cuts, ground meats, poultry — so raw juices drip downward onto lower-risk storage only.',
    ),
    'Situation: Chicken above lettuce': _kit(
        (
            'On the line, you apply “Situation: Chicken above lettuce” before the next ticket leaves the pass.',
            'You coach a new hire: Example: A pan of raw chicken sits on a shelf above uncovered lettuce.',
            'An inspector asks about “Situation: Chicken above lettuce” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Chicken above lettuce”?',
        (
            'Example: A pan of raw chicken sits on a shelf above uncovered lettuce.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: A pan of raw chicken sits on a shelf above uncovered lettuce.',
    ),
    'Hot holding during service': _kit(
        (
            'On the line, you apply “Hot holding during service” before the next ticket leaves the pass.',
            'You coach a new hire: During service, check hot wells and check temps on a schedule.',
            'An inspector asks about “Hot holding during service” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Hot holding during service”?',
        (
            'During service, check hot wells and check temps on a schedule.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'During service, check hot wells and check temps on a schedule.',
    ),
    'Buffet and self-service': _kit(
        (
            'On the line, you apply “Buffet and self-service” before the next ticket leaves the pass.',
            'You coach a new hire: Provide clean plates for returns — guests should not refill dirty plates.',
            'An inspector asks about “Buffet and self-service” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Buffet and self-service”?',
        (
            'Provide clean plates for returns — guests should not refill dirty plates.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Provide clean plates for returns — guests should not refill dirty plates.',
    ),
    'Situation: Dirty plate refill': _kit(
        (
            'On the line, you apply “Situation: Dirty plate refill” before the next ticket leaves the pass.',
            'You coach a new hire: Example: A guest returns to the buffet with a used plate.',
            'An inspector asks about “Situation: Dirty plate refill” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Dirty plate refill”?',
        (
            'Example: A guest returns to the buffet with a used plate.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: A guest returns to the buffet with a used plate.',
    ),
    'Leftovers and takeout': _kit(
        (
            'On the line, you apply “Leftovers and takeout” before the next ticket leaves the pass.',
            'You coach a new hire: Cool leftovers with the two-step method if saving.',
            'An inspector asks about “Leftovers and takeout” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Leftovers and takeout”?',
        (
            'Cool leftovers with the two-step method if saving.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Cool leftovers with the two-step method if saving.',
    ),
    'Ice scoop hygiene': _kit(
        (
            'On the line, you apply “Ice scoop hygiene” before the next ticket leaves the pass.',
            'You coach a new hire: Store scoops in a clean holder outside the ice, handle up.',
            'An inspector asks about “Ice scoop hygiene” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Ice scoop hygiene”?',
        (
            'Store scoops in a clean holder outside the ice, handle up.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Store scoops in a clean holder outside the ice, handle up.',
    ),
    'Situation: Scoop in the ice': _kit(
        (
            'On the line, you apply “Situation: Scoop in the ice” before the next ticket leaves the pass.',
            'You coach a new hire: Example: You find the scoop handle buried in the ice bin.',
            'An inspector asks about “Situation: Scoop in the ice” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Scoop in the ice”?',
        (
            'Example: You find the scoop handle buried in the ice bin.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: You find the scoop handle buried in the ice bin.',
    ),
    'Service utensils and sneeze guards': _kit(
        (
            'On the line, you apply “Service utensils and sneeze guards” before the next ticket leaves the pass.',
            'You coach a new hire: Utensils need clean handles and regular swap-outs.',
            'An inspector asks about “Service utensils and sneeze guards” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Service utensils and sneeze guards”?',
        (
            'Utensils need clean handles and regular swap-outs.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Utensils need clean handles and regular swap-outs.',
    ),
    'Bare hand vs utensils at service': _kit(
        (
            'On the line, you apply “Bare hand vs utensils at service” before the next ticket leaves the pass.',
            'You coach a new hire: Plating ready-to-eat foods for service still needs barriers where required.',
            'An inspector asks about “Bare hand vs utensils at service” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Bare hand vs utensils at service”?',
        (
            'Plating ready-to-eat foods for service still needs barriers where required.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Plating ready-to-eat foods for service still needs barriers where required.',
    ),
    'Closing: discard vs save': _kit(
        (
            'On the line, you apply “Closing: discard vs save” before the next ticket leaves the pass.',
            'You coach a new hire: Know what must be discarded at close — time-control items, abused hot hold, uncovered food with pest risk.',
            'An inspector asks about “Closing: discard vs save” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Closing: discard vs save”?',
        (
            'Know what must be discarded at close — time-control items, abused hot hold, uncovered food with pest risk.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Know what must be discarded at close — time-control items, abused hot hold, uncovered food with pest risk.',
    ),
    'Temperature logs habit': _kit(
        (
            'On the line, you apply “Temperature logs habit” before the next ticket leaves the pass.',
            'You coach a new hire: Logs prove control when memory fails.',
            'An inspector asks about “Temperature logs habit” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Temperature logs habit”?',
        (
            'Logs prove control when memory fails.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Logs prove control when memory fails.',
    ),
    'Alameda inspection readiness': _kit(
        (
            'On the line, you apply “Alameda inspection readiness” before the next ticket leaves the pass.',
            'You coach a new hire: Stay ready for Alameda County Environmental Health: stocked hand sinks, working thermometers, labeled chemicals, pest-fr',
            'An inspector asks about “Alameda inspection readiness” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Alameda inspection readiness”?',
        (
            'Stay ready for Alameda County Environmental Health: stocked hand sinks, working thermometers, labeled chemicals, pest-fr',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Stay ready for Alameda County Environmental Health: stocked hand sinks, working thermometers, labeled chemicals, pest-free storage, and trained staff who can explain procedures.',
    ),
    'Situation: Critical violation found': _kit(
        (
            'On the line, you apply “Situation: Critical violation found” before the next ticket leaves the pass.',
            'You coach a new hire: Example: An inspector cites no soap at the kitchen hand sink.',
            'An inspector asks about “Situation: Critical violation found” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Situation: Critical violation found”?',
        (
            'Example: An inspector cites no soap at the kitchen hand sink.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'Example: An inspector cites no soap at the kitchen hand sink.',
    ),
    'Finish with the official course': _kit(
        (
            'On the line, you apply “Finish with the official course” before the next ticket leaves the pass.',
            'You coach a new hire: This six-module track is practice for California food handler card topics used in Alameda County workplaces.',
            'An inspector asks about “Finish with the official course” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Finish with the official course”?',
        (
            'This six-module track is practice for California food handler card topics used in Alameda County workplaces.',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'This six-module track is practice for California food handler card topics used in Alameda County workplaces.',
    ),
    'Full course recap': _kit(
        (
            'On the line, you apply “Full course recap” before the next ticket leaves the pass.',
            'You coach a new hire: You covered hygiene and illness, temperatures, contamination and allergens, cleaning and facilities, pathogens and high-',
            'An inspector asks about “Full course recap” — you point to the station and explain the control.',
        ),
        'Which choice best matches “Full course recap”?',
        (
            'You covered hygiene and illness, temperatures, contamination and allergens, cleaning and facilities, pathogens and high-',
            'Skip this control during rush — speed matters more than safety.',
            'Guess ingredients or temperatures instead of verifying.',
            'Hide problems from managers and inspectors.',
        ),
        0,
        'You covered hygiene and illness, temperatures, contamination and allergens, cleaning and facilities, pathogens and high-risk guests, and receiving through service — about two hours of food handler pre',
    ),
}


def format_body_with_examples(rule_text: str, examples: tuple[str, ...]) -> str:
    rule = (rule_text or "").strip()
    if not examples:
        return rule
    lines = [rule, "", "Examples:"]
    for i, ex in enumerate(examples, start=1):
        lines.append(f"{i}. {ex}")
    return "\n".join(lines)


def narration_with_examples(say: str, examples: tuple[str, ...]) -> str:
    base = (say or "").strip()
    if not examples:
        return base
    bits = [base, "Here are a few friendly examples."]
    for ex in examples[:3]:
        bits.append(ex)
    bits.append("When you are ready, try the quiz or a short game to lock it in.")
    return " ".join(bits)


def kit_for_title(title: str, body: str = "") -> SegmentKit:
    """Back-compat: look up by English title (also accepts a slide_key string)."""
    return kit_for_slide(title=title, body=body)


def kit_for_slide(
    *,
    slide_key: str = "",
    title: str = "",
    body: str = "",
) -> SegmentKit:
    """Prefer the stable slide_key so translated titles still hit curated kits."""
    if slide_key and slide_key in _KITS:
        return _KITS[slide_key]
    if title and title in _KITS:
        return _KITS[title]
    return _synthesize(title or slide_key, body)


# Alias every English title under its stable slide_key so translated slides
# still resolve curated kits after the displayed title changes.
from .slide_keys import register_title_aliases  # noqa: E402

register_title_aliases(_KITS)


def _synthesize(title: str, body: str) -> SegmentKit:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", (body or "").strip()) if s.strip()]
    fact = sentences[0] if sentences else f"Review the key idea for {title}."
    examples = (
        f"Imagine applying “{title}” at work or on the road today.",
        f"Teach a friend one sentence about “{title}.”",
        f"Spot a real-world case that matches: {fact[:110]}",
    )
    choices = (
        fact[:140],
        f"Ignore “{title}” — it is optional trivia.",
        f"The opposite of “{title}” is always safer.",
        "Skip this topic until after you are certified.",
    )
    return _kit(
        examples,
        f"Which statement best matches “{title}”?",
        choices,
        0,
        fact,
    )


def attach_kit_fields(slide: CourseSlide, kit: SegmentKit) -> CourseSlide:
    """Return a copy of slide with multimodal fields filled."""
    data = slide.model_dump()
    data["examples"] = list(kit.examples)
    data["modalities"] = list(CERT_MODALITIES)
    data["quiz_spec"] = {
        "prompt": kit.quiz_prompt,
        "choices": list(kit.quiz_choices),
        "correct_index": kit.quiz_correct_index,
        "explanation": kit.quiz_explanation,
    }
    data["game_spec"] = {
        "kind": kit.game_kind,
        "prompt": kit.game_prompt,
        "options": list(kit.game_options),
        "correct_index": kit.game_correct_index,
        "steps": list(kit.game_steps),
    }
    return CourseSlide.model_validate(data)


def quiz_from_slide(slide: CourseSlide, objective: LearningObjective) -> QuizQuestion | None:
    spec = getattr(slide, "quiz_spec", None) or {}
    if not isinstance(spec, dict) or not spec.get("choices"):
        return None
    choices = [str(c) for c in spec.get("choices") or []]
    if len(choices) < 2:
        return None
    correct = int(spec.get("correct_index", 0))
    correct = max(0, min(correct, len(choices) - 1))
    return QuizQuestion(
        question_id=str(uuid.uuid4()),
        objective_id=objective.objective_id,
        prompt=str(spec.get("prompt") or f"Check — {slide.title}"),
        choices=choices,
        correct_index=correct,
        kind="pop",
        explanation=str(spec.get("explanation") or ""),
    )


def game_from_slide(slide: CourseSlide, objective_id: str = "") -> GameChallenge | None:
    spec = getattr(slide, "game_spec", None) or {}
    if not isinstance(spec, dict) or not spec:
        return None
    kind_raw = str(spec.get("kind") or "match_term")
    try:
        kind = GameKind(kind_raw)
    except ValueError:
        kind = GameKind.MATCH_TERM
    if kind is GameKind.ORDER_STEPS:
        steps = [str(s) for s in (spec.get("steps") or []) if str(s).strip()]
        if len(steps) < 2:
            return None
        return GameChallenge(
            game_id=str(uuid.uuid4()),
            kind=kind,
            title=f"Game: {slide.title}",
            prompt=str(spec.get("prompt") or "Put the steps in order"),
            payload={
                "steps_correct": steps,
                "steps_shown": list(reversed(steps)),
            },
            objective_id=objective_id,
        )
    if kind is GameKind.SPOT_GAP:
        # A valid spot_gap spec must not fall through to the match-term builder
        # (wrong payload shape). Build the real spot-the-gap payload.
        gap_options = [str(o) for o in (spec.get("options") or []) if str(o).strip()]
        answer = str(spec.get("answer") or "").strip()
        sentence = str(
            spec.get("sentence_with_gap") or spec.get("sentence") or ""
        ).strip()
        if len(gap_options) < 2 or not answer or not sentence:
            return None
        default_correct = gap_options.index(answer) if answer in gap_options else 0
        gap_correct = max(0, min(int(spec.get("correct_index", default_correct)), len(gap_options) - 1))
        return GameChallenge(
            game_id=str(uuid.uuid4()),
            kind=GameKind.SPOT_GAP,
            title=f"Game: {slide.title}",
            prompt=str(spec.get("prompt") or "Fill the blank"),
            payload={
                "sentence_with_gap": sentence,
                "answer": answer,
                "options": gap_options,
                "correct_index": gap_correct,
            },
            objective_id=objective_id,
        )
    options = [str(o) for o in (spec.get("options") or []) if str(o).strip()]
    if len(options) < 2:
        return None
    correct = int(spec.get("correct_index", 0))
    correct = max(0, min(correct, len(options) - 1))
    return GameChallenge(
        game_id=str(uuid.uuid4()),
        kind=GameKind.MATCH_TERM,
        title=f"Game: {slide.title}",
        prompt=str(spec.get("prompt") or f"Which option matches “{slide.title}”?"),
        payload={"term": slide.title, "options": options, "correct_index": correct},
        objective_id=objective_id,
    )


def preferred_modalities(profile_scores: dict[str, float]) -> list[str]:
    """Rank modalities using learner preference knobs (higher = prefer more)."""
    ranking = [
        ("image", float(profile_scores.get("learn_from_images", 0.7))),
        ("text", float(profile_scores.get("learn_from_text", 0.7))),
        ("video", float(profile_scores.get("learn_from_video", 0.7))),
        ("examples", float(profile_scores.get("learn_from_examples", 0.75))),
        ("quiz", float(profile_scores.get("learn_from_quiz", 0.55))),
        ("game", float(profile_scores.get("learn_from_games", 0.55))),
        ("activity", float(profile_scores.get("learn_from_activity", 0.5))),
    ]
    ranking.sort(key=lambda row: (-row[1], row[0]))
    return [name for name, _ in ranking]


def coverage_report() -> dict[str, int]:
    return {"curated_kits": len(_KITS), "modalities": len(CERT_MODALITIES)}
