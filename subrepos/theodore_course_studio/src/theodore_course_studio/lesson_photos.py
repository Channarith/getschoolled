"""Photographic plates for a lesson page, with a PowerPoint entrance.

Geometric storyboards stay available for tests and exports. The lesson stage
shows one of these photographs instead, and each page uses a different entrance.
"""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).with_name("avatar_static") / "lesson_photos"
_PREFIX = "/api/studio/avatar/lesson_photos"

TRANSITIONS = ("fade", "fly", "wipe", "zoom", "cover", "split")

# Earlier rules win. Phrases are matched against the slide title and body.
_RULES: tuple[tuple[str, ...], str] = (
    (("stop sign", "stop signs", "yield", "red light", "traffic signal"), "lesson-stop.jpg"),
    (("night", "headlight", "headlights", "after dark", "dusk"), "lesson-night-road.jpg"),
    (("school", "school bus", "crosswalk", "pedestrian", "children"), "lesson-school-zone.jpg"),
    (("highway", "freeway", "lane", "steering", "following", "speed"), "lesson-driving.jpg"),
    (("intersection", "right of way", "right-of-way", "turn signal"), "lesson-intersection.jpg"),
    (("handwash", "hand wash", "wash your hands", "gloves", "hygiene", "illness"), "lesson-handwash.jpg"),
    (("thermometer", "temperature", "cooking", "reheat", "danger zone", "holding"), "lesson-kitchen.jpg"),
    (("refrigerat", "fridge", "storage", "allergen", "contamin", "fifo", "sanitize"), "lesson-fridge.jpg"),
)


def photo_plate(*, title: str, body: str = "", category: str = "", index: int = 0) -> dict[str, str]:
    """Return the photo URL and entrance for this slide. URL is empty if the file is missing."""
    text = f"{title} {body}".lower()
    filename = ""
    for keys, name in _RULES:
        if any(key in text for key in keys):
            filename = name
            break
    if not filename:
        cat = (category or "").lower()
        if "food" in cat:
            filename = "lesson-kitchen.jpg"
        elif "driv" in cat:
            filename = "lesson-intersection.jpg"
        else:
            filename = "lesson-classroom.jpg"
    if not (_DIR / filename).is_file():
        return {"url": "", "transition": "fade", "file": ""}
    return {
        "url": f"{_PREFIX}/{filename}",
        "transition": TRANSITIONS[int(index) % len(TRANSITIONS)],
        "file": filename,
    }
