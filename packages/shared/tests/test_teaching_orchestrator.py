"""End-to-end: harvest -> teach -> present, fully offline (mock meeting)."""

import json

from aoep_shared.harvest import CourseTags, extract_text, generate_course
from aoep_shared.teaching import run_end_to_end
from aoep_shared.teaching.lesson import lesson_from_generated_course, teach_course

_SAMPLE = (
    "Introduction\nWelcome. This class covers cell biology objectives.\n\n"
    "History\nThe cell theory developed over centuries.\n\n"
    "Example 1\nA worked example of osmosis in a plant cell.\n\n"
    "Q&A\nCommon questions and answers about mitosis.\n\n"
    "Summary\nIn summary, cells are the basic unit of life.\n"
)


def test_lesson_fallback_has_intro_segments_outro():
    course = generate_course(extract_text(_SAMPLE, default_title="Cells"), subject="biology")
    lesson = teach_course(course, engine="fallback")
    assert lesson.engine == "fallback"
    assert lesson.steps[0].kind == "intro"
    assert lesson.steps[-1].kind == "outro"
    assert len(lesson.segments) == len(course.slides)
    assert lesson.full_narration.strip()


def test_run_end_to_end_offline(tmp_path):
    tags = CourseTags(access_tier="free", core_fundamental=True)
    result = run_end_to_end(
        text=_SAMPLE, subject="biology", tags=tags,
        out_dir=tmp_path / "e2e", teach_engine="fallback",
        meeting_provider="mock", present=True,
    )
    d = result.to_dict()
    # Part 1
    assert d["course"]["subject"] == "biology"
    assert 0 <= d["course"]["composition_score"] < 1000
    assert "core-fundamental" in d["course"]["tags"]
    # Part 2
    assert d["lesson"]["engine"] == "fallback"
    assert d["lesson"]["segments"] >= 5
    # Part 3
    assert d["meeting"]["provider_used"] == "mock"
    assert d["meeting"]["join_url"].startswith("https://meet.local/mock/")
    assert d["presentation"]["steps_presented"] == d["lesson"]["steps"]

    # Artifacts written to disk and the manifest is self-consistent.
    for key in ("course_json", "pptx", "lesson_plan", "lesson_script",
                "presentation_plan", "presentation_result", "manifest"):
        assert key in result.artifacts
    manifest = json.loads((tmp_path / "e2e" / "manifest.json").read_text())
    assert manifest["course"]["composition_score"] == d["course"]["composition_score"]


def test_run_end_to_end_plan_only(tmp_path):
    result = run_end_to_end(text=_SAMPLE, subject="biology",
                            out_dir=tmp_path / "plan", present=False)
    assert result.presentation is None
    assert result.join_url == ""
    assert "presentation_plan" in result.artifacts
    assert "presentation_result" not in result.artifacts
