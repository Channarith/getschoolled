"""Tests for certification course storyboards (DMV + food handler)."""

from __future__ import annotations

import pytest

from aoep_shared.cert_storyboard import (
    STORYBOARD_LESSONS,
    has_storyboard,
    render_scene_svg,
    storyboard_for_lesson,
    storyboard_for_slide,
)
from aoep_shared.cert_storyboard.art import BACKDROPS, SPRITES
from aoep_shared.cert_storyboard.catalog import storyboard_scene_for_slide


LIVE_LESSONS = (
    "ca-dmv-permit-basics",
    "ca-dmv-permit-signs",
    "ca-dmv-permit-sharing",
    "drivers-permit-test",
    "ca-alameda-food-handler-hygiene",
    "ca-alameda-food-handler-temps",
    "ca-alameda-food-handler-contamination",
    "food-handler-safety",
)


@pytest.mark.parametrize("lesson_id", LIVE_LESSONS)
def test_live_lessons_have_storyboards(lesson_id: str) -> None:
    assert has_storyboard(lesson_id)
    segments = storyboard_for_lesson(lesson_id, include_svg=False)
    assert len(segments) >= 10
    for i, seg in enumerate(segments):
        assert seg["slide_index"] == i
        assert seg["title"]
        assert seg["narration"]
        assert seg["backdrop"] in BACKDROPS
        assert seg["cast"]
        assert any(c["kind"] in SPRITES for c in seg["cast"])


@pytest.mark.parametrize("lesson_id", LIVE_LESSONS)
def test_every_slide_renders_animated_svg(lesson_id: str) -> None:
    for i in range(10):
        seg = storyboard_scene_for_slide(lesson_id, i)
        assert seg is not None, f"missing scene {lesson_id}#{i}"
        svg = render_scene_svg(seg.scene)
        assert svg.startswith("<svg")
        assert "keyframes" in svg or "@keyframes" in svg
        assert seg.scene.title in svg or "Storyboard" in svg
        # Cast sprites or callouts present
        assert "<g class=\"cast\"" in svg or "<g class=\"callout\"" in svg


def test_storyboard_slide_api_shape() -> None:
    data = storyboard_for_slide("ca-dmv-permit-basics", 7, include_svg=True)
    assert data is not None
    assert data["scene_id"]
    assert data["svg"].startswith("<svg")
    assert data["svg_data_url"].startswith("data:image/svg+xml")
    assert "school" in data["title"].lower() or "bus" in data["narration"].lower()


def test_food_handwashing_scene_has_sink_and_soap() -> None:
    seg = storyboard_scene_for_slide("ca-alameda-food-handler-hygiene", 2)
    assert seg is not None
    kinds = {c.kind for c in seg.scene.cast}
    assert "sink" in kinds
    assert "soap" in kinds


def test_dmv_emergency_scene_has_ambulance() -> None:
    seg = storyboard_scene_for_slide("ca-dmv-permit-sharing", 5)
    assert seg is not None
    kinds = {c.kind for c in seg.scene.cast}
    assert "ambulance" in kinds


def test_registry_lists_lessons() -> None:
    assert "ca-dmv-permit-basics" in STORYBOARD_LESSONS
    assert "ca-alameda-food-handler-temps" in STORYBOARD_LESSONS
