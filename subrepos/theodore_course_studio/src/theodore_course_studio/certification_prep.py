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

from .avatar_director import avatar_script_for_slide
from .cert_i18n import NEEDS_NATIVE_REVIEW, translate_cert_slide
from .page_media import motion_data_url, picture_data_url
from .cert_multimodal import (
    CERT_MODALITIES,
    format_body_with_examples,
    kit_for_slide,
    narration_with_examples,
)
from .slide_keys import slide_key_for
from .studio_languages import normalize_language
from .types import CategoryId, CourseSlide, StudioCourse


def _storyboard_media(lesson_id: str, slide_index: int, *, title: str, symbol: str, color: str) -> tuple[str, str]:
    """Prefer full cert storyboard scenes; fall back to simple motion cards."""
    try:
        from aoep_shared.cert_storyboard import has_storyboard, storyboard_for_slide

        if has_storyboard(lesson_id):
            seg = storyboard_for_slide(lesson_id, slide_index, include_svg=True)
            if seg and seg.get("svg_data_url"):
                return seg["svg_data_url"], seg.get("svg_data_url", "")
    except Exception:
        pass
    still = picture_data_url(title=title, symbol=symbol, color=color)
    motion = motion_data_url(
        title=title, symbol=symbol, color=color, bounce_px=20, bounce_dur_s=2.4
    )
    return still, motion

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
    symbol: str = "📘"
    color: str = "#2563eb"
    activity: str = ""
    # Stable key; empty means "derive from English title via slide_keys".
    key: str = ""


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


# Topic-aware still/motion card visuals + a short do/say activity per beat.
_VISUALS: dict[str, tuple[str, str, str]] = {
    "Prep, not a DMV course": (
        "📋",
        "#64748b",
        "Say: this is prep only — the handbook is the authority.",
    ),
    "California learner's permit": (
        "🪪",
        "#0ea5e9",
        "Name two steps you need before a provisional permit.",
    ),
    "Right-of-way at stops": (
        "🛑",
        "#dc2626",
        "At a four-way stop, who goes first if you arrive together?",
    ),
    "California speed basics": (
        "⏱",
        "#f59e0b",
        "Say the Basic Speed Law in one sentence.",
    ),
    "Following distance": (
        "🚗",
        "#2563eb",
        "Count a three-second gap out loud.",
    ),
    "Signals and lane changes": (
        "↻",
        "#7c3aed",
        "List the mirror–signal–blind-spot order.",
    ),
    "Turning and red lights": (
        "🚦",
        "#ef4444",
        "When is a right turn on red allowed in California?",
    ),
    "School buses in California": (
        "🚌",
        "#eab308",
        "Who must stop for flashing red bus lights on an undivided road?",
    ),
    "Seat belts and phones": (
        "📱",
        "#334155",
        "Name one legal way to use a phone while driving in CA.",
    ),
    "DUI limits (California)": (
        "🚫",
        "#b91c1c",
        "What BAC limit applies to drivers 21 and older?",
    ),
    "What to do after a crash": (
        "🆘",
        "#f97316",
        "List three things to do after a crash if it is safe.",
    ),
    "Study next": (
        "✅",
        "#16a34a",
        "Name the next topic you will review after this lesson.",
    ),
    "Regulatory signs": (
        "⬛",
        "#111827",
        "What shape and color is a STOP sign?",
    ),
    "Yield and stop": (
        "▽",
        "#dc2626",
        "Difference between yield and a full stop?",
    ),
    "Warning signs": (
        "◆",
        "#eab308",
        "What do yellow diamond signs tell you to do?",
    ),
    "Guide and service signs": (
        "🛣",
        "#16a34a",
        "Match green / blue / brown signs to their purpose.",
    ),
    "Traffic signals": (
        "🚥",
        "#22c55e",
        "What does flashing red mean?",
    ),
    "Pavement markings": (
        "〰",
        "#facc15",
        "Yellow vs white lines — which separates opposite traffic?",
    ),
    "Railroad crossings": (
        "🚂",
        "#991b1b",
        "How far from the rail should you stop when lights flash?",
    ),
    "Roundabouts": (
        "🌀",
        "#0ea5e9",
        "Who has the right-of-way when you enter a roundabout?",
    ),
    "Parking clearances": (
        "🅿",
        "#6366f1",
        "Name two places you must not park near.",
    ),
    "Night headlights": (
        "💡",
        "#1e3a8a",
        "When must you use headlights in California?",
    ),
    "Pedestrians and bikes": (
        "🚶",
        "#14b8a6",
        "Where must you yield to pedestrians?",
    ),
    "Motorcycle awareness": (
        "🏍",
        "#a855f7",
        "Why leave motorcycles a full lane?",
    ),
    "Large truck no-zones": (
        "🚛",
        "#475569",
        "Name one truck blind-spot “no-zone.”",
    ),
    "Freeway merging": (
        "🔀",
        "#0284c7",
        "What should you do on the on-ramp before merging?",
    ),
    "Weather and hydroplaning": (
        "🌧",
        "#0369a1",
        "If you hydroplane, what should you do first?",
    ),
    "Emergency vehicles": (
        "🚨",
        "#dc2626",
        "How do you yield to lights and sirens?",
    ),
    "Work zones": (
        "🚧",
        "#ea580c",
        "Why are work-zone fines often higher?",
    ),
    "Before you drive": (
        "🔧",
        "#64748b",
        "Name three vehicle checks before you move.",
    ),
    "Handbook checkpoint": (
        "📖",
        "#0f766e",
        "Which handbook sections will you re-read next?",
    ),
    "Practice test habit": (
        "📝",
        "#4f46e5",
        "How long should each study block be?",
    ),
    "Prep card, not accreditation": (
        "📋",
        "#64748b",
        "Say: this track is practice, not accredited training.",
    ),
    "Why food handler cards matter": (
        "🪪",
        "#0d9488",
        "Who enforces food safety during inspections in Alameda?",
    ),
    "Handwashing that works": (
        "🧼",
        "#06b6d4",
        "How many seconds should you wash with soap?",
    ),
    "Gloves done right": (
        "🧤",
        "#38bdf8",
        "When must you change gloves?",
    ),
    "Illness reporting": (
        "🤒",
        "#e11d48",
        "Name two symptoms you must report before working.",
    ),
    "Personal cleanliness": (
        "👕",
        "#8b5cf6",
        "List two personal hygiene rules on the line.",
    ),
    "Ready-to-eat foods": (
        "🥗",
        "#22c55e",
        "How do you avoid bare-hand contact with RTE food?",
    ),
    "Cuts and bandages": (
        "🩹",
        "#f43f5e",
        "What covers a hand wound before gloves?",
    ),
    "Customer allergen basics": (
        "🥜",
        "#d97706",
        "What do you do if unsure about an allergen?",
    ),
    "Your next short block": (
        "✅",
        "#16a34a",
        "Name the next food-safety topic to study.",
    ),
    "Temperature danger zone": (
        "🌡",
        "#ef4444",
        "What Fahrenheit range is the danger zone?",
    ),
    "Cold holding": (
        "❄️",
        "#0284c7",
        "Cold TCS foods must stay at or below what temp?",
    ),
    "Hot holding": (
        "🔥",
        "#ea580c",
        "Hot TCS foods must stay at or above what temp?",
    ),
    "Safe cooking targets": (
        "🍗",
        "#b45309",
        "What internal temp for poultry?",
    ),
    "Cooling cooked food": (
        "🧊",
        "#0ea5e9",
        "Cool 135°F to 70°F within how many hours?",
    ),
    "Reheating": (
        "♨️",
        "#dc2626",
        "Reheat previously cooked TCS food to what temp?",
    ),
    "Thawing safely": (
        "💧",
        "#38bdf8",
        "Name one safe thawing method (not the counter).",
    ),
    "Receiving checks": (
        "📦",
        "#6366f1",
        "When should you reject a delivery?",
    ),
    "Date marking": (
        "🗓",
        "#7c3aed",
        "What is the typical refrigerated RTE hold window?",
    ),
    "Thermometer habits": (
        "📏",
        "#334155",
        "Where do you probe food with a thermometer?",
    ),
    "Cross-contamination": (
        "🔀",
        "#b91c1c",
        "How do you keep raw proteins off ready-to-eat food?",
    ),
    "Clean then sanitize": (
        "✨",
        "#0d9488",
        "Say the clean → rinse → sanitize order.",
    ),
    "Sanitizer strength": (
        "🧪",
        "#0891b2",
        "How do you verify sanitizer strength?",
    ),
    "FIFO stock rotation": (
        "↕",
        "#4f46e5",
        "What does FIFO stand for?",
    ),
    "Pest prevention": (
        "🪳",
        "#78716c",
        "Name two pest-prevention habits in a kitchen.",
    ),
    "Allergen cross-contact": (
        "⚠",
        "#f59e0b",
        "Why is cleaning alone not enough for allergens?",
    ),
    "Common pathogens": (
        "🦠",
        "#be123c",
        "Name one high-risk food linked to Salmonella.",
    ),
    "Health inspections": (
        "🏛",
        "#1d4ed8",
        "What should you do when a critical violation is found?",
    ),
    "If a guest gets sick": (
        "📞",
        "#c2410c",
        "Who do you notify first if a guest reports illness?",
    ),
    "Finish strong": (
        "🎓",
        "#15803d",
        "Where do you take the official food handler assessment?",
    ),
}


def _b(
    title: str,
    body: str,
    say: str | None = None,
    *,
    symbol: str | None = None,
    color: str | None = None,
    activity: str | None = None,
    key: str = "",
) -> CertBeat:
    default_symbol, default_color, default_activity = _VISUALS.get(
        title,
        ("📘", "#2563eb", f"Recall one key point about “{title}.”"),
    )
    return CertBeat(
        title=title,
        body=body,
        say=say or body,
        symbol=symbol or default_symbol,
        color=color or default_color,
        activity=activity or default_activity,
        key=key,
    )


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
        "CA / Alameda food handler — Hygiene & illness (1/6)",
        "Module 1 of a ~2-hour CA food handler prep track: hygiene, illness, wounds, RTE, allergens.",
        18,
        (
            _b(
                "Prep card, not accreditation",
                "This lesson is Module 1 of a roughly two-hour California / Alameda food handler prep track. It is study practice only — not county-accredited training. Complete your employer’s approved California food handler course and follow Alameda County Environmental Health guidance for the real card. Practice checkpoint (1/20 in hygiene): teach \"Prep card, not accreditation\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in…",
            ),
            _b(
                "Why food handler cards matter",
                "California requires many food employees to hold a valid food handler card. Cards show you understand basic safe practices. Local environmental health, including Alameda County, inspects kitchens and can cite violations that make people sick. Keep your card current and treat every shift as inspection-ready. Practice checkpoint (2/20 in hygiene): teach \"Why food handler cards matter\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer…",
            ),
            _b(
                "Two-hour course map",
                "Plan about two hours across six modules: hygiene and illness; temperatures; contamination and allergens; cleaning and facilities; pathogens and high-risk guests; receiving, storage, and service. Each block is about twenty minutes with situations and examples. Spaced sessions are fine — the full track is designed to match a typical food handler course length. Practice checkpoint (3/20 in hygiene): teach \"Two-hour course map\" to a new hire in under a minute. Start with the rule, then the tool or station (hand…",
            ),
            _b(
                "Handwashing that works",
                "Wash with soap and warm water for at least twenty seconds before handling food, after restroom use, after raw meat or seafood, after touching face, hair, or garbage, after cleaning, and whenever you switch tasks. Scrub palms, backs of hands, between fingers, and under nails. Dry with a single-use towel. Hand sanitizer is not a substitute for washing in food service. Practice checkpoint (4/20 in hygiene): teach \"Handwashing that works\" to a new hire in under a minute. Start with the rule, then the tool or…",
            ),
            _b(
                "Situation: After raw chicken",
                "Example: You bread raw chicken, then need to plate a salad. Remove gloves if worn, wash hands for twenty seconds at the hand sink, dry with a clean towel, put on a fresh pair of gloves, and only then touch the ready-to-eat salad. Raw juices on gloves or hands can spread Salmonella and Campylobacter to food that will not be cooked again. Practice checkpoint (5/20 in hygiene): teach \"Situation: After raw chicken\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink,…",
            ),
            _b(
                "Situation: Back from break",
                "Example: You return from break after using your phone and the restroom. Phone surfaces and restroom doors carry germs. Wash hands thoroughly before putting on gloves or touching food, utensils, or ice. If you touched your face or hair on the way back, wash again. Treat every return to the line as a handwashing moment. Practice checkpoint (6/20 in hygiene): teach \"Situation: Back from break\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color,…",
            ),
            _b(
                "Gloves done right",
                "Gloves are a barrier, not magic. Change gloves when torn or dirty, after handling raw proteins, before ready-to-eat foods, after touching money or dirty surfaces, and at least every four hours during continuous use — or sooner if your policy is stricter. Always wash hands before putting on a new pair. Never wash and reuse single-use gloves. Practice checkpoint (7/20 in hygiene): teach \"Gloves done right\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer,…",
            ),
            _b(
                "Situation: Raw then sandwich",
                "Example: You portion raw burger patties, then a ticket calls for a cold turkey sandwich. Do not keep the same gloves. Remove them, wash hands, glove again, and assemble the sandwich with clean utensils. Same rule for tongs: wash-rinse-sanitize or switch to a clean set before they touch ready-to-eat bread or produce. Practice checkpoint (8/20 in hygiene): teach \"Situation: Raw then sandwich\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color,…",
            ),
            _b(
                "Bare-hand contact rules",
                "Many California food operations restrict bare-hand contact with ready-to-eat foods. Use gloves, tongs, deli paper, or spatulas as trained. If your approved procedures allow limited bare-hand contact under strict controls, follow them exactly — never invent exceptions. When in doubt, use a barrier. Practice checkpoint (9/20 in hygiene): teach \"Bare-hand contact rules\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in…",
            ),
            _b(
                "Illness reporting",
                "Report vomiting, diarrhea, jaundice, or sore throat with fever to your manager before working. Do not handle food while contagious. Diagnosed Salmonella Typhi, Shigella, Shiga toxin-producing E. coli, hepatitis A, or norovirus trigger exclusion and reporting rules your manager must follow. Feeling “a little off” still warrants a conversation — guests cannot see your symptoms. Practice checkpoint (10/20 in hygiene): teach \"Illness reporting\" to a new hire in under a minute. Start with the rule, then the tool or…",
            ),
            _b(
                "Situation: Morning stomach flu",
                "Example: You wake up with diarrhea and feel weak but need the shift. Staying home protects guests and coworkers. Call your manager, report symptoms honestly, and follow exclusion guidance before returning — often twenty-four hours symptom-free for vomiting or diarrhea unless a diagnosed pathogen requires longer. Working sick is a common cause of norovirus outbreaks. Practice checkpoint (11/20 in hygiene): teach \"Situation: Morning stomach flu\" to a new hire in under a minute. Start with the rule, then the tool…",
            ),
            _b(
                "Big Six and exclusion",
                "Managers follow exclusion and restriction rules for the Big Six: norovirus, hepatitis A, Salmonella Typhi, nontyphoidal Salmonella, Shigella, and Shiga toxin-producing E. coli. Jaundice is an immediate stop. You do not diagnose yourself — you report symptoms and diagnoses so management can apply the code. Never hide a doctor’s note about a foodborne pathogen. Practice checkpoint (12/20 in hygiene): teach \"Big Six and exclusion\" to a new hire in under a minute. Start with the rule, then the tool or station (hand…",
            ),
            _b(
                "Personal cleanliness",
                "Wear clean clothes and aprons, restrain hair, keep nails short and clean, and avoid jewelry that traps soil — typically a plain band is the only ring allowed if policy permits any. Do not eat, drink, smoke, or chew gum in food prep areas except in designated spots. Change soiled aprons; they collect pathogens and can touch ready-to-eat food. Practice checkpoint (13/20 in hygiene): teach \"Personal cleanliness\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer,…",
            ),
            _b(
                "Hair, nails, and jewelry",
                "Hair restraints — hats, nets, or wraps — keep hair out of food. Beards may need covers per policy. Fingernails should be short; artificial nails and polish often require gloves because they trap debris and chip into food. Remove dangling earrings, watches, and bracelets that contact food or cannot be cleaned. Practice checkpoint (14/20 in hygiene): teach \"Hair, nails, and jewelry\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer…",
            ),
            _b(
                "Cuts and bandages",
                "Cover wounds with clean, impermeable bandages. Wear gloves over hand and wrist wounds. Bright bandage colors help you notice if one falls into food. Stay off the line if you cannot fully protect food from blood or wound drainage. Report injuries to a manager and replace contaminated food and utensils. Practice checkpoint (15/20 in hygiene): teach \"Cuts and bandages\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in…",
            ),
            _b(
                "Situation: Cut finger on the line",
                "Example: A knife nick bleeds during prep. Stop food contact immediately. Clean and bandage the wound, glove over it, discard any food that may have been contaminated, wash and sanitize the station, and tell your manager. Do not wrap a towel around a bleeding finger and keep chopping — that contaminates the batch. Practice checkpoint (16/20 in hygiene): teach \"Situation: Cut finger on the line\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color,…",
            ),
            _b(
                "Ready-to-eat foods",
                "Ready-to-eat foods will not be cooked again before service — salads, garnishes, bread, sushi, deli meats, and plated desserts. They need clean hands or barriers, clean utensils, and protection from raw juices and dirty surfaces. Store them above raw animal foods and away from chemicals. Practice checkpoint (17/20 in hygiene): teach \"Ready-to-eat foods\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass),…",
            ),
            _b(
                "Customer allergen basics",
                "Know the major food allergens — milk, eggs, fish, shellfish, tree nuts, peanuts, wheat, soy, and sesame (FDA Big 9). Never guess ingredients. Check labels, recipes, and the kitchen. Prevent cross-contact with shared fryers, tongs, and cutting boards. Allergic reactions can be life-threatening within minutes. Practice checkpoint (18/20 in hygiene): teach \"Customer allergen basics\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer…",
            ),
            _b(
                "Situation: Guest nut allergy",
                "Example: A guest says they have a severe tree-nut allergy. Do not say “it should be fine.” Ask the kitchen to confirm ingredients and prep path, use clean utensils and surfaces, and tell the guest honestly if you cannot guarantee no cross-contact. Managers should own complex allergen tickets. Practice checkpoint (19/20 in hygiene): teach \"Situation: Guest nut allergy\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in…",
            ),
            _b(
                "Module wrap — hygiene",
                "You covered handwashing, gloves, illness reporting, personal cleanliness, wounds, ready-to-eat barriers, and allergens — the foundation of a two-hour food handler prep. Next: temperature control — danger zone, cooking, holding, cooling, and reheating. Pause if needed; spaced practice beats rushing. Practice checkpoint (20/20 in hygiene): teach \"Module wrap — hygiene\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in…",
            ),
        ),
        _FOOD_DISCLAIMER,
    ),
    CertLessonTemplate(
        "alameda-food-temps",
        CertTrackId.ALAMEDA_FOOD_HANDLER,
        "CA / Alameda food handler — Temperatures (2/6)",
        "Module 2: danger zone, cooking, holding, cooling, reheating, thawing.",
        18,
        (
            _b(
                "Temperature danger zone",
                "Bacteria that cause foodborne illness multiply fastest between 41°F and 135°F — the temperature danger zone. Limit how long time/temperature control for safety (TCS) foods sit in this range. Move food quickly through receiving, prep, cooking, cooling, and service. When unsure, check with a clean, calibrated thermometer. Practice checkpoint (1/20 in temps): teach \"Temperature danger zone\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color,…",
            ),
            _b(
                "What counts as TCS food",
                "TCS foods need time and temperature control: milk and dairy, meat, poultry, seafood, cooked vegetables and grains, cut melons and leafy greens, sprouts, garlic-in-oil, and many leftovers. Shelf-stable canned goods are different until opened. Know which items on your menu are TCS so you hold and cool them correctly. Practice checkpoint (2/20 in temps): teach \"What counts as TCS food\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer…",
            ),
            _b(
                "Cold holding",
                "Hold cold TCS foods at 41°F or below. Check refrigerators and cold wells with a calibrated thermometer — do not trust the dial alone. Store raw animal foods below ready-to-eat items so juices cannot drip down. Keep cold-holding units closed when not in use and avoid overpacking so air can circulate. Practice checkpoint (3/20 in temps): teach \"Cold holding\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or…",
            ),
            _b(
                "Situation: Walk-in at 48°F",
                "Example: The walk-in thermometer reads 48°F at open. Do not ignore it. Tell a manager, move TCS food to a working cold unit if needed, and stop accepting deliveries into that box until it holds 41°F or below. Food held too warm too long may need to be discarded per policy — temperature abuse is a critical risk. Practice checkpoint (4/20 in temps): teach \"Situation: Walk-in at 48°F\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer…",
            ),
            _b(
                "Hot holding",
                "Hold hot TCS foods at 135°F or above. Stir and check temperatures in several spots. Hot-holding equipment is not for reheating from cold — food must already be reheated correctly before it goes into a steam table or hot box. Cover pans to hold heat and prevent contamination. Practice checkpoint (5/20 in temps): teach \"Hot holding\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode —…",
            ),
            _b(
                "Situation: Steam table drops",
                "Example: Soup in a steam table reads 128°F. That is in the danger zone. Reheat properly to 165°F within two hours if policy allows recovery, or discard if time and temperature limits were exceeded. Do not just turn the dial up and hope — verify with a thermometer after reheating, then return to hot hold at 135°F+. Practice checkpoint (6/20 in temps): teach \"Situation: Steam table drops\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer…",
            ),
            _b(
                "Cooking poultry to 165°F",
                "Poultry — chicken, turkey, duck — and stuffed foods generally need a minimum internal temperature of 165°F. Probe the thickest part without touching bone. Juices running clear are not a substitute for a thermometer. Ground poultry also targets 165°F. Practice checkpoint (7/20 in temps): teach \"Cooking poultry to 165°F\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes…",
            ),
            _b(
                "Ground meats to 155°F",
                "Ground meats such as beef, pork, and other comminuted meats commonly require 155°F for a specified time (or hotter for less time per the code chart). Grinding spreads bacteria through the product, so the center must reach a safe temperature. Check patties and meatballs in the thickest piece. Practice checkpoint (8/20 in temps): teach \"Ground meats to 155°F\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or…",
            ),
            _b(
                "Whole cuts and fish 145°F",
                "Whole cuts of beef, pork, lamb, and fish often target 145°F with a rest time where required. Eggs for immediate service may follow different rules than pooled eggs held for later. Always use your operation’s approved cook chart — never rely on color alone. Practice checkpoint (9/20 in temps): teach \"Whole cuts and fish 145°F\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what…",
            ),
            _b(
                "Situation: Checking a burger",
                "Example: A guest wants a burger “pink in the middle.” Your restaurant policy and local code decide whether undercooked ground beef can be served and what consumer advisory is required. Never invent a lower cook temp. Probe the patty; if it is under the required temperature, continue cooking or follow the approved advisory process. Practice checkpoint (10/20 in temps): teach \"Situation: Checking a burger\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer,…",
            ),
            _b(
                "Cooling cooked food",
                "Cool from 135°F to 70°F within two hours, then from 70°F to 41°F within four more hours — six hours total. Use shallow pans, ice baths, ice paddles, or blast chillers. Divide large batches. Do not leave a deep pot of chili on the counter overnight. Practice checkpoint (11/20 in temps): teach \"Cooling cooked food\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong…",
            ),
            _b(
                "Situation: Deep pot of chili",
                "Example: A twenty-quart pot of chili sits on a prep table to “cool.” The center stays hot for hours while the danger zone breeds bacteria and toxins. Instead: portion into shallow pans, use an ice bath, stir, and check temperatures on a log. If the two-hour or six-hour limits are missed, discard per policy. Practice checkpoint (12/20 in temps): teach \"Situation: Deep pot of chili\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer…",
            ),
            _b(
                "Reheating leftovers",
                "Reheat previously cooked TCS food to 165°F within two hours before hot holding. Stir and check multiple spots. Do not rely on steam tables, crock pots, or warmers to reheat — they hold heat, they do not reheat safely from cold. Cool leftover reheated food again with the two-step method if saving. Practice checkpoint (13/20 in temps): teach \"Reheating leftovers\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or…",
            ),
            _b(
                "Thawing safely",
                "Thaw in a refrigerator at 41°F or below, under cold running water at 70°F or colder with product submerged and water overflowing, in a microwave if you cook immediately after, or as part of cooking. Never thaw on the counter at room temperature — the surface enters the danger zone while the center stays frozen. Practice checkpoint (14/20 in temps): teach \"Thawing safely\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in…",
            ),
            _b(
                "Situation: Chicken on the counter",
                "Example: Frozen chicken sits in a bus tub on the prep counter “so it thaws faster.” Stop the practice. Move it to cold thawing methods. If the surface has been in the danger zone too long, follow discard rules. Train new staff that speed is not an excuse for unsafe thawing. Practice checkpoint (15/20 in temps): teach \"Situation: Chicken on the counter\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass),…",
            ),
            _b(
                "Receiving temperature checks",
                "Check cold deliveries with a thermometer: refrigerated foods generally 41°F or below, frozen foods solidly frozen. Reject warm, damaged, pest-infested, or spoiled product. Keep the cold chain unbroken from dock to storage. Record temperatures when your site requires logs. Practice checkpoint (16/20 in temps): teach \"Receiving temperature checks\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the…",
            ),
            _b(
                "Date marking",
                "Label prepared ready-to-eat TCS foods held over twenty-four hours. Day of prep counts as day one. Follow the typical seven-day refrigerated hold at 41°F or below unless your code or policy is stricter. Discard on time — date marks are for safety, not just inventory. Practice checkpoint (17/20 in temps): teach \"Date marking\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what…",
            ),
            _b(
                "Thermometer habits",
                "Calibrate bi-metal thermometers with ice-point or boiling-point methods. Clean and sanitize probes between foods. Probe the thickest part. Glass thermometers do not belong in food. Log temperatures when required — inspectors look for consistent control, not one lucky reading. Practice checkpoint (18/20 in temps): teach \"Thermometer habits\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the…",
            ),
            _b(
                "Time as a public health control",
                "Some operations use time alone for pizza, sushi rice, or buffet items under written procedures — typically up to four hours from leaving temperature control, then discard. Labels must show when time started. If your site is not approved for this, do not improvise; use temperature control instead. Practice checkpoint (19/20 in temps): teach \"Time as a public health control\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket,…",
            ),
            _b(
                "Module wrap — temperatures",
                "You practiced danger zone, TCS, cold and hot holding, cook temps, cooling, reheating, thawing, receiving, date marks, and thermometers. Next module: contamination, allergens, pests, and inspection readiness. Practice checkpoint (20/20 in temps): teach \"Module wrap — temperatures\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture…",
            ),
        ),
        _FOOD_DISCLAIMER,
    ),
    CertLessonTemplate(
        "alameda-food-contamination",
        CertTrackId.ALAMEDA_FOOD_HANDLER,
        "CA / Alameda food handler — Contamination (3/6)",
        "Module 3: cross-contamination, sanitizing, pests, allergens, inspections.",
        18,
        (
            _b(
                "Cross-contamination basics",
                "Cross-contamination spreads pathogens from raw foods, dirty surfaces, cloths, or hands onto ready-to-eat foods. Keep raw and ready-to-eat paths separate. Wash-rinse-sanitize boards and utensils between uses. Never let raw juices drip onto other foods in storage or prep. Practice checkpoint (1/20 in contamination): teach \"Cross-contamination basics\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then…",
            ),
            _b(
                "Color-coded boards and tools",
                "Many kitchens use color-coded boards — for example red for raw meat, yellow for raw poultry, green for produce, blue for seafood, white for dairy or bakery. Follow your chart even when the line is busy. If colors are not used, wash-rinse-sanitize thoroughly between every product change. Practice checkpoint (2/20 in contamination): teach \"Color-coded boards and tools\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in…",
            ),
            _b(
                "Situation: Same knife raw then RTE",
                "Example: A cook slices raw chicken, wipes the knife on an apron, and cuts tomatoes for salsa. That wipe does nothing useful. Wash, rinse, and sanitize the knife and board — or switch to a clean set — before touching ready-to-eat produce. Aprons are not sanitizers. Practice checkpoint (3/20 in contamination): teach \"Situation: Same knife raw then RTE\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass),…",
            ),
            _b(
                "Clean then sanitize",
                "Scrape or rinse debris, wash with detergent, rinse, sanitize at the correct concentration and contact time, then air dry. Sanitizing a dirty surface does not work — soil consumes sanitizer. Follow label directions for chlorine, quaternary ammonium, or iodine products. Practice checkpoint (4/20 in contamination): teach \"Clean then sanitize\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the…",
            ),
            _b(
                "Sanitizer strength and strips",
                "Mix sanitizer per label. Verify with test strips matched to your chemical — chlorine, quat, or iodine each need the right paper. Replace solutions when dirty, weak, or past the change schedule. Too strong can leave chemical residue; too weak fails to kill pathogens. Practice checkpoint (5/20 in contamination): teach \"Sanitizer strength and strips\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then…",
            ),
            _b(
                "Situation: Cloudy sanitizer bucket",
                "Example: The sanitizer bucket is cloudy with food bits and a strip reads under range. Dump it, clean the bucket, remix to the correct ppm, retest, and only then wipe food-contact surfaces. A dirty bucket spreads soil instead of sanitizing. Practice checkpoint (6/20 in contamination): teach \"Situation: Cloudy sanitizer bucket\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what…",
            ),
            _b(
                "FIFO stock rotation",
                "First In, First Out: place new stock behind older product and use the oldest first. Check dates when stocking. FIFO reduces spoilage and the chance of serving expired TCS foods. Combine with date marking for prepared items. Practice checkpoint (7/20 in contamination): teach \"FIFO stock rotation\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it…",
            ),
            _b(
                "Pest prevention",
                "Deny pests food, water, and shelter: seal gaps, store food sealed and off the floor, clean spills fast, and remove clutter. Keep dumpsters closed. Use licensed pest control — do not spray pesticides over food, prep areas, or equipment yourself. Practice checkpoint (8/20 in contamination): teach \"Pest prevention\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if…",
            ),
            _b(
                "Situation: Droppings in dry storage",
                "Example: You find rodent droppings near flour bags. Do not sweep them into a corner and open for service. Stop using affected product, notify a manager, isolate the area, and follow pest-control and discard guidance. Inspect packages for gnaw marks before restocking. Practice checkpoint (9/20 in contamination): teach \"Situation: Droppings in dry storage\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass),…",
            ),
            _b(
                "Allergen cross-contact",
                "Allergen protein can transfer on shared oil, fryers, grills, tongs, cutting boards, and gloves. Cleaning alone may not remove residues — use dedicated equipment when required and wash thoroughly. Communicate allergen tickets clearly from front of house to kitchen. Practice checkpoint (10/20 in contamination): teach \"Allergen cross-contact\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the…",
            ),
            _b(
                "FDA Big 9 list",
                "Memorize the Big 9: milk, eggs, fish, Crustacean shellfish, tree nuts, peanuts, wheat, soybeans, and sesame. Sesame labeling is relatively newer — check ingredients on sauces, breads, and spice blends. Regional menus may add other sensitivities; still verify every ticket. Practice checkpoint (11/20 in contamination): teach \"FDA Big 9 list\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the…",
            ),
            _b(
                "Situation: Shared fryer allergen",
                "Example: French fries share oil with breaded shrimp. A guest with shellfish allergy asks if fries are safe. If oil is shared, the honest answer may be no. Do not hide shared equipment. Offer an alternative cooked in a clean pan if available, or decline safely. Practice checkpoint (12/20 in contamination): teach \"Situation: Shared fryer allergen\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the…",
            ),
            _b(
                "Chemical contamination",
                "Store chemicals below and away from food, utensils, and linens. Label spray bottles. Never reuse food containers for chemicals. Follow SDS guidance. If chemical contacts food or food-contact surfaces, discard food and clean per procedure before reopening the station. Practice checkpoint (13/20 in contamination): teach \"Chemical contamination\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the…",
            ),
            _b(
                "Physical hazards",
                "Glass, metal shards, bones, plastic, bandages, and jewelry can injure guests. Use scoops with handles, keep lights shielded, and discard food if glass breaks nearby. Report equipment that sheds parts. Physical hazards are as serious as biological ones on an inspection. Practice checkpoint (14/20 in contamination): teach \"Physical hazards\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the…",
            ),
            _b(
                "Common pathogens overview",
                "Salmonella links to poultry and eggs; STEC to ground beef and produce; Listeria to deli and cold ready-to-eat foods; norovirus to hands and ready-to-eat foods; Campylobacter to undercooked poultry. Control with hygiene, correct cooking and holding, and excluding sick workers. Practice checkpoint (15/20 in contamination): teach \"Common pathogens overview\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass),…",
            ),
            _b(
                "Produce washing",
                "Wash fruits and vegetables under running water before cutting, even if you peel them — knives carry surface soil into the flesh. Do not use soap on food. Handle sprouts and pre-cut leafy greens as higher-risk TCS items with cold holding. Practice checkpoint (16/20 in contamination): teach \"Produce washing\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you…",
            ),
            _b(
                "Health inspections",
                "Alameda County Environmental Health inspects for critical violations that can cause illness — handwashing, temperatures, contamination, sick workers — and for good retail practices. Keep logs current, fix problems immediately, and ask supervisors when unsure. Be honest with inspectors. Practice checkpoint (17/20 in contamination): teach \"Health inspections\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or…",
            ),
            _b(
                "If a guest gets sick",
                "Take complaints seriously. Notify a manager right away. Preserve suspected food if instructed. Do not guess medical causes or argue with the guest. Cooperate with investigators. Document what was served and when if asked by management. Practice checkpoint (18/20 in contamination): teach \"If a guest gets sick\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if…",
            ),
            _b(
                "Situation: Inspector at the door",
                "Example: An inspector arrives during lunch rush. Stay calm, continue safe practices, and answer questions honestly. Do not hide dirty pans or turn off cold-holding alarms. Managers typically accompany the inspector; your job is to keep working safely and provide logs when asked. Practice checkpoint (19/20 in contamination): teach \"Situation: Inspector at the door\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf,…",
            ),
            _b(
                "Module wrap — contamination",
                "You covered cross-contamination, cleaning and sanitizing, FIFO, pests, allergens, chemicals, physical hazards, pathogens, produce, and inspections. Next: cleaning systems and facilities in depth. Practice checkpoint (20/20 in contamination): teach \"Module wrap — contamination\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture…",
            ),
        ),
        _FOOD_DISCLAIMER,
    ),
    CertLessonTemplate(
        "alameda-food-cleaning",
        CertTrackId.ALAMEDA_FOOD_HANDLER,
        "CA / Alameda food handler — Cleaning & facilities (4/6)",
        "Module 4: warewashing, surfaces, cloths, sinks, ice, chemicals, closing.",
        18,
        (
            _b(
                "Why cleaning is food safety",
                "Cleaning removes soil; sanitizing reduces pathogens on already clean surfaces. Together they protect guests as much as cooking temperatures do. A sparkling dirty kitchen — grease with sanitizer sprayed on top — still fails. Build cleaning into every task, not only closing. Practice checkpoint (1/20 in cleaning): teach \"Why cleaning is food safety\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then…",
            ),
            _b(
                "Three-compartment sink",
                "Typical setup: wash (detergent, hot water), rinse (clean water), sanitize (correct ppm and contact time), then air dry. Scrape before the wash bay. Do not combine steps in one basin. Keep sinks for warewashing — not for handwashing or dumping mop water. Practice checkpoint (2/20 in cleaning): teach \"Three-compartment sink\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what…",
            ),
            _b(
                "Dishmachine basics",
                "Follow the machine’s temperature or chemical sanitizing requirements. Scrape and rack so spray arms can reach every surface. Check gauge readings or test strips per policy. If the machine fails, switch to the three-compartment sink method rather than serving on dirty dishes. Practice checkpoint (3/20 in cleaning): teach \"Dishmachine basics\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the…",
            ),
            _b(
                "Food-contact surfaces",
                "Food-contact surfaces — boards, knives, prep tables, slicer parts, thermometer probes — need wash, rinse, sanitize between raw and ready-to-eat uses and on a schedule during continuous use. Non-food-contact surfaces still need regular cleaning so they do not become pest or soil reservoirs. Practice checkpoint (4/20 in cleaning): teach \"Food-contact surfaces\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or…",
            ),
            _b(
                "Situation: After raw fish prep",
                "Example: You finish butchering raw fish on a table that will next hold garnishes. Clear debris, wash with detergent, rinse, sanitize with tested solution, air dry or wipe with sanitized cloth per policy, then set up garnishes. Skipping to a quick wipe leaves pathogens for the next ticket. Practice checkpoint (5/20 in cleaning): teach \"Situation: After raw fish prep\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in…",
            ),
            _b(
                "Wiping cloths",
                "Store wiping cloths in sanitizer solution between uses. Do not leave damp cloths on counters overnight — they grow bacteria. Use separate cloths for food-contact and heavy soil if your policy requires it. Replace solution when cloudy. Practice checkpoint (6/20 in cleaning): teach \"Wiping cloths\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it…",
            ),
            _b(
                "Situation: Cloth left overnight",
                "Example: A wet towel sits on a cutting board all night. In the morning it smells sour. Do not use it on food-contact surfaces. Send it to laundry, wash and sanitize the board, and remix sanitizer. Train the team that “we’ll clean later” cloths become contamination tools. Practice checkpoint (7/20 in cleaning): teach \"Situation: Cloth left overnight\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then…",
            ),
            _b(
                "Handwashing sinks stay dedicated",
                "Handwashing sinks need soap, towels or dryers, warm water, and clear access. Never dump mop water, rinse produce, or wash dishes in a hand sink. Blocked hand sinks are a common critical violation because they stop people from washing when they should. Practice checkpoint (8/20 in cleaning): teach \"Handwashing sinks stay dedicated\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode —…",
            ),
            _b(
                "Situation: Mop water in hand sink",
                "Example: Someone dumps mop water in the handwashing sink during rush. Stop that practice. Mop water belongs in the service sink. Clean and sanitize the hand sink, restock soap and towels, and remind the team — inspectors treat blocked or misused hand sinks seriously. Practice checkpoint (9/20 in cleaning): teach \"Situation: Mop water in hand sink\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then…",
            ),
            _b(
                "Floors, walls, ceilings",
                "Clean floors regularly so grease and food debris do not attract pests. Keep walls and ceilings free of peeling paint and mold. Repair standing water issues. Facility condition supports every other food safety control — pests and mold follow neglect. Practice checkpoint (10/20 in cleaning): teach \"Floors, walls, ceilings\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes…",
            ),
            _b(
                "Restroom readiness",
                "Employee and guest restrooms need soap, towels or dryers, hot water, and regular cleaning. Stock before rush. A restroom without soap breaks the handwashing chain that protects the kitchen. Practice checkpoint (11/20 in cleaning): teach \"Restroom readiness\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture the next sixty seconds…",
            ),
            _b(
                "Garbage and grease",
                "Empty garbage before it overflows. Keep indoor cans clean and lined. Outdoor dumpsters stay closed and away from open receiving doors when possible. Manage grease traps per schedule — grease buildup attracts pests and creates slip and odor hazards. Practice checkpoint (12/20 in cleaning): teach \"Garbage and grease\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong…",
            ),
            _b(
                "Water and ice safety",
                "Use potable water for food and ice. Clean ice machines on schedule. Store ice scoops outside the ice with handles up — never in the bin. Ice is food; bare hands do not belong in the ice machine. Practice checkpoint (13/20 in cleaning): teach \"Water and ice safety\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture the next sixty…",
            ),
            _b(
                "Chemical storage",
                "Keep cleaners and sanitizers in labeled bottles, stored away from food and single-use items. Never mix chemicals. Know where the SDS binder lives. Train new hires before they handle concentrates. Practice checkpoint (14/20 in cleaning): teach \"Chemical storage\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture the next sixty…",
            ),
            _b(
                "Situation: Bleach beside flour",
                "Example: A bottle of bleach concentrate sits on a dry-storage shelf beside open flour. Move chemicals to the chemical area immediately, check whether flour was contaminated, and discard if unsure. Retrain whoever stocked the shelf — this is a classic chemical-contamination setup. Practice checkpoint (15/20 in cleaning): teach \"Situation: Bleach beside flour\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or…",
            ),
            _b(
                "Clean-in-place equipment",
                "Slicers, mixers, and soft-serve machines need disassembly per manufacturer instructions. “Wipe down” is not enough for parts that touch food. Schedule deep cleans and tag equipment that is mid-cleaning so nobody uses a half-sanitized slicer. Practice checkpoint (16/20 in cleaning): teach \"Clean-in-place equipment\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong…",
            ),
            _b(
                "Closing cleaning checklist",
                "Closing is when many contamination problems start: crumb-filled toasters, dirty pop nozzles, greasy hoods, and uncovered food. Follow a written checklist — surfaces, equipment, floors, trash, pest scan — and initial it. Morning shifts inherit whatever night left behind. Practice checkpoint (17/20 in cleaning): teach \"Closing cleaning checklist\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the…",
            ),
            _b(
                "Who cleans what",
                "Line cooks sanitize their stations; dishwashers own warewashing; managers verify chemical strength and machine temps. Ambiguous ownership means nothing gets cleaned. Know your zone and escalate broken equipment instead of working around it silently. Practice checkpoint (18/20 in cleaning): teach \"Who cleans what\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong…",
            ),
            _b(
                "Ventilation and grease",
                "Grease-laden vapor coats hoods and walls. Follow hood-cleaning schedules. Report firesafety issues with suppression systems to managers immediately. Grease buildup is a fire and pest hazard as well as a sanitation problem. Practice checkpoint (19/20 in cleaning): teach \"Ventilation and grease\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during…",
            ),
            _b(
                "Module wrap — cleaning",
                "You covered warewashing, food-contact surfaces, cloths, hand sinks, facilities, ice, chemicals, equipment, and closing routines. Next: pathogens and high-risk guests in more depth. Practice checkpoint (20/20 in cleaning): teach \"Module wrap — cleaning\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture the next sixty seconds on a…",
            ),
        ),
        _FOOD_DISCLAIMER,
    ),
    CertLessonTemplate(
        "alameda-food-pathogens",
        CertTrackId.ALAMEDA_FOOD_HANDLER,
        "CA / Alameda food handler — Pathogens & high-risk (5/6)",
        "Module 5: major pathogens, vulnerable guests, outbreak response.",
        18,
        (
            _b(
                "How people get sick from food",
                "Foodborne illness comes from biological hazards (bacteria, viruses, parasites), chemical hazards, and physical hazards. Most kitchen outbreaks involve contaminated hands, undercooked TCS foods, cooling failures, or sick employees working. Your habits are the control system. Practice checkpoint (1/20 in pathogens): teach \"How people get sick from food\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass),…",
            ),
            _b(
                "Bacteria, viruses, parasites, toxins",
                "Bacteria can grow in food when FAT TOM conditions allow. Viruses like norovirus do not grow in food but spread easily on hands. Parasites may arrive with undercooked seafood or contaminated water. Some bacteria make toxins that cooking will not destroy — cooling and holding still matter. Practice checkpoint (2/20 in pathogens): teach \"Bacteria, viruses, parasites, toxins\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket,…",
            ),
            _b(
                "Norovirus deep dive",
                "Norovirus is highly contagious and a leading cause of foodborne illness from infected food handlers. It spreads through vomit particles, feces, and contaminated ready-to-eat foods. Exclusion, ruthless handwashing, and staying off the line when sick are the main defenses — cooking helps less for foods served raw. Practice checkpoint (3/20 in pathogens): teach \"Norovirus deep dive\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer…",
            ),
            _b(
                "Salmonella",
                "Salmonella is linked to poultry, eggs, and produce. Prevent with correct cook temperatures, no cross-contamination from raw poultry juices, and refrigerated egg storage. Report diagnosed Salmonella to management for exclusion rules. Practice checkpoint (4/20 in pathogens): teach \"Salmonella\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during…",
            ),
            _b(
                "STEC and ground beef",
                "Shiga toxin-producing E. coli links to undercooked ground beef and contaminated produce. Grinders spread surface bacteria into the center — that is why ground beef needs higher temps than a whole steak. Wash hands and boards after raw beef. Practice checkpoint (5/20 in pathogens): teach \"STEC and ground beef\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if…",
            ),
            _b(
                "Listeria and cold RTE foods",
                "Listeria monocytogenes can grow at refrigerator temperatures and is linked to deli meats, soft cheeses, and cold ready-to-eat foods. Clean cold rooms, respect date marks, and be especially careful with high-risk guests. Do not leave opened deli chubs forever. Practice checkpoint (6/20 in pathogens): teach \"Listeria and cold RTE foods\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure…",
            ),
            _b(
                "Hepatitis A",
                "Hepatitis A spreads from infected workers to food, especially ready-to-eat items. Vaccination policies may apply in some jurisdictions. Exclusion after diagnosis is mandatory. Handwashing after restroom use is critical. Practice checkpoint (7/20 in pathogens): teach \"Hepatitis A\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture…",
            ),
            _b(
                "Clostridium botulinum",
                "Botulism links to improper canning, reduced-oxygen packaging, and garlic-in-oil held warm. Never use bulging or damaged cans. Follow approved procedures for vacuum packaging — do not invent sous-vide rules on the fly. Practice checkpoint (8/20 in pathogens): teach \"Clostridium botulinum\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush.…",
            ),
            _b(
                "Clostridium perfringens",
                "Perfringens thrives when large batches of meat stews and gravies cool too slowly. Spores survive cooking; bacteria grow during long danger-zone cooling. Portion shallow and cool fast — this pathogen is a classic banquet and catering failure. Practice checkpoint (9/20 in pathogens): teach \"Clostridium perfringens\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong…",
            ),
            _b(
                "Staphylococcus aureus",
                "Staph toxins come from infected cuts and hands; toxin can survive reheating. Prevent with handwashing, glove rules, covering wounds, and not working with infected sores. Temperature abuse lets toxin form in foods like protein salads. Practice checkpoint (10/20 in pathogens): teach \"Staphylococcus aureus\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you…",
            ),
            _b(
                "High-risk populations",
                "Young children, older adults, pregnant people, and immunocompromised guests get sicker from the same pathogens. Hospitals, nursing homes, daycare, and similar operations often ban undercooked eggs or rare ground beef. When you cater or serve these groups, follow the stricter rules. Practice checkpoint (11/20 in pathogens): teach \"High-risk populations\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass),…",
            ),
            _b(
                "Situation: Nursing home catering",
                "Example: Your restaurant caters a nursing home lunch. Use pasteurized eggs if required, cook ground meats fully, keep cold foods cold on the road, and exclude any sick staff from the event. A “normal” restaurant shortcut can become an outbreak in a vulnerable population. Practice checkpoint (12/20 in pathogens): teach \"Situation: Nursing home catering\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass),…",
            ),
            _b(
                "Symptoms to take seriously",
                "Vomiting, diarrhea, fever, jaundice, and severe cramps after a meal may signal foodborne illness — but many causes exist. Staff who hear guest reports escalate to managers. Staff with those symptoms do not work food handling until cleared. Practice checkpoint (13/20 in pathogens): teach \"Symptoms to take seriously\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong…",
            ),
            _b(
                "Outbreak response basics",
                "If multiple guests report illness, management may preserve samples, pull menu items, deepen cleaning, and cooperate with environmental health. Your role: honest timelines, no discarded evidence, and continued safe practices. Rumors on social media still need a professional kitchen response. Practice checkpoint (14/20 in pathogens): teach \"Outbreak response basics\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf,…",
            ),
            _b(
                "Situation: Three guests report illness",
                "Example: Three tickets from last night’s banquet call with similar symptoms. Tell a manager immediately. Do not dump the leftover banquet pans. Do not accuse a coworker in the dining room. Document what you know and let leadership work with the health department. Practice checkpoint (15/20 in pathogens): teach \"Situation: Three guests report illness\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass),…",
            ),
            _b(
                "FAT TOM growth conditions",
                "Bacteria need Food, Acidity, Time, Temperature, Oxygen, and Moisture (FAT TOM) in the right ranges. You cannot change physics, but you control time and temperature every shift. Limit how long TCS foods sit in the danger zone — that is the practical FAT TOM lever on the line. Practice checkpoint (16/20 in pathogens): teach \"FAT TOM growth conditions\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then…",
            ),
            _b(
                "Spores and cooling",
                "Some bacteria form spores that survive cooking. If cooling is slow, spores return to active growth. That is why the two-step cooling rule exists. Reheating later may kill cells but not always undo toxin problems — prevent growth in the first place. Practice checkpoint (17/20 in pathogens): teach \"Spores and cooling\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes…",
            ),
            _b(
                "Ready-to-eat contamination routes",
                "Ready-to-eat foods get contaminated by hands, raw drip, dirty cloths, pests, and unclean equipment. Because there is no final kill step, prevention is everything. Treat every salad, garnish, and bread basket as a high-care item. Practice checkpoint (18/20 in pathogens): teach \"Ready-to-eat contamination routes\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if…",
            ),
            _b(
                "Prevention hierarchy",
                "Rank controls: keep sick workers off the line, wash hands, cook and hold correctly, cool fast, prevent cross-contamination, clean and sanitize, control allergens and chemicals. If a shortcut skips the top of that list, it is not a shortcut — it is a risk. Practice checkpoint (19/20 in pathogens): teach \"Prevention hierarchy\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what…",
            ),
            _b(
                "Module wrap — pathogens",
                "You studied major pathogens, high-risk guests, outbreak response, and prevention hierarchy. Final module: receiving, storage, and service — where food enters and leaves your control. Practice checkpoint (20/20 in pathogens): teach \"Module wrap — pathogens\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture the next sixty seconds…",
            ),
        ),
        _FOOD_DISCLAIMER,
    ),
    CertLessonTemplate(
        "alameda-food-service",
        CertTrackId.ALAMEDA_FOOD_HANDLER,
        "CA / Alameda food handler — Receiving & service (6/6)",
        "Module 6: suppliers, storage, buffets, ice, logs, inspection readiness.",
        18,
        (
            _b(
                "Approved suppliers",
                "Buy from approved reputable suppliers. Home-prepared foods generally cannot be served in a permitted food facility. Inspect supplier practices when management asks you to help with vendor checks. If a deal looks too cheap and the truck is warm, walk away. Practice checkpoint (1/20 in service): teach \"Approved suppliers\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes…",
            ),
            _b(
                "Receiving inspection checklist",
                "Check temperatures, package integrity, dates, pest evidence, and signs of thaw-refreeze. Accept into cold storage quickly. Reject and document problems. Do not leave TCS deliveries on a hot dock while you finish unrelated tasks. Practice checkpoint (2/20 in service): teach \"Receiving inspection checklist\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you…",
            ),
            _b(
                "Situation: Warm dairy delivery",
                "Example: Milk arrives at 50°F on a summer afternoon. Reject it. Do not “use it fast” to avoid waste. Temperature-abused dairy can already support pathogen growth. Tell the vendor and your manager, and keep the cold chain standard consistent for every delivery. Practice checkpoint (3/20 in service): teach \"Situation: Warm dairy delivery\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure…",
            ),
            _b(
                "Dry storage rules",
                "Keep dry goods six inches off the floor, away from walls enough to clean, and under 50–70°F when possible per policy. Seal bags after opening. Separate chemicals completely. Rotate with FIFO and watch for pests in cardboard. Practice checkpoint (4/20 in service): teach \"Dry storage rules\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during…",
            ),
            _b(
                "Cold storage organization",
                "Top to bottom typically: ready-to-eat, seafood, whole cuts, ground meats, poultry — so raw juices drip downward onto lower-risk storage only. Cover food. Do not overload. Keep a working thermometer visible. Practice checkpoint (5/20 in service): teach \"Cold storage organization\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture…",
            ),
            _b(
                "Situation: Chicken above lettuce",
                "Example: A pan of raw chicken sits on a shelf above uncovered lettuce. Move the chicken below, cover both, and discard lettuce if juices may have dripped. Retrain the stocking pattern — this is one of the most common and most preventable contamination setups. Practice checkpoint (6/20 in service): teach \"Situation: Chicken above lettuce\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure…",
            ),
            _b(
                "Hot holding during service",
                "During service, check hot wells and check temps on a schedule. Stir soups. Replace pans rather than mixing tiny leftovers into fresh product if policy forbids it. Keep sneeze guards in place on buffets. Practice checkpoint (7/20 in service): teach \"Hot holding during service\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture the…",
            ),
            _b(
                "Buffet and self-service",
                "Provide clean plates for returns — guests should not refill dirty plates. Use long-handled utensils. Maintain hot and cold barriers. Assign a staff member to monitor the buffet when required. Label allergens clearly. Practice checkpoint (8/20 in service): teach \"Buffet and self-service\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush.…",
            ),
            _b(
                "Situation: Dirty plate refill",
                "Example: A guest returns to the buffet with a used plate. Politely offer a clean plate. Used plates bring saliva and leftovers back to the common utensils. This is a standard control — practice the script so it feels natural during rush. Practice checkpoint (9/20 in service): teach \"Situation: Dirty plate refill\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong…",
            ),
            _b(
                "Leftovers and takeout",
                "Cool leftovers with the two-step method if saving. Label and date. For takeout, remind guests that food safety continues at home — but your responsibility includes correct cook and hold before it leaves. Do not send temperature-abused food out the door to avoid waste. Practice checkpoint (10/20 in service): teach \"Leftovers and takeout\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure…",
            ),
            _b(
                "Ice scoop hygiene",
                "Store scoops in a clean holder outside the ice, handle up. Never leave the scoop buried in ice. Wash and sanitize scoops on schedule. Guests and staff both watch this — it is a visible trust signal. Practice checkpoint (11/20 in service): teach \"Ice scoop hygiene\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture the next sixty…",
            ),
            _b(
                "Situation: Scoop in the ice",
                "Example: You find the scoop handle buried in the ice bin. Remove it, discard ice that may be contaminated per policy, wash and sanitize the scoop and bin as required, and retrain. Bare-hand and handle contamination of ice is a common inspection finding. Practice checkpoint (12/20 in service): teach \"Situation: Scoop in the ice\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode —…",
            ),
            _b(
                "Service utensils and sneeze guards",
                "Utensils need clean handles and regular swap-outs. Sneeze guards must actually shield food. Replace dropped utensils — five-second rules are not a food code. Keep serving spoons out of pockets and aprons. Practice checkpoint (13/20 in service): teach \"Service utensils and sneeze guards\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush.…",
            ),
            _b(
                "Bare hand vs utensils at service",
                "Plating ready-to-eat foods for service still needs barriers where required. Garnishing with bare hands after touching raw tickets breaks the chain. Stage clean tongs and gloves at the pass. Practice checkpoint (14/20 in service): teach \"Bare hand vs utensils at service\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture the next…",
            ),
            _b(
                "Closing: discard vs save",
                "Know what must be discarded at close — time-control items, abused hot hold, uncovered food with pest risk. What you save must be cooled, covered, labeled, and stored correctly. Closing decisions are food safety decisions, not only cost decisions. Practice checkpoint (15/20 in service): teach \"Closing: discard vs save\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes…",
            ),
            _b(
                "Temperature logs habit",
                "Logs prove control when memory fails. Record walk-in, hot hold, cook checks, and cooling as required. Fake logs are worse than missing logs — inspectors and managers notice patterns that do not match reality. Practice checkpoint (16/20 in service): teach \"Temperature logs habit\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what goes wrong if you skip it during rush. Picture…",
            ),
            _b(
                "Alameda inspection readiness",
                "Stay ready for Alameda County Environmental Health: stocked hand sinks, working thermometers, labeled chemicals, pest-free storage, and trained staff who can explain procedures. Prep-only practice here supports that readiness — it does not replace official training. Practice checkpoint (17/20 in service): teach \"Alameda inspection readiness\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the…",
            ),
            _b(
                "Situation: Critical violation found",
                "Example: An inspector cites no soap at the kitchen hand sink. Fix it immediately — restock, then check every other hand sink. Critical violations are about preventing illness now, not arguing later. Ask your manager how to document the correction. Practice checkpoint (18/20 in service): teach \"Situation: Critical violation found\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode —…",
            ),
            _b(
                "Finish with the official course",
                "This six-module track is practice for California food handler card topics used in Alameda County workplaces. It is not county-accredited training. Review your employer’s approved course materials, then take the official assessment for your card. Practice checkpoint (19/20 in service): teach \"Finish with the official course\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer, board color, sanitizer bucket, walk-in shelf, or pass), then the failure mode — what…",
            ),
            _b(
                "Full course recap",
                "You covered hygiene and illness, temperatures, contamination and allergens, cleaning and facilities, pathogens and high-risk guests, and receiving through service — about two hours of food handler prep with situations and examples. Revisit weak modules, drill the numbers (41, 135, 165, two-step cooling), and keep every shift inspection-ready. Practice checkpoint (20/20 in service): teach \"Full course recap\" to a new hire in under a minute. Start with the rule, then the tool or station (hand sink, thermometer,…",
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
    lang = normalize_language(language)
    template = _find_template(track or CertTrackId.CA_DMV_PERMIT, lesson_id)
    category = CATEGORIES[template.track]
    jurisdiction = JURISDICTIONS[template.track]
    slides: list[CourseSlide] = []
    translated_count = 0
    for i, beat in enumerate(template.beats):
        key = beat.key or slide_key_for(beat.title, lesson_id=template.lesson_id)
        # English kits stay keyed by slide_key (correct_index / kind from EN).
        kit = kit_for_slide(slide_key=key, title=beat.title, body=beat.body)
        tr = translate_cert_slide(key, lang)
        if tr is not None:
            translated_count += 1
            slide_title = tr.title
            slide_body_base = tr.body
            slide_say = tr.say
            slide_activity = tr.activity
            examples = list(tr.examples) if tr.examples else list(kit.examples)
            quiz_prompt = tr.quiz_prompt or kit.quiz_prompt
            quiz_choices = list(tr.quiz_choices) if tr.quiz_choices else list(kit.quiz_choices)
            quiz_explanation = tr.quiz_explanation or kit.quiz_explanation
            game_prompt = tr.game_prompt or kit.game_prompt
            game_options = list(tr.game_options) if tr.game_options else list(kit.game_options)
            game_steps = list(tr.game_steps) if tr.game_steps else list(kit.game_steps)
        else:
            slide_title = beat.title
            slide_body_base = beat.body
            slide_say = beat.say
            slide_activity = beat.activity
            examples = list(kit.examples)
            quiz_prompt = kit.quiz_prompt
            quiz_choices = list(kit.quiz_choices)
            quiz_explanation = kit.quiz_explanation
            game_prompt = kit.game_prompt
            game_options = list(kit.game_options)
            game_steps = list(kit.game_steps)
        body = format_body_with_examples(slide_body_base, examples)
        narration = narration_with_examples(slide_say, examples)
        slide = CourseSlide(
                index=i,
                slide_key=key,
                title=slide_title,
                body=body,
                narration=narration,
                picture_url=picture_data_url(
                    title=slide_title, symbol=beat.symbol, color=beat.color
                ),
                picture_alt=f"Picture for {slide_title}",
                video_url=motion_data_url(
                    title=slide_title,
                    symbol=beat.symbol,
                    color=beat.color,
                    bounce_px=20,
                    bounce_dur_s=2.4,
                ),
                video_caption=f"Watch: {slide_title}",
                activity_prompt=slide_activity,
                examples=examples,
                modalities=list(CERT_MODALITIES),
                quiz_spec={
                    "prompt": quiz_prompt,
                    "choices": quiz_choices,
                    "correct_index": kit.quiz_correct_index,
                    "explanation": quiz_explanation,
                },
                game_spec={
                    "kind": kit.game_kind,
                    "prompt": game_prompt,
                    "options": game_options,
                    "correct_index": kit.game_correct_index,
                    "steps": game_steps,
                },
                tags=[
                    "certification_prep",
                    template.track.value,
                    jurisdiction,
                    template.lesson_id,
                    category.value,
                    "picture_led",
                    "motion_clip",
                    "storyboard",
                    "multimodal",
                    "examples",
                    "quiz",
                    "game",
                ],
            )
        slide.avatar_script = avatar_script_for_slide(slide)
        slides.append(slide)
    used_curated = translated_count > 0
    spoken_language = lang if used_curated else "en"
    if used_curated:
        translation_source = "curated"
        translation_note = f"Curated {lang} overlay for {translated_count}/{len(slides)} slides."
        if lang in NEEDS_NATIVE_REVIEW:
            translation_note += " Needs native review."
    else:
        translation_source = "english"
        translation_note = (
            f"English source; no curated overlay for language={lang!r}."
            if lang != "en"
            else "English source."
        )
    minutes = max(
        CERT_SESSION_MIN_MINUTES,
        min(CERT_SESSION_MAX_MINUTES, template.estimated_minutes),
    )
    return StudioCourse(
        course_id=f"cert-{uuid.uuid4().hex[:10]}",
        title=title or template.title,
        category=category,
        language=lang,
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
            "picture_led": True,
            "motion_clip": True,
            "read_aloud": True,
            "multimodal": True,
            "modalities": list(CERT_MODALITIES),
            "examples_per_segment": True,
            "quiz_per_segment": True,
            "game_per_segment": True,
            "spoken_language": spoken_language,
            "translation_source": translation_source,
            "translation_note": translation_note,
        },
        created_at_ms=int(time.time() * 1000),
        status="ready",
    )


class CertTracksResponse(BaseModel):
    default_track: str = CertTrackId.CA_DMV_PERMIT.value
    tracks: list[dict] = Field(default_factory=list)
    courses: list[CertCourseOption] = Field(default_factory=list)
