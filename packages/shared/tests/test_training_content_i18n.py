"""Training content localization (en / es / zh lesson bodies)."""

from __future__ import annotations

import pytest

from aoep_shared.audio_courses import build_catalog, get_course, list_courses
from aoep_shared.training_content_i18n import (
    localize_course_title,
    localize_facts,
    normalize_training_locale,
)


def test_normalize_training_locale():
    assert normalize_training_locale("en") == "en"
    assert normalize_training_locale("es-MX") == "es"
    assert normalize_training_locale("zh-CN") == "zh"
    # Every platform-supported language is now accepted as a training locale.
    assert normalize_training_locale("fr") == "fr"
    assert normalize_training_locale("ja-JP") == "ja"
    # Unsupported codes still collapse to English.
    assert normalize_training_locale("xx") == "en"
    assert normalize_training_locale(None) == "en"


def test_uncurated_locale_falls_back_to_english_body():
    # No curated content and no translator registered (offline default) ->
    # English body, with body_locale reported honestly as "en" so the client
    # narrates with an English voice that matches the text.
    course = get_course("audio-what-is-blockchain", "en", training_locale="fr")
    assert course is not None
    assert course.body_locale == "en"


def test_body_translator_localizes_uncurated_locale():
    from aoep_shared.training_content_i18n import set_body_translator

    def fake_translate(text, source, target):
        return f"[{target}] {text}"

    set_body_translator(fake_translate)
    try:
        course = get_course("audio-what-is-blockchain", "en", training_locale="fr")
        assert course is not None
        assert course.body_locale == "fr"
        assert all(s.text.startswith("[fr] ") for s in course.segments)
    finally:
        set_body_translator(None)


def test_localize_course_title():
    assert localize_course_title("Budgeting Basics", "es") == "Fundamentos del presupuesto"
    assert localize_course_title("Budgeting Basics", "zh") == "预算基础"
    assert localize_course_title("Ancient Egypt", "es") == "Ancient Egypt"


def test_localize_facts_returns_spanish_bullets():
    facts, loc = localize_facts("Budgeting Basics", "es")
    assert loc == "es"
    assert facts is not None
    assert any("presupuesto" in f.lower() for f in facts)


def test_knowledge_course_spanish_title_keeps_full_offline_body():
    course = get_course("audio-budgeting-basics", "en", training_locale="es")
    assert course is not None
    # Offline, prefer the complete English lesson over the old three-fact
    # Spanish preview. A configured body translator localizes all segments.
    assert course.body_locale == "en"
    assert "Fundamentos del presupuesto" in course.title
    assert len(course.segments) >= 30
    assert course.duration_min >= 30


def test_list_courses_includes_training_locale():
    out = list_courses(locale="en", training_locale="zh", limit=3)
    assert out["training_locale"] == "zh"
    assert "body_locale" in out["courses"][0]


def test_build_catalog_training_locale_defaults_from_ui_locale():
    courses = build_catalog("es")
    budgeting = next(c for c in courses if c.id == "audio-budgeting-basics")
    assert budgeting.body_locale == "en"
    assert budgeting.duration_min >= 30


@pytest.mark.parametrize("tloc", ["es", "zh"])
def test_budgeting_full_course_can_be_translated(tloc):
    from aoep_shared.training_content_i18n import set_body_translator

    set_body_translator(lambda text, source, target: f"[{target}] {text}")
    try:
        course = get_course("audio-budgeting-basics", locale="en", training_locale=tloc)
        assert course is not None
        assert course.body_locale == tloc
        assert len(course.segments) >= 30
        assert all(s.text.startswith(f"[{tloc}] ") for s in course.segments)
    finally:
        set_body_translator(None)
