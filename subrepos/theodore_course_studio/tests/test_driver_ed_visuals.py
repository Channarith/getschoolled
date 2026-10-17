"""Driver Ed slides teach with a drawn road scene, a sign, and a few short points."""

from __future__ import annotations

import re

import pytest

from theodore_course_studio.certification_prep import CertTrackId, build_cert_program
from theodore_course_studio.driver_ed_visuals import (
    MAX_POINTS,
    ROAD_SCENE_LAYOUT,
    key_points,
    road_scene_timeline,
    scene_for,
)
from theodore_course_studio.teach import _visual_timeline
from theodore_course_studio.traffic_signs import sign_for_title
from theodore_course_studio.types import CategoryId, CourseSlide

_FILLER = re.compile(r"name the shape and color|decide before you move|teach the rule in one sentence", re.I)


@pytest.fixture(scope="module")
def program(tmp_path_factory):
    course = build_cert_program(track=CertTrackId.CA_DMV_PERMIT, data_dir=tmp_path_factory.mktemp("dmv"))
    assert course.category == CategoryId.DRIVER_EDUCATION
    return course


def _spoken(slide: CourseSlide) -> str:
    return slide.narration or slide.body or slide.title


def test_every_driver_ed_slide_gets_a_road_scene(program):
    assert len(program.slides) > 50
    scenes = set()
    for index, slide in enumerate(program.slides):
        if (slide.presentation_style or "").strip():
            continue
        timeline = _visual_timeline(slide, index, _spoken(slide), program.category)
        assert timeline["layout"] == ROAD_SCENE_LAYOUT, slide.title
        cues = timeline["cues"]
        assert 1 <= len(cues) <= MAX_POINTS
        persistent = [layer for layer in cues[0]["layers"] if layer.get("persistent")]
        assert len(persistent) == 1
        svg = persistent[0]["svg"]
        assert svg.startswith("<svg") and 'role="img"' in svg and "aria-label=" in svg and "<title>" in svg
        assert not re.search(r"https?://(?!www\.w3\.org/)", svg), slide.title
        assert persistent[0]["alt"]
        points = next(layer for layer in cues[0]["layers"] if layer["kind"] == "keypoints")["items"]
        assert 1 <= len(points) <= MAX_POINTS
        for point in points:
            assert not _FILLER.search(point), point
            assert len(point.split()) <= 17, point
        scenes.add(timeline["scene_id"])
    assert len(scenes) >= 8


def test_sign_slides_draw_their_sign(program):
    signed = 0
    for index, slide in enumerate(program.slides):
        sign = sign_for_title(slide.title)
        if sign is None or (slide.presentation_style or "").strip():
            continue
        timeline = _visual_timeline(slide, index, _spoken(slide), program.category)
        assert timeline.get("sign"), slide.title
        signed += 1
    assert signed > 10


def test_key_points_cue_with_the_narration():
    slide = CourseSlide(
        index=0,
        title="Stop sign",
        body="Come to a full stop at the limit line. Look left, right, then left again. Go only when the way is clear.",
    )
    sentences = [part.strip() + "." for part in slide.body.split(".") if part.strip()]
    base = {"layout": "layered", "duration_s": 9.0, "cues": []}
    timeline = road_scene_timeline(slide, base, sentences)
    assert [cue["layers"][-1]["active"] for cue in timeline["cues"]] == [0, 1, 2]
    starts = [cue["start_s"] for cue in timeline["cues"]]
    assert starts == sorted(starts) and starts[0] == 0
    assert scene_for(slide).scene_id == "intersection"
    assert key_points(slide)[0].startswith("Come to a full stop")


def test_other_courses_keep_their_own_timeline():
    slide = CourseSlide(index=0, title="Leading a meeting", body="Open with the goal. Close with owners.")
    timeline = _visual_timeline(slide, 0, slide.body, CategoryId.LEADERSHIP)
    assert timeline.get("layout") != ROAD_SCENE_LAYOUT
