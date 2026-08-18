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
