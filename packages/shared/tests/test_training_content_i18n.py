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
    assert normalize_training_locale("fr") == "en"
    assert normalize_training_locale(None) == "en"


def test_localize_course_title():
    assert localize_course_title("Budgeting Basics", "es") == "Fundamentos del presupuesto"
    assert localize_course_title("Budgeting Basics", "zh") == "预算基础"
    assert localize_course_title("Ancient Egypt", "es") == "Ancient Egypt"


def test_localize_facts_returns_spanish_bullets():
    facts, loc = localize_facts("Budgeting Basics", "es")
    assert loc == "es"
    assert facts is not None
    assert any("presupuesto" in f.lower() for f in facts)


def test_knowledge_course_spanish_training_body():
    course = get_course("audio-budgeting-basics", "en", training_locale="es")
    assert course is not None
    assert course.body_locale == "es"
    assert "Fundamentos del presupuesto" in course.title
    key_seg = next(s for s in course.segments if "presupuesto" in s.text.lower())
    assert key_seg.heading  # localized heading from catalog_i18n


def test_list_courses_includes_training_locale():
    out = list_courses(locale="en", training_locale="zh", limit=3)
    assert out["training_locale"] == "zh"
    assert "body_locale" in out["courses"][0]


def test_build_catalog_training_locale_defaults_from_ui_locale():
    courses = build_catalog("es")
    budgeting = next(c for c in courses if c.id == "audio-budgeting-basics")
    assert budgeting.body_locale == "es"


@pytest.mark.parametrize("tloc,needle", [
    ("es", "presupuesto"),
    ("zh", "预算"),
])
def test_budgeting_facts_in_training_locale(tloc, needle):
    course = get_course("audio-budgeting-basics", locale="en", training_locale=tloc)
    assert course is not None
    joined = " ".join(s.text for s in course.segments)
    assert needle in joined
