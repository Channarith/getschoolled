"""Audio-only 'drive mode' course catalog."""

from aoep_shared.audio_courses import (
    build_catalog,
    categories,
    get_course,
    list_courses,
)


def test_catalog_has_hundreds_of_audio_courses():
    cat = build_catalog()
    assert len(cat) >= 200  # "hundreds" of classes


def test_every_course_is_audio_only_and_drive_safe():
    for c in build_catalog():
        assert c.format == "audio"
        assert c.visual_required is False
        assert c.drive_safe is True
        assert len(c.segments) >= 2          # has narration
        assert c.duration_min >= 20


def test_enriched_courses_include_quiz_segments():
    cat = build_catalog()
    with_quiz = [c for c in cat if any(s.kind == "quiz" for s in c.segments)]
    assert len(with_quiz) >= len(cat) // 2
    sample = with_quiz[0]
    quiz = next(s for s in sample.segments if s.kind == "quiz")
    assert quiz.text


def test_language_courses_are_included():
    ids = {c.id for c in build_catalog()}
    assert "lang-es-phrases" in ids
    assert "lang-ja-phrases" in ids
    es = get_course("lang-es-phrases")
    # Listen-and-repeat narration references the target phrase.
    joined = " ".join(s.text for s in es.segments)
    assert "Hola" in joined


def test_knowledge_courses_span_many_categories():
    cats = {c["category"] for c in categories()}
    assert {"Languages", "History", "Science & Nature", "Personal Finance",
            "Health & Wellness", "Technology"} <= cats


def test_list_filter_and_paginate():
    page = list_courses(category="Languages", limit=10)
    assert page["total"] > 10 and len(page["courses"]) == 10
    assert all(c["category"] == "Languages" for c in page["courses"])
    nxt = list_courses(category="Languages", offset=10, limit=10)
    assert nxt["offset"] == 10
    # search
    found = list_courses(q="stoicism")
    assert found["total"] >= 1


def test_curated_topic_has_real_key_points():
    c = get_course("audio-budgeting-basics")
    assert c is not None
    text = " ".join(s.text for s in c.segments).lower()
    assert "budget" in text and "fifty-thirty-twenty" in text.replace("-", "-")


def test_get_unknown_returns_none():
    assert get_course("nope") is None
