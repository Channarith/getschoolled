from __future__ import annotations

from pathlib import Path

from theodore_course_studio.corpus import scan_corpus, write_corpus_index
from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.profile_adapt import adapt_slide
from theodore_course_studio.review_store import ReviewStore
from theodore_course_studio.teach import TeachEngine
from theodore_course_studio.training_run import run_training_pass
from theodore_course_studio.types import CourseSlide, LearnerProfileScores, QualityLabel


def _mini_corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    (root / "Leadership").mkdir(parents=True)
    good = root / "Leadership" / "Leadership#1_Good_Demo_Source_PDF.pdf"
    bad = root / "Leadership" / "Leadership#2_Bad_Skip_Me_PDF.pdf"
    # Minimal valid-ish PDF bytes are hard; leave empty files — extract may error,
    # training run should still index labels.
    good.write_bytes(b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    bad.write_bytes(b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    # Text fallback source for course build when PDF extract is empty:
    # create a tiny pptx-like path that extract will fail, and instead inject
    # via review/build using a synthetic course in later tests.
    return root


def test_scan_and_training_run_indexes_labels(tmp_path: Path, monkeypatch):
    root = _mini_corpus(tmp_path)
    data_dir = tmp_path / "data"
    docs = scan_corpus(root)
    assert len(docs) == 2
    labels = {d.quality_label for d in docs}
    assert QualityLabel.GOOD in labels
    assert QualityLabel.BAD in labels
    write_corpus_index(docs, data_dir=data_dir)

    report = run_training_pass(
        corpus_root=root,
        data_dir=data_dir,
        extract_text=False,
        seed_page_hints=False,
    )
    assert report.documents_scanned == 2
    assert len(report.incorporate_ids) == 1
    assert len(report.reject_ids) == 1


def test_review_comments_and_page_verdicts(tmp_path: Path):
    store = ReviewStore(data_dir=tmp_path / "data")
    store.set_page_verdict(source_id="src-a", page_index=2, marked_reject=True, comment="circle mark")
    store.add_comment(source_id="src-a", body="Too dense — shorten for Theodore", page_index=2)
    pages = store.pages_for("src-a")
    assert pages[0].marked_reject is True
    comments = store.comments_for(source_id="src-a")
    assert comments[0].body.startswith("Too dense")


def test_profile_adapt_shortens_when_fatigued():
    slide = CourseSlide(
        index=0,
        title="Listening",
        body="First idea. Second idea. Third idea stays long.",
        narration="First idea. Second idea. Third idea stays long.",
    )
    turn = adapt_slide(
        slide,
        LearnerProfileScores(fatigue=0.8, attention=0.3),
    )
    assert "shorten_for_fatigue_or_low_attention" in turn.adaptations_applied
    assert "Third idea" not in turn.narration


def test_teach_engine_advances(tmp_path: Path):
    data_dir = tmp_path / "data"
    builder = CourseBuilder(data_dir=data_dir)
    from theodore_course_studio.types import CategoryId, StudioCourse

    c = StudioCourse(
        course_id="course-demo",
        title="Demo",
        category=CategoryId.LEADERSHIP,
        slides=[
            CourseSlide(index=0, title="One", body="Alpha point.", narration="Alpha point."),
            CourseSlide(index=1, title="Two", body="Beta point.", narration="Beta point."),
        ],
        status="ready",
    )
    builder.save_course(c)
    engine = TeachEngine(builder)
    first = engine.start(session_id="s1", course_id="course-demo")
    assert first["turn"]["title"] == "One"
    assert first["progress"]["total_objectives"] == 2
    assert first["media"]
    assert first["animation"]["enter"] == "fade-up"
    second = engine.advance("s1")
    assert second["turn"]["title"] == "Two"
    pop = engine.pop_quiz("s1")
    assert pop.choices
    graded = engine.answer_pop("s1", pop.correct_index)
    assert graded["result"]["passed"] is True
