"""On-demand lesson visuals for student asks (offline SVG / animations)."""

from __future__ import annotations

from aoep_shared.lesson_visuals import (
    extract_us_states,
    generate_lesson_visual,
    wants_visual,
)


def test_wants_visual_for_compare_and_license():
    assert wants_visual("Can you compare California and Texas driver's licenses?")
    assert wants_visual("Show me an example of a safe left turn")
    assert not wants_visual("ok")


def test_extract_states():
    states = extract_us_states("differences between california and texas licenses")
    abbrs = {a for _, a in states}
    assert "CA" in abbrs and "TX" in abbrs


def test_license_compare_generates_svg_and_frames():
    vis = generate_lesson_visual(
        "Discuss the differences between California and New York for a driver's license",
        force=True,
    )
    assert vis is not None
    assert "<svg" in vis.svg.lower()
    assert vis.frames
    assert vis.narration
    assert "California" in vis.title or "license" in vis.title.lower()
    d = vis.to_dict()
    assert d["has_animation"] is True
    assert d["sync"] == "with_audio"


def test_generic_scene_visual():
    vis = generate_lesson_visual("Show me a picture of kitchen food safety", force=True)
    assert vis is not None
    assert "<svg" in vis.svg.lower()
