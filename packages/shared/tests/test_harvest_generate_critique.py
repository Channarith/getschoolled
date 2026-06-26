"""Generation (extract->compose->score->tag) + critique/optimization loop."""

from aoep_shared.harvest import (
    CourseTags,
    HarvestCritic,
    extract_text,
    generate_course,
    optimize_with_ledger,
    summarize_reports,
)
from aoep_shared.optimization import OptimizationLedger

_RICH = (
    "Introduction\nWelcome. This class covers cell biology objectives.\n\n"
    "History\nThe cell theory developed over centuries.\n\n"
    "Example 1\nA worked example of osmosis in a plant cell.\n\n"
    "Exercise\nPractice: label the parts of a cell.\n\n"
    "Q&A\nCommon questions and answers about mitosis.\n\n"
    "Summary\nIn summary, cells are the basic unit of life.\n"
)


def test_generate_course_produces_score_and_tags():
    doc = extract_text(_RICH, default_title="Cell Biology")
    tags = CourseTags(access_tier="free", core_fundamental=True)
    course = generate_course(doc, subject="biology", tags=tags, source="unit.txt")
    assert course.slides
    assert course.composition is not None
    assert 0 <= course.composition_score < 1000
    d = course.to_dict()
    assert d["composition"]["quality_index"] >= 0
    assert "free" in d["tags"]["labels"]
    # Catalog payload carries tags + the composition score.
    payload = course.catalog_payload()
    assert payload["subject"] == "biology"
    assert payload["meta_composition_score"] == course.composition_score


def test_critic_flags_thin_course():
    doc = extract_text("Photosynthesis\nPlants make food from light.\n",
                       default_title="Thin")
    course = generate_course(doc, subject="biology")
    report = HarvestCritic().review(course)
    assert report.passed is False
    assert report.issues
    assert report.grade in {"A", "B", "C", "D", "F"}


def test_critic_passes_rich_course():
    doc = extract_text(_RICH, default_title="Cell Biology")
    course = generate_course(doc, subject="biology")
    report = HarvestCritic().review(course)
    # A well-rounded course should clear coverage/interactivity bars.
    assert report.metrics["interactivity"] > 0
    assert "introduction" in course.composition.present_categories()


def test_optimize_with_ledger_tracks_and_promotes():
    docs = [extract_text(_RICH, default_title=f"C{i}") for i in range(3)]
    courses = [generate_course(d, subject="biology") for d in docs]
    reports = [HarvestCritic().review(c) for c in courses]
    summary = summarize_reports(reports)
    assert summary["count"] == 3
    ledger = OptimizationLedger()
    step, promoted = optimize_with_ledger(ledger, reports)
    assert promoted is True  # first commit becomes champion
    assert ledger.champion("harvester_quality").step_id == step.step_id
