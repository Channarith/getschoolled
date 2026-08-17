"""Tests for certification course storyboards (DMV + food handler + driver-ed bank)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aoep_shared.cert_storyboard import (
    DRIVER_ED_LESSON_IDS,
    STORYBOARD_LESSONS,
    driver_scenario_count,
    has_storyboard,
    render_scene_svg,
    storyboard_for_lesson,
    storyboard_for_slide,
)
from aoep_shared.cert_storyboard.art import BACKDROPS, SPRITES
from aoep_shared.cert_storyboard.catalog import storyboard_scene_for_slide
from aoep_shared.cert_storyboard.driver_ed_bank import DRIVER_ED_LESSONS
from aoep_shared.cert_storyboard.generic import build_generic_storyboard
from aoep_shared.languages import SUPPORTED_LANGUAGES


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
        assert '<g class="cast"' in svg or '<g class="callout"' in svg


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


def test_driver_ed_bank_exceeds_200_scenarios() -> None:
    count = driver_scenario_count()
    assert count >= 200, count
    assert len(DRIVER_ED_LESSON_IDS) >= 20
    assert len(DRIVER_ED_LESSONS) == len(DRIVER_ED_LESSON_IDS)


def test_every_driver_ed_lesson_has_storyboard_and_curriculum() -> None:
    cur_root = Path(__file__).resolve().parents[3] / "sample-curriculum"
    titles: set[str] = set()
    for lesson_id in DRIVER_ED_LESSON_IDS:
        assert has_storyboard(lesson_id)
        segments = storyboard_for_lesson(lesson_id, include_svg=False)
        assert len(segments) >= 10
        lesson_dir = cur_root / lesson_id
        assert (lesson_dir / "lesson.txt").is_file(), lesson_id
        for seg in segments:
            titles.add(f"{lesson_id}:{seg['title']}")
            assert seg["backdrop"] in BACKDROPS
            assert any(c["kind"] in SPRITES for c in seg["cast"])
    assert len(titles) >= 200


@pytest.mark.parametrize("lesson_id", list(DRIVER_ED_LESSON_IDS)[::5])
def test_driver_ed_sample_svgs_render(lesson_id: str) -> None:
    seg = storyboard_scene_for_slide(lesson_id, 0)
    assert seg is not None
    svg = render_scene_svg(seg.scene)
    assert '<g class="cast"' in svg
    assert "@keyframes" in svg


def test_generic_storyboard_is_multimodal_and_profile_aware() -> None:
    visual = build_generic_storyboard(
        lesson_id="ai-fluency-essentials",
        slide_index=0,
        title="Prompt design",
        body="A clear prompt states the goal. It supplies context and constraints.",
        narration="Give the model a clear goal, useful context, and constraints.",
        profile={"primary_style": "visual"},
    )
    auditory = build_generic_storyboard(
        lesson_id="ai-fluency-essentials",
        slide_index=0,
        title="Prompt design",
        body="A clear prompt states the goal. It supplies context and constraints.",
        narration="Give the model a clear goal, useful context, and constraints.",
        profile={"primary_style": "auditory"},
    )
    assert visual.profile_mode == "visual"
    assert auditory.profile_mode == "auditory"
    assert len(visual.segment.scene.cast) > len(auditory.segment.scene.cast)
    assert visual.examples
    assert visual.activity_prompt
    assert visual.translation_ready is True
    assert len(SUPPORTED_LANGUAGES) >= 27
