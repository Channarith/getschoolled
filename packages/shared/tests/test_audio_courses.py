"""Audio-only 'drive mode' course catalog."""

from aoep_shared.audio_courses import (
    MIN_DRIVE_MINUTES,
    MIN_DRIVE_SEGMENTS,
    MIN_DRIVE_WORDS,
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
        assert len(c.segments) >= MIN_DRIVE_SEGMENTS
        assert c.duration_min >= MIN_DRIVE_MINUTES
        assert c.word_count >= MIN_DRIVE_WORDS


def test_knowledge_courses_are_not_filler_loops():
    """Long-form knowledge lessons must contain unique authored narration."""
    knowledge = [c for c in build_catalog() if c.id.startswith("audio-")]
    assert knowledge
    for c in knowledge:
        bodies = [s.text for s in c.segments if s.kind == "narration"]
        assert len(bodies) == len(set(bodies)), f"{c.id} repeats narration bodies"
        assert len(c.segments) >= MIN_DRIVE_SEGMENTS
        assert c.duration_min >= MIN_DRIVE_MINUTES
        assert c.word_count >= MIN_DRIVE_WORDS


def test_courses_do_not_include_synthetic_padding_segments():
    banned = (
        "welcome to this audio lesson",
        "keep your eyes on the road",
        "repeat after me",
        "great work! let's review",
        "learning on the move",
        "why it's worth knowing",
        "quick recap of",
    )
    for c in (c for c in build_catalog() if c.id.startswith("audio-")):
        synthetic = [s for s in c.segments if s.kind in {"quiz", "reinforcement"}]
        assert not synthetic, f"{c.id} contains generated padding or recall segments"
        joined = " ".join(s.text for s in c.segments).lower()
        for phrase in banned:
            assert phrase not in joined, f"{c.id} still contains filler narration: {phrase!r}"


def test_knowledge_courses_start_with_selected_topic_then_add_context():
    from aoep_shared.audio_courses import _TOPICS, get_course
    from aoep_shared.audio_topic_data import TOPIC_SECTIONS

    for titles in _TOPICS.values():
        for title in titles:
            # Only test topics that have authored TOPIC_SECTIONS entries.
            # Topics without entries rely on _extended_knowledge_segments to
            # pull content from related topics, which is valid but can't be
            # checked for primary-first ordering.
            if title not in TOPIC_SECTIONS:
                continue
            slug = title.lower().replace(" ", "-").replace(",", "").replace("'", "")
            c = get_course(f"audio-{slug}")
            assert c is not None
            assert c.segments[0].heading == "Overview"
            assert c.segments[-1].heading == "Key takeaways"
            primary = TOPIC_SECTIONS[title]
            assert [s.heading for s in c.segments[1:1 + len(primary)]] == [
                heading for heading, _ in primary
            ]
            assert all(
                s.heading.startswith("Related context — ")
                for s in c.segments[1 + len(primary):-1]
            )


def test_blockchain_course_has_substantive_content():
    c = get_course("audio-what-is-blockchain")
    assert c is not None
    joined = " ".join(f"{s.heading} {s.text}" for s in c.segments).lower()
    for term in ("satoshi", "hash", "proof of work", "ethereum", "bitcoin"):
        assert term in joined, f"missing {term}"
    assert len(c.segments) >= MIN_DRIVE_SEGMENTS
    assert c.duration_min >= MIN_DRIVE_MINUTES


def test_language_courses_are_included():
    ids = {c.id for c in build_catalog()}
    assert "lang-es-phrases" in ids
    assert "lang-ja-phrases" in ids
    es = get_course("lang-es-phrases")
    # Listen-and-repeat narration references the target phrase.
    joined = " ".join(s.text for s in es.segments)
    assert "Hola" in joined
    assert len(es.segments) >= MIN_DRIVE_SEGMENTS
    assert es.duration_min >= MIN_DRIVE_MINUTES
    assert es.word_count >= MIN_DRIVE_WORDS


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
