"""Lesson → storyboard catalog registry for cert prep courses."""

from __future__ import annotations

from typing import Any, Optional

from .catalog_dmv import build_dmv_basics, build_dmv_sharing, build_dmv_signs
from .catalog_food import (
    build_food_contamination,
    build_food_hygiene,
    build_food_temps,
)
from .types import SegmentStoryboard

# Canonical live-class lesson ids → builders. Aliases map studio / alternate ids.
_BUILDERS = {
    "ca-dmv-permit-basics": lambda: build_dmv_basics("ca-dmv-permit-basics"),
    "ca-dmv-basics": lambda: build_dmv_basics("ca-dmv-basics"),
    "drivers-permit-test": lambda: build_dmv_basics("drivers-permit-test"),
    "ca-dmv-permit-signs": lambda: build_dmv_signs("ca-dmv-permit-signs"),
    "ca-dmv-signs": lambda: build_dmv_signs("ca-dmv-signs"),
    "ca-dmv-permit-sharing": lambda: build_dmv_sharing("ca-dmv-permit-sharing"),
    "ca-dmv-sharing": lambda: build_dmv_sharing("ca-dmv-sharing"),
    "ca-alameda-food-handler-hygiene": lambda: build_food_hygiene(
        "ca-alameda-food-handler-hygiene"
    ),
    "alameda-food-hygiene": lambda: build_food_hygiene("alameda-food-hygiene"),
    "food-handler-safety": lambda: build_food_hygiene("food-handler-safety"),
    "ca-alameda-food-handler-temps": lambda: build_food_temps(
        "ca-alameda-food-handler-temps"
    ),
    "alameda-food-temps": lambda: build_food_temps("alameda-food-temps"),
    "ca-alameda-food-handler-contamination": lambda: build_food_contamination(
        "ca-alameda-food-handler-contamination"
    ),
    "alameda-food-contamination": lambda: build_food_contamination(
        "alameda-food-contamination"
    ),
}

STORYBOARD_LESSONS: tuple[str, ...] = tuple(sorted(_BUILDERS.keys()))


def has_storyboard(lesson_id: str) -> bool:
    return lesson_id in _BUILDERS


def _segments(lesson_id: str) -> list[SegmentStoryboard]:
    builder = _BUILDERS.get(lesson_id)
    if not builder:
        return []
    return builder()


def storyboard_for_lesson(
    lesson_id: str, *, include_svg: bool = True
) -> list[dict[str, Any]]:
    """Return all segment storyboards for a lesson as API-ready dicts."""
    return [s.to_dict(include_svg=include_svg) for s in _segments(lesson_id)]


def storyboard_for_slide(
    lesson_id: str, slide_index: int, *, include_svg: bool = True
) -> Optional[dict[str, Any]]:
    """Return one slide's storyboard, or None if missing."""
    for seg in _segments(lesson_id):
        if seg.slide_index == slide_index:
            return seg.to_dict(include_svg=include_svg)
    return None


def storyboard_scene_for_slide(lesson_id: str, slide_index: int) -> Optional[SegmentStoryboard]:
    for seg in _segments(lesson_id):
        if seg.slide_index == slide_index:
            return seg
    return None
