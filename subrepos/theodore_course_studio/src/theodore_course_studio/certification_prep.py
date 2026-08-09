"""Certification-prep tracks for Course Studio (peer to early-learning).

These are study aids for public exams / cards — not DMV-approved courses and
not Alameda-accredited food-handler training. Official handbooks and county
guidance remain the authority.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from .types import CategoryId, CourseSlide, StudioCourse

# Soft session target for adult cert prep (kids stay on early_learning budgets).
CERT_SESSION_MIN_MINUTES = 15
CERT_SESSION_MAX_MINUTES = 20
CERT_TARGET_SLIDES = 12


class CertTrackId(str, Enum):
    CA_DMV_PERMIT = "ca_dmv_permit"
    ALAMEDA_FOOD_HANDLER = "alameda_food_handler"


TRACK_NAMES = {
    CertTrackId.CA_DMV_PERMIT: "California DMV permit prep",
    CertTrackId.ALAMEDA_FOOD_HANDLER: "Alameda County / CA food handler prep",
}

JURISDICTIONS = {
    CertTrackId.CA_DMV_PERMIT: "us-ca",
    CertTrackId.ALAMEDA_FOOD_HANDLER: "us-ca-alameda",
}

CATEGORIES = {
    CertTrackId.CA_DMV_PERMIT: CategoryId.DRIVER_EDUCATION,
    CertTrackId.ALAMEDA_FOOD_HANDLER: CategoryId.FOOD_SAFETY,
}


@dataclass(frozen=True)
class CertBeat:
    title: str
    body: str
    say: str


@dataclass(frozen=True)
class CertLessonTemplate:
    lesson_id: str
    track: CertTrackId
    title: str
    description: str
    estimated_minutes: int
    beats: tuple[CertBeat, ...]
    disclaimer: str


class CertCourseRequest(BaseModel):
    track: CertTrackId = CertTrackId.CA_DMV_PERMIT
    lesson_id: str = "ca-dmv-basics"
    language: str = "en"
    title: str | None = None


class CertCourseOption(BaseModel):
    lesson_id: str
    track: CertTrackId
    track_name: str
    jurisdiction: str
    category: str
    title: str
    description: str
    slides: int
    estimated_minutes: int
    prep_only: bool = True


def _b(title: str, body: str, say: str | None = None) -> CertBeat:
    return CertBeat(title=title, body=body, say=say or body)


_DMV_DISCLAIMER = (
    "Certification prep only — not a DMV-approved driver education course. "
    "Study the current California Driver's Handbook and take official practice "
    "tests at dmv.ca.gov before your knowledge exam."
)

_FOOD_DISCLAIMER = (
    "Certification prep only — not Alameda County–accredited food handler training. "
    "Confirm card requirements with Alameda County Environmental Health / "
    "California food handler card rules before working with food."
)

_TEMPLATES: tuple[CertLessonTemplate, ...] = (
    CertLessonTemplate(
        "ca-dmv-basics",
        CertTrackId.CA_DMV_PERMIT,
        "CA DMV — Rules of the road (basics)",
        "California right-of-way, signals, speed, and following distance.",
        18,
        (
            _b(
                "Prep, not a DMV course",
                "This short lesson helps you study for the California knowledge test. "
                "It is not DMV-approved driver education. Always use the current "
                "California Driver's Handbook as the source of truth.",
            ),
            _b(
                "California learner's permit",
                "To get a provisional instruction permit in California you typically "
                "need to pass a vision exam and a knowledge test, complete required "
                "application steps, and meet age/education requirements. Confirm "
                "current rules on dmv.ca.gov before you apply.",
            ),
            _b(
                "Right-of-way at stops",
                "At a four-way stop, the first vehicle to arrive goes first. If two "
                "arrive together, yield to the driver on your right. Yield to "
                "pedestrians in marked or unmarked crosswalks and to emergency "
                "vehicles with lights and sirens.",
            ),
            _b(
                "California speed basics",
                "California’s Basic Speed Law: never drive faster than is safe for "
                "conditions, even below the posted limit. Common posted limits "
                "include 25 mph in business or residential districts unless posted "
                "otherwise, and higher freeway limits as posted.",
            ),
            _b(
                "Following distance",
                "Use at least a three-second following gap in good conditions. "
                "Increase space in rain, fog, night, heavy traffic, or when "
                "following large trucks and motorcycles.",
            ),
            _b(
                "Signals and lane changes",
                "Signal before turns and lane changes. Check mirrors, signal, check "
                "your blind spot over your shoulder, then move smoothly. Do not "
                "change lanes in an intersection.",
            ),
            _b(
                "Turning and red lights",
                "California generally allows a right turn on red after a complete "
                "stop unless a sign prohibits it. Yield to pedestrians and cross "
                "traffic. Left on red is only allowed from a one-way street onto "
                "a one-way street when permitted.",
            ),
            _b(
                "School buses in California",
                "When a school bus displays flashing red lights and a stop signal "
                "arm on an undivided roadway, traffic in both directions must stop. "
                "On a divided highway, only traffic traveling the same direction as "
                "the bus must stop. Stay stopped until the lights stop and the arm "
                "is withdrawn.",
            ),
            _b(
                "Seat belts and phones",
                "California requires seat belt use. Handheld phone use while driving "
                "is restricted — use hands-free or pull over safely. Distracted "
                "driving citations and crash risk are high; put the phone away.",
            ),
            _b(
                "DUI limits (California)",
                "For drivers 21+, the BAC limit is 0.08%. Drivers under 21 are "
                "subject to zero-tolerance rules. Commercial drivers have a lower "
                "limit. Never drive impaired — arrange another ride.",
            ),
            _b(
                "What to do after a crash",
                "If safe, move out of traffic and turn on hazards. Call 911 for "
                "injuries. Exchange names, contact, license, and insurance info. "
                "Do not argue fault at the scene; report as required.",
            ),
            _b(
                "Study next",
                "Review road signs, sharing the road, and night/weather driving in "
                "the next short lessons. Take free CA DMV practice tests until you "
                "consistently score high before your real exam.",
            ),
        ),
        _DMV_DISCLAIMER,
    ),
    CertLessonTemplate(
        "ca-dmv-signs",
        CertTrackId.CA_DMV_PERMIT,
        "CA DMV — Signs, signals, markings",
        "Regulatory, warning, and guide signs used on California roads.",
        16,
        (
            _b(
                "Regulatory signs",
                "White rectangular signs with black or red markings tell you what "
                "you must or must not do: speed limits, Do Not Enter, One Way, "
                "and No U-Turn. A red octagon is always STOP.",
            ),
            _b(
                "Yield and stop",
                "A red-and-white triangle is YIELD — slow and give way. A stop "
                "sign requires a complete stop behind the limit line or crosswalk "
                "before proceeding when clear.",
            ),
            _b(
                "Warning signs",
                "Yellow diamond signs warn of curves, merges, pedestrians, school "
                "zones, and slippery roads. Slow and prepare to react; they do not "
                "always require a full stop.",
            ),
            _b(
                "Guide and service signs",
                "Green signs guide routes and exits. Blue signs mark services "
                "(fuel, food, lodging). Brown signs mark parks and recreation.",
            ),
            _b(
                "Traffic signals",
                "Green means go if clear; yellow means prepare to stop if safe; "
                "red means stop. Flashing red = stop sign. Flashing yellow = "
                "proceed with caution.",
            ),
            _b(
                "Pavement markings",
                "Yellow lines separate opposite directions; white lines separate "
                "same-direction lanes. A solid line on your side means do not "
                "pass or change lanes across it.",
            ),
            _b(
                "Railroad crossings",
                "Never cross when lights flash or gates lower. Stop at least "
                "15 feet from the nearest rail. If stalled on tracks, exit "
                "immediately and move away at an angle toward the oncoming train.",
            ),
            _b(
                "Roundabouts",
                "Yield to traffic already in the circle, enter when clear, and "
                "signal when exiting. Do not stop inside the circulating roadway.",
            ),
            _b(
                "Parking clearances",
                "Do not park too close to hydrants, crosswalks, stop signs, or "
                "driveways. Check local curb colors and posted restrictions — "
                "California cities enforce colored curb zones.",
            ),
            _b(
                "Night headlights",
                "Use headlights from 30 minutes after sunset to 30 minutes before "
                "sunrise and whenever visibility is poor. Dim high beams for "
                "oncoming traffic and when following closely.",
            ),
        ),
        _DMV_DISCLAIMER,
    ),
    CertLessonTemplate(
        "ca-dmv-sharing",
        CertTrackId.CA_DMV_PERMIT,
        "CA DMV — Sharing the road safely",
        "Trucks, bikes, pedestrians, weather, and freeway habits for CA roads.",
        17,
        (
            _b(
                "Pedestrians and bikes",
                "Yield to pedestrians in crosswalks. Give bicyclists room when "
                "passing and watch for them in bike lanes and at intersections. "
                "Never block a crosswalk while waiting at a red light.",
            ),
            _b(
                "Motorcycle awareness",
                "Motorcycles are easy to miss in blind spots. Give them a full "
                "lane and extra following distance. Double-check before lane "
                "changes.",
            ),
            _b(
                "Large truck no-zones",
                "Trucks have large blind spots on all sides, long stopping "
                "distances, and wide turns. Do not cut in and brake; avoid "
                "lingering beside a truck.",
            ),
            _b(
                "Freeway merging",
                "Accelerate on the on-ramp to match traffic, signal, and merge "
                "when there is a gap. Use the left lane for passing, then return "
                "right when safe.",
            ),
            _b(
                "Weather and hydroplaning",
                "Slow down in rain and fog. Use low beams in fog. If you "
                "hydroplane, ease off the gas and steer straight until tires "
                "regain grip — avoid sudden braking.",
            ),
            _b(
                "Emergency vehicles",
                "Yield to emergency vehicles with lights/sirens by pulling to "
                "the right and stopping. Do not block intersections. Move over "
                "for stopped emergency or tow vehicles when required.",
            ),
            _b(
                "Work zones",
                "Obey reduced work-zone speeds and flaggers. Fines often double "
                "in construction zones. Expect lane shifts and workers near "
                "traffic.",
            ),
            _b(
                "Before you drive",
                "Check brakes, lights, tires, mirrors, and fuel. Adjust mirrors "
                "and seats before moving. Fix warning lights promptly.",
            ),
            _b(
                "Handbook checkpoint",
                "Re-read the California Driver's Handbook sections on signs, "
                "sharing the road, and special driving situations. Official "
                "wording beats any study aid.",
            ),
            _b(
                "Practice test habit",
                "Take short CA DMV practice quizzes after each 15–20 minute "
                "study block. Come back later for another lesson instead of "
                "cramming for hours.",
            ),
        ),
        _DMV_DISCLAIMER,
    ),
    CertLessonTemplate(
        "alameda-food-hygiene",
        CertTrackId.ALAMEDA_FOOD_HANDLER,
        "CA / Alameda food handler — Hygiene & illness",
        "Handwashing, gloves, and when to stay home — California food handler prep.",
        16,
        (
            _b(
                "Prep card, not accreditation",
                "This lesson prepares you for California food handler card topics "
                "used in Alameda County workplaces. It is not county-accredited "
                "training. Follow your employer’s approved course and Alameda "
                "County Environmental Health guidance.",
            ),
            _b(
                "Why food handler cards matter",
                "California requires many food employees to hold a valid food "
                "handler card. Local environmental health (including Alameda "
                "County) enforces safe practices during inspections.",
            ),
            _b(
                "Handwashing that works",
                "Wash with soap and warm water for at least 20 seconds before "
                "handling food, after restroom use, after raw meat, after "
                "touching face/hair/garbage, and when switching tasks. Sanitizer "
                "is not a substitute for washing.",
            ),
            _b(
                "Gloves done right",
                "Change gloves when torn or dirty, after raw proteins, and before "
                "ready-to-eat foods. Wash hands before putting on a new pair.",
            ),
            _b(
                "Illness reporting",
                "Report vomiting, diarrhea, jaundice, or sore throat with fever "
                "to your manager before working. Diagnosed Salmonella Typhi, "
                "Shigella, STEC, hepatitis A, or norovirus require exclusion "
                "rules your manager must follow.",
            ),
            _b(
                "Personal cleanliness",
                "Wear clean clothes/aprons, restrain hair, keep nails short/clean, "
                "and avoid jewelry that can trap soil. Do not eat, drink, or "
                "smoke in food prep areas except in designated spots.",
            ),
            _b(
                "Ready-to-eat foods",
                "Do not touch ready-to-eat foods with bare hands where rules "
                "require barriers — use gloves, tongs, or deli paper as trained.",
            ),
            _b(
                "Cuts and bandages",
                "Cover wounds with clean bandages and wear gloves over hand "
                "wounds. Stay off the line if you cannot protect food from "
                "contamination.",
            ),
            _b(
                "Customer allergen basics",
                "Know major allergens (FDA Big 9 includes sesame). Never guess "
                "ingredients — check with the kitchen and prevent cross-contact.",
            ),
            _b(
                "Your next short block",
                "Continue with temperature control and contamination prevention "
                "in 15–20 minute sessions, or come back later — spaced practice "
                "beats marathon cramming.",
            ),
        ),
        _FOOD_DISCLAIMER,
    ),
    CertLessonTemplate(
        "alameda-food-temps",
        CertTrackId.ALAMEDA_FOOD_HANDLER,
        "CA / Alameda food handler — Temperatures",
        "Danger zone, cooking, holding, cooling, and reheating targets.",
        18,
        (
            _b(
                "Temperature danger zone",
                "Bacteria grow fast between 41°F and 135°F. Limit time in this "
                "zone. Time and temperature control is core to California food "
                "safety practice.",
            ),
            _b(
                "Cold holding",
                "Hold cold TCS foods at 41°F or below. Check refrigerators with "
                "a calibrated thermometer. Store raw animal foods below "
                "ready-to-eat items.",
            ),
            _b(
                "Hot holding",
                "Hold hot TCS foods at 135°F or above. Hot-holding equipment is "
                "not for reheating from cold — reheat properly first.",
            ),
            _b(
                "Safe cooking targets",
                "Common minimum internal temps: poultry 165°F; ground meats "
                "155°F; whole cuts of beef/pork/lamb and fish 145°F (with rest "
                "where required). Always verify with a food thermometer.",
            ),
            _b(
                "Cooling cooked food",
                "Cool from 135°F to 70°F within 2 hours, then to 41°F within "
                "4 more hours (6 hours total). Use shallow pans, ice baths, or "
                "blast chillers — never deep pots left on a counter.",
            ),
            _b(
                "Reheating",
                "Reheat previously cooked TCS food to 165°F within 2 hours "
                "before hot holding. Do not rely on steam tables or slow "
                "cookers to reheat.",
            ),
            _b(
                "Thawing safely",
                "Thaw in a refrigerator, under cold running water, in a "
                "microwave if cooking immediately, or as part of cooking. "
                "Never thaw on the counter at room temperature.",
            ),
            _b(
                "Receiving checks",
                "Reject deliveries that arrive too warm, damaged, pest-infested, "
                "or past safe dating. Keep cold chain unbroken from dock to "
                "storage.",
            ),
            _b(
                "Date marking",
                "Label prepared ready-to-eat TCS foods and follow the typical "
                "7-day refrigerated hold rule (day of prep counts as day 1) "
                "unless your code/policy is stricter.",
            ),
            _b(
                "Thermometer habits",
                "Calibrate and clean thermometers. Probe the thickest part of "
                "food. Log temperatures when your site requires it — inspectors "
                "look for consistent control.",
            ),
        ),
        _FOOD_DISCLAIMER,
    ),
    CertLessonTemplate(
        "alameda-food-contamination",
        CertTrackId.ALAMEDA_FOOD_HANDLER,
        "CA / Alameda food handler — Contamination & clean-up",
        "Cross-contamination, sanitizing, pests, and inspection readiness.",
        17,
        (
            _b(
                "Cross-contamination",
                "Keep raw proteins separate from ready-to-eat foods. Use separate "
                "boards/utensils or wash-rinse-sanitize between uses. Never let "
                "raw juices drip onto other foods.",
            ),
            _b(
                "Clean then sanitize",
                "Scrape, wash with detergent, rinse, sanitize at correct "
                "concentration, then air dry. Sanitizing dirty surfaces does "
                "not work.",
            ),
            _b(
                "Sanitizer strength",
                "Mix chlorine, quat, or iodine per label. Verify with test "
                "strips and replace dirty or weak solutions.",
            ),
            _b(
                "FIFO stock rotation",
                "First In, First Out: place new stock behind older product and "
                "use the oldest first to reduce spoilage risk.",
            ),
            _b(
                "Pest prevention",
                "Seal gaps, store food sealed, clean spills, and remove clutter. "
                "Use licensed pest control — do not spray pesticides over food "
                "areas yourself.",
            ),
            _b(
                "Allergen cross-contact",
                "Allergens need dedicated handling: clean equipment, separate "
                "prep, and accurate menu communication. Cleaning alone may not "
                "remove allergen residues.",
            ),
            _b(
                "Common pathogens",
                "Know high-risk associations: Salmonella (poultry/eggs), STEC "
                "(ground beef/produce), Listeria (deli/RTE), norovirus "
                "(hands/RTE). Control with hygiene and cooking/holding.",
            ),
            _b(
                "Health inspections",
                "Alameda County Environmental Health inspects for critical "
                "violations that can cause illness. Keep logs, fix problems "
                "immediately, and ask supervisors when unsure.",
            ),
            _b(
                "If a guest gets sick",
                "Take complaints seriously, notify a manager, preserve suspected "
                "food if instructed, and cooperate with investigators. Do not "
                "guess or argue medical causes.",
            ),
            _b(
                "Finish strong",
                "Review your employer’s approved California food handler course "
                "materials, then take the official assessment for your card. "
                "This studio track is practice only.",
            ),
        ),
        _FOOD_DISCLAIMER,
    ),
)


def list_cert_courses(track: CertTrackId | None = None) -> list[CertCourseOption]:
    out: list[CertCourseOption] = []
    for template in _TEMPLATES:
        if track is not None and template.track is not track:
            continue
        out.append(
            CertCourseOption(
                lesson_id=template.lesson_id,
                track=template.track,
                track_name=TRACK_NAMES[template.track],
                jurisdiction=JURISDICTIONS[template.track],
                category=CATEGORIES[template.track].value,
                title=template.title,
                description=template.description,
                slides=len(template.beats),
                estimated_minutes=template.estimated_minutes,
                prep_only=True,
            )
        )
    return out


def _find_template(track: CertTrackId, lesson_id: str) -> CertLessonTemplate:
    for template in _TEMPLATES:
        if template.track is track and template.lesson_id == lesson_id:
            return template
    # Allow lesson_id alone (unique across tracks).
    for template in _TEMPLATES:
        if template.lesson_id == lesson_id:
            return template
    known = ", ".join(t.lesson_id for t in _TEMPLATES)
    raise ValueError(f"unknown certification lesson_id={lesson_id!r}; known: {known}")


def build_cert_course(
    *,
    track: CertTrackId | None = None,
    lesson_id: str,
    language: str = "en",
    title: str | None = None,
    data_dir: Path | None = None,
) -> StudioCourse:
    del data_dir  # reserved for future pack overrides
    template = _find_template(track or CertTrackId.CA_DMV_PERMIT, lesson_id)
    category = CATEGORIES[template.track]
    jurisdiction = JURISDICTIONS[template.track]
    slides = [
        CourseSlide(
            index=i,
            title=beat.title,
            body=beat.body,
            narration=beat.say,
            tags=[
                "certification_prep",
                template.track.value,
                jurisdiction,
                template.lesson_id,
                category.value,
            ],
        )
        for i, beat in enumerate(template.beats)
    ]
    minutes = max(
        CERT_SESSION_MIN_MINUTES,
        min(CERT_SESSION_MAX_MINUTES, template.estimated_minutes),
    )
    return StudioCourse(
        course_id=f"cert-{uuid.uuid4().hex[:10]}",
        title=title or template.title,
        category=category,
        language=language or "en",
        audience="adult_cert_prep",
        subject=TRACK_NAMES[template.track],
        estimated_minutes=minutes,
        source_ids=[f"curated:{template.lesson_id}"],
        slides=slides,
        profile_adaptations={
            "mode": "certification_prep",
            "track": template.track.value,
            "jurisdiction": jurisdiction,
            "prep_only": True,
            "disclaimer": template.disclaimer,
            "session_soft_minutes": CERT_SESSION_MAX_MINUTES,
            "lesson_id": template.lesson_id,
        },
        created_at_ms=int(time.time() * 1000),
        status="ready",
    )


class CertTracksResponse(BaseModel):
    default_track: str = CertTrackId.CA_DMV_PERMIT.value
    tracks: list[dict] = Field(default_factory=list)
    courses: list[CertCourseOption] = Field(default_factory=list)
