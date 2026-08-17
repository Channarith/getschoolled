"""Certification course storyboards — animated scenarios per slide/segment.

Provides full-scene SVG storyboards for California DMV permit prep and Alameda /
CA food-handler prep. Each curriculum slide maps to one animated scene with
backdrop, cast (cars, signs, pedestrians, kitchen props), camera move, object
callouts, and narration synced for TTS.

Public surface:
- ``storyboard_for_lesson(lesson_id)`` → list of segment dicts
- ``storyboard_for_slide(lesson_id, slide_index)`` → one segment
- ``render_scene_svg(scene)`` / ``scene_data_url(scene)`` → playable SVG
- ``has_storyboard(lesson_id)`` → bool
"""

from __future__ import annotations

from .catalog import (
    STORYBOARD_LESSONS,
    has_storyboard,
    storyboard_for_lesson,
    storyboard_for_slide,
)
from .render import render_scene_html, render_scene_svg, scene_data_url
from .types import Cast, ObjectCallout, Scene, SegmentStoryboard

__all__ = [
    "Cast",
    "ObjectCallout",
    "Scene",
    "SegmentStoryboard",
    "STORYBOARD_LESSONS",
    "has_storyboard",
    "storyboard_for_lesson",
    "storyboard_for_slide",
    "render_scene_svg",
    "render_scene_html",
    "scene_data_url",
]
