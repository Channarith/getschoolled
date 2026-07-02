"""Tests for worked examples and media export."""

import re

from aoep_shared.harvest import extract_text, generate_course
from aoep_shared.harvest.examples import extract_worked_examples
from aoep_shared.harvest.media import export_course_media, pick_demo_video


def test_extract_worked_examples_from_code():
    text = (
        "The for loop walks a list.\n\n"
        "  for name in [\"Ada\", \"Alan\"]:\n"
        "      print(name)\n"
    )
    ex = extract_worked_examples(text, "Loops", subject="python")
    assert ex
    assert "for name" in ex[0].body
    assert ex[0].source == "extracted"
    assert ex[0].title.startswith("Worked:")


def test_synthesizes_concrete_math_not_meta_example():
    ex = extract_worked_examples(
        "Variables represent unknown values in expressions.",
        "Variables",
        subject="mathematics",
    )
    assert ex
    assert ex[0].source == "synthesized"
    assert "example of" not in ex[0].narration.lower()
    assert re.search(r"\d", ex[0].body)
    assert "=" in ex[0].body


def test_synthesizes_user_style_linear_system():
    ex = extract_worked_examples(
        "Solve simultaneous equations with three unknowns.",
        "Systems",
        subject="algebra",
    )
    assert ex
    body = ex[0].body
    assert "A + B = 10" in body or "x + y = 7" in body
    assert "example of an example" not in body.lower()


def test_skips_meta_example_sentences():
    text = (
        "This is an example of an example for illustration only. "
        "For example, we might discuss things. "
        "Given A + B = 10 and A + C = 12, solve for A."
    )
    ex = extract_worked_examples(text, "Systems", subject="algebra")
    assert ex
    assert any("A + B" in e.body or "A + C" in e.body for e in ex)


def test_generate_includes_example_slides():
    text = (
        "Introduction\nWelcome to algebra; we cover solving equations.\n\n"
        "Linear systems\nA + B = 10 and A + C = 12 with B + C = 9.\n\n"
        "Summary\nIn summary, algebra finds unknowns.\n"
    )
    course = generate_course(extract_text(text, default_title="Algebra"), subject="mathematics")
    assert any(s.category == "example" for s in course.slides)
    worked = [s for s in course.slides if s.category == "example"]
    assert any(re.search(r"\d", s.body) for s in worked)


def test_media_manifest_written(tmp_path):
    text = "Intro\nHello world with enough words to pass filters here today.\n"
    course = generate_course(extract_text(text, default_title="Demo"), subject="ai")
    manifest = export_course_media(
        course, tmp_path, synthesize_audio=False, attach_demo_videos=True,
        repo_root=tmp_path,
    )
    assert manifest.slides
    assert (tmp_path / "media_manifest.json").is_file()


def test_pick_demo_video_for_ai():
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]  # repo root from packages/shared/tests
    rel = pick_demo_video(subject="ai", title="Patterns", repo_root=root)
    if (root / "docs/demos/salareen_20_minute_expert.mp4").is_file():
        assert rel == "docs/demos/salareen_20_minute_expert.mp4"
