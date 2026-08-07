from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_course_studio.early_learning import (
    EarlyLevel,
    build_early_course,
    list_early_courses,
)
from theodore_course_studio.main import app
from theodore_course_studio.teach import TeachEngine
from theodore_course_studio.generate import CourseBuilder


def test_every_level_has_a_course():
    levels = {row.level for row in list_early_courses()}
    assert levels == set(EarlyLevel)


def test_pre_k_course_is_short_picture_led_and_read_aloud():
    course = build_early_course(level=EarlyLevel.PRE_K, topic_id="colors")
    assert course.audience == "pre_k"
    assert course.subject == "Colors"
    assert 5 <= len(course.slides) <= 10
    assert course.estimated_minutes <= 20
    for slide in course.slides:
        assert len(slide.title.split()) <= 4
        assert len(slide.body.split()) <= 10
        assert slide.narration
        assert slide.picture_url.startswith("data:image/svg+xml,")
        assert slide.video_url.startswith("data:image/svg+xml,")
        assert slide.picture_alt
        assert slide.video_caption
        assert slide.activity_prompt


def test_grade_two_content_stays_one_idea_per_slide():
    course = build_early_course(
        level=EarlyLevel.GRADE_2, topic_id="animal_habitats"
    )
    assert course.audience == "grade_2"
    assert course.subject == "Science"
    assert len(course.slides) <= 10
    assert all(len(slide.body.split()) <= 12 for slide in course.slides)


def test_animated_visual_contains_motion_and_works_offline():
    course = build_early_course(level=EarlyLevel.PRE_K, topic_id="shapes")
    motion = course.slides[0].video_url
    assert "http://" not in motion and "https://" not in motion
    decoded = __import__("urllib.parse").parse.unquote(motion.split(",", 1)[1])
    assert "<animate" in decoded
    assert "<svg" in decoded


def test_teach_preserves_curated_child_narration(tmp_path):
    course = build_early_course(
        level=EarlyLevel.KINDERGARTEN, topic_id="letter_sounds"
    )
    builder = CourseBuilder(data_dir=tmp_path / "data")
    builder.save_course(course)
    engine = TeachEngine(builder)
    payload = engine.start(
        session_id="kid-1",
        course_id=course.course_id,
        use_voice_agent=True,
    )
    # The generic xAI/local fallback must not replace carefully leveled text.
    assert payload["turn"]["narration"] == course.slides[0].narration
    assert payload["voice"]["provider"] == "curated-child-read-aloud"
    assert any(item["kind"] == "image" for item in payload["media"])
    assert any(item["kind"] == "video" for item in payload["media"])
    assert payload["activity_prompt"] == course.slides[0].activity_prompt


def test_early_learning_api_builds_and_persists_course(monkeypatch, tmp_path):
    # Main's builder is module-scoped; test the endpoint contract and generated
    # payload without relying on the repo's real course data.
    import theodore_course_studio.main as main_module

    builder = CourseBuilder(data_dir=tmp_path / "data")
    monkeypatch.setattr(main_module, "_builder", builder)
    monkeypatch.setattr(main_module, "_teach", TeachEngine(builder))
    client = TestClient(app)

    options = client.get("/api/studio/early-learning/options")
    assert options.status_code == 200
    assert len(options.json()["levels"]) == 4
    assert options.json()["default_level"] == "pre_k"

    made = client.post(
        "/api/studio/courses/early-learning",
        json={"level": "pre_k", "topic_id": "colors", "language": "en"},
    )
    assert made.status_code == 200
    payload = made.json()
    assert payload["audience"] == "pre_k"
    assert payload["slides"][0]["picture_url"].startswith("data:image/svg+xml,")
    assert builder.get_course(payload["course_id"]) is not None


def test_studio_defaults_to_children_builder():
    page = TestClient(app).get("/studio")
    assert page.status_code == 200
    assert "Make a children's lesson" in page.text
    assert "One idea per screen" in page.text
    assert "Read aloud" in page.text
    assert "Watch video" in page.text
    assert "Advanced: build from adult" in page.text

