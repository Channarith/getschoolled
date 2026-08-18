"""Stable slide_key ids for cert (and other) slides.

Avatar cues and multimodal kits used to key off English titles. Once a
slide is translated (Khmer, etc.) that lookup breaks. Every cert beat
ships a permanent slide_key that stays English-derived and never changes
when the displayed title is localized.
"""

from __future__ import annotations

TITLE_TO_SLIDE_KEY: dict[str, str] = {
    'Prep, not a DMV course': 'ca-dmv-basics.prep-not-a-dmv-course',
    "California learner's permit": 'ca-dmv-basics.california-learner-s-permit',
    'Right-of-way at stops': 'ca-dmv-basics.right-of-way-at-stops',
    'California speed basics': 'ca-dmv-basics.california-speed-basics',
    'Following distance': 'ca-dmv-basics.following-distance',
    'Signals and lane changes': 'ca-dmv-basics.signals-and-lane-changes',
    'Turning and red lights': 'ca-dmv-basics.turning-and-red-lights',
    'School buses in California': 'ca-dmv-basics.school-buses-in-california',
    'Seat belts and phones': 'ca-dmv-basics.seat-belts-and-phones',
    'DUI limits (California)': 'ca-dmv-basics.dui-limits-california',
    'What to do after a crash': 'ca-dmv-basics.what-to-do-after-a-crash',
    'Study next': 'ca-dmv-basics.study-next',
    'Regulatory signs': 'ca-dmv-signs.regulatory-signs',
    'Yield and stop': 'ca-dmv-signs.yield-and-stop',
    'Warning signs': 'ca-dmv-signs.warning-signs',
    'Guide and service signs': 'ca-dmv-signs.guide-and-service-signs',
    'Traffic signals': 'ca-dmv-signs.traffic-signals',
    'Pavement markings': 'ca-dmv-signs.pavement-markings',
    'Railroad crossings': 'ca-dmv-signs.railroad-crossings',
    'Roundabouts': 'ca-dmv-signs.roundabouts',
    'Parking clearances': 'ca-dmv-signs.parking-clearances',
    'Night headlights': 'ca-dmv-signs.night-headlights',
    'Pedestrians and bikes': 'ca-dmv-sharing.pedestrians-and-bikes',
    'Motorcycle awareness': 'ca-dmv-sharing.motorcycle-awareness',
    'Large truck no-zones': 'ca-dmv-sharing.large-truck-no-zones',
    'Freeway merging': 'ca-dmv-sharing.freeway-merging',
    'Weather and hydroplaning': 'ca-dmv-sharing.weather-and-hydroplaning',
    'Emergency vehicles': 'ca-dmv-sharing.emergency-vehicles',
    'Work zones': 'ca-dmv-sharing.work-zones',
    'Before you drive': 'ca-dmv-sharing.before-you-drive',
    'Handbook checkpoint': 'ca-dmv-sharing.handbook-checkpoint',
    'Practice test habit': 'ca-dmv-sharing.practice-test-habit',
    'Prep card, not accreditation': 'alameda-food-hygiene.prep-card-not-accreditation',
    'Why food handler cards matter': 'alameda-food-hygiene.why-food-handler-cards-matter',
    'Handwashing that works': 'alameda-food-hygiene.handwashing-that-works',
    'Gloves done right': 'alameda-food-hygiene.gloves-done-right',
    'Illness reporting': 'alameda-food-hygiene.illness-reporting',
    'Personal cleanliness': 'alameda-food-hygiene.personal-cleanliness',
    'Ready-to-eat foods': 'alameda-food-hygiene.ready-to-eat-foods',
    'Cuts and bandages': 'alameda-food-hygiene.cuts-and-bandages',
    'Customer allergen basics': 'alameda-food-hygiene.customer-allergen-basics',
    'Your next short block': 'alameda-food-hygiene.your-next-short-block',
    'Temperature danger zone': 'alameda-food-temps.temperature-danger-zone',
    'Cold holding': 'alameda-food-temps.cold-holding',
    'Hot holding': 'alameda-food-temps.hot-holding',
    'Safe cooking targets': 'alameda-food-temps.safe-cooking-targets',
    'Cooling cooked food': 'alameda-food-temps.cooling-cooked-food',
    'Reheating': 'alameda-food-temps.reheating',
    'Thawing safely': 'alameda-food-temps.thawing-safely',
    'Receiving checks': 'alameda-food-temps.receiving-checks',
    'Date marking': 'alameda-food-temps.date-marking',
    'Thermometer habits': 'alameda-food-temps.thermometer-habits',
    'Cross-contamination': 'alameda-food-contamination.cross-contamination',
    'Clean then sanitize': 'alameda-food-contamination.clean-then-sanitize',
    'Sanitizer strength': 'alameda-food-contamination.sanitizer-strength',
    'FIFO stock rotation': 'alameda-food-contamination.fifo-stock-rotation',
    'Pest prevention': 'alameda-food-contamination.pest-prevention',
    'Allergen cross-contact': 'alameda-food-contamination.allergen-cross-contact',
    'Common pathogens': 'alameda-food-contamination.common-pathogens',
    'Health inspections': 'alameda-food-contamination.health-inspections',
    'If a guest gets sick': 'alameda-food-contamination.if-a-guest-gets-sick',
    'Finish strong': 'alameda-food-contamination.finish-strong',
}

SLIDE_KEY_TO_TITLE: dict[str, str] = {v: k for k, v in TITLE_TO_SLIDE_KEY.items()}

ALL_CERT_SLIDE_KEYS: frozenset[str] = frozenset(TITLE_TO_SLIDE_KEY.values())


def slide_key_for(title: str, *, lesson_id: str = "") -> str:
    """Return the stable key for an English title, or derive one.

    ``lesson_id`` is only used when the title is not in the curated map.
    """
    known = TITLE_TO_SLIDE_KEY.get(title)
    if known:
        return known
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:48] or "slide"
    prefix = (lesson_id or "course").strip() or "course"
    return f"{prefix}.{slug}"


def register_title_aliases(store: dict) -> None:
    """Copy title-keyed entries under their slide_key so either lookup works."""
    for title, key in TITLE_TO_SLIDE_KEY.items():
        if title in store and key not in store:
            store[key] = store[title]
