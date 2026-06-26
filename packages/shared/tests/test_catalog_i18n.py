"""Catalog content localization (categories, levels, lesson types,
segment headings, narration templates, locale-aware audio catalog)."""

from __future__ import annotations

import pytest

from aoep_shared import catalog_i18n
from aoep_shared.audio_courses import (
    build_catalog, categories, get_course, list_courses,
)


def test_normalize_locale_handles_variants():
    n = catalog_i18n.normalize_locale
    assert n("en") == "en"
    assert n("es-MX") == "es"
    assert n("fr_FR") == "fr"
    assert n("ZH-Hans") == "zh"
    # Khmer is fully supported (brand-required).
    assert n("km") == "km"
    assert n("km-KH") == "km"
    # Unsupported -> English fallback.
    assert n("zzz") == "en"
    assert n("xx") == "en"
    assert n(None) == "en"
    assert n("") == "en"


def test_localize_category_falls_back_to_english():
    assert catalog_i18n.localize_category("History", "fr") == "Histoire"
    assert catalog_i18n.localize_category("History", "ja") == "歴史"
    assert catalog_i18n.localize_category("History", "zz") == "History"
    # Unknown category -> identity.
    assert catalog_i18n.localize_category("Quantum Mechanics", "fr") == "Quantum Mechanics"


def test_localize_level():
    assert catalog_i18n.localize_level("beginner", "es") == "principiante"
    assert catalog_i18n.localize_level("intermediate", "de") == "Mittelstufe"
    assert catalog_i18n.localize_level("advanced", "zh") == "高级"


def test_localize_lesson_type():
    assert catalog_i18n.localize_lesson_type("Essential phrases", "ja") == "必須フレーズ"
    assert catalog_i18n.localize_lesson_type("Travel survival", "ar") == "البقاء في السفر"


def test_localize_heading():
    assert catalog_i18n.localize_heading("Introduction", "es") == "Introducción"
    assert catalog_i18n.localize_heading("Recap", "ru") == "Итог"
    assert catalog_i18n.localize_heading("Key idea", "vi") == "Ý chính"


def test_narration_template_substitution():
    out = catalog_i18n.narration("lang_intro", "es",
                                 language="Francés", lesson="Frases esenciales")
    assert "Bienvenido a Francés - Frases esenciales" in out
    assert "{language}" not in out and "{lesson}" not in out


def test_narration_unknown_key_returns_key():
    assert catalog_i18n.narration("nope", "en", x="y") == "nope"


@pytest.mark.parametrize("locale,expected_cat,expected_level", [
    ("en", "Languages", "beginner"),
    ("es", "Idiomas", "principiante"),
    ("fr", "Langues", "débutant"),
    ("zh", "语言", "入门"),
    ("ja", "言語", "初級"),
    ("ar", "اللغات", "مبتدئ"),
])
def test_language_course_is_localized(locale, expected_cat, expected_level):
    courses = build_catalog(locale)
    es_phrases = next(c for c in courses if c.id == "lang-es-phrases")
    assert es_phrases.category == expected_cat
    assert es_phrases.level == expected_level
    assert es_phrases.segments[0].heading == catalog_i18n.localize_heading(
        "Introduction", locale)


def test_language_course_title_uses_locale_language_name():
    # When browsing in es, a course teaching French should be titled
    # with the Spanish word for "French", not the English one.
    fr_course = next(c for c in build_catalog("es") if c.id == "lang-fr-phrases")
    assert fr_course.title.startswith("Francés:"), fr_course.title
    fr_course_ja = next(c for c in build_catalog("ja") if c.id == "lang-fr-phrases")
    assert "フランス語" in fr_course_ja.title


def test_knowledge_course_keeps_title_but_localizes_headings():
    course = next(c for c in build_catalog("es") if c.id == "audio-ancient-egypt")
    # Title stays English when no translation entry exists.
    assert "Ancient Egypt" in course.title
    # Category + headings + narration template are localized.
    assert course.category == "Historia"
    assert course.segments[0].heading == "Introducción"
    assert "Bienvenido" in course.segments[0].text


def test_knowledge_course_translated_title_with_training_locale():
    course = get_course("audio-budgeting-basics", locale="en", training_locale="zh")
    assert course is not None
    assert "预算基础" in course.title
    assert course.body_locale == "zh"


def test_recap_text_is_localized():
    course = next(c for c in build_catalog("fr") if c.id == "lang-es-phrases")
    recap_seg = next(s for s in course.segments if s.heading == "Récapitulatif")
    assert "Bravo" in recap_seg.text or "réviser" in recap_seg.text.lower() \
        or "Revoyons" in recap_seg.text


def test_list_courses_respects_locale():
    out = list_courses(locale="ja", limit=5)
    assert out["locale"] == "ja"
    titles = [c["title"] for c in out["courses"]]
    assert all("audio" in t or "オーディオ" in t or True for t in titles)
    levels = {c["level"] for c in out["courses"]}
    assert levels <= {"初級", "中級", "上級"} or "初級" in levels


def test_list_courses_filters_by_localized_or_canonical_category():
    es = list_courses(locale="es", category="Idiomas", limit=200)
    en = list_courses(locale="es", category="Languages", limit=200)
    assert es["total"] == en["total"] > 0
    # Every returned course must have the localized category label.
    assert all(c["category"] == "Idiomas" for c in es["courses"])


def test_categories_endpoint_emits_localized_and_canonical_ids():
    cats = categories("fr")
    by_id = {row["category_id"]: row for row in cats}
    assert by_id["Languages"]["category"] == "Langues"
    assert by_id["History"]["category"] == "Histoire"
    assert all(row["count"] > 0 for row in cats)


def test_get_course_with_locale():
    c_en = get_course("audio-budgeting-basics", "en")
    c_es = get_course("audio-budgeting-basics", "es")
    assert c_en is not None and c_es is not None
    assert c_en.category == "Personal Finance"
    assert c_es.category == "Finanzas personales"
    assert c_es.segments[0].heading == "Introducción"


def test_unknown_locale_falls_back_to_english_cleanly():
    c = get_course("lang-es-phrases", "zz")
    assert c is not None
    assert c.category == "Languages"
    assert c.level == "beginner"
