from __future__ import annotations

from theodore_course_studio.assessment import build_pop_quiz_for_slide
from theodore_course_studio.cert_multimodal import (
    CERT_MODALITIES,
    _KITS,
    coverage_report,
    kit_for_title,
    preferred_modalities,
)
from theodore_course_studio.certification_prep import build_cert_course, list_cert_courses
from theodore_course_studio.engagement import pick_game_for_slide
from theodore_course_studio.knowledge import LearningObjective
from theodore_course_studio.types import LearnerProfileScores


def test_every_cert_title_has_curated_kit():
    missing = []
    for row in list_cert_courses():
        course = build_cert_course(lesson_id=row.lesson_id)
        for slide in course.slides:
            if slide.title not in _KITS:
                missing.append(slide.title)
    assert missing == [], missing
    assert coverage_report()["curated_kits"] >= 120


def test_every_segment_is_multimodal():
    for row in list_cert_courses():
        course = build_cert_course(lesson_id=row.lesson_id)
        assert course.profile_adaptations.get("multimodal") is True
        for slide in course.slides:
            assert len(slide.examples) >= 2, slide.title
            assert "Examples:" in slide.body
            assert slide.modalities == list(CERT_MODALITIES)
            assert slide.quiz_spec.get("choices")
            assert slide.game_spec
            assert slide.picture_url.startswith("data:image/svg+xml")
            assert slide.video_url.startswith("data:image/svg+xml")
            assert slide.activity_prompt


def test_curated_quiz_and_game_used():
    course = build_cert_course(lesson_id="ca-dmv-basics")
    slide = next(s for s in course.slides if s.title == "Following distance")
    obj = LearningObjective(
        objective_id="o1",
        course_id=course.course_id,
        title=slide.title,
        description=slide.body,
        slide_indexes=[slide.index],
    )
    quiz = build_pop_quiz_for_slide(slide, obj)
    assert "three seconds" in " ".join(quiz.choices).lower() or quiz.explanation
    game = pick_game_for_slide(slide, objective_id="o1")
    assert game.prompt
    assert game.payload


def test_preferred_modalities_rank_quiz_high():
    order = preferred_modalities(
        {
            "learn_from_quiz": 1.0,
            "learn_from_images": 0.1,
            "learn_from_text": 0.1,
            "learn_from_video": 0.1,
            "learn_from_examples": 0.1,
            "learn_from_games": 0.1,
            "learn_from_activity": 0.1,
        }
    )
    assert order[0] == "quiz"


def test_teach_payload_includes_learning_kit(tmp_path):
    from theodore_course_studio.generate import CourseBuilder
    from theodore_course_studio.teach import TeachEngine

    course = build_cert_course(lesson_id="alameda-food-temps")
    builder = CourseBuilder(data_dir=tmp_path / "data")
    builder.save_course(course)
    engine = TeachEngine(builder)
    start = engine.start(
        session_id="mm1",
        course_id=course.course_id,
        learner_id="learner-mm",
        use_voice_agent=False,
        profile=LearnerProfileScores(learn_from_video=1.0, learn_from_quiz=0.9),
    )
    kit = start["learning_kit"]
    assert kit["has_examples"] is True
    assert kit["has_quiz"] is True
    assert kit["has_game"] is True
    assert kit["has_video"] is True
    assert "video" in kit["preferred"][:3]
    assert start["examples"]
    assert "nudge_video_learners" in (start["turn"]["adaptations_applied"] or [])


def test_studio_mentions_multimodal_cert_copy():
    from fastapi.testclient import TestClient

    from theodore_course_studio.main import app

    page = TestClient(app).get("/studio")
    assert page.status_code == 200
    assert "examples, quiz, and a game" in page.text
    assert "pf-quiz" in page.text
    assert "teach-examples" in page.text


def test_kit_for_unknown_title_synthesizes():
    kit = kit_for_title("Totally unknown topic", "Remember to stay safe always.")
    assert len(kit.examples) >= 2
    assert kit.quiz_choices
