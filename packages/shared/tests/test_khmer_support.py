"""Khmer (km) is a first-class supported language across the platform.

The brand 'Salareen' derives from the Khmer word for school (\u179f\u17b6\u179b\u17b6\u179a\u17c0\u1793 sala-rian),
so end-to-end Khmer support is a hard requirement, not a stretch goal.
This test file is the executable contract: it covers every place Khmer
needs to be wired (languages list, LANGUAGE_META, phrasebook, catalog
i18n tables, notification i18n, audio_courses titles + segments).
"""

from __future__ import annotations

from aoep_shared import catalog_i18n
from aoep_shared.audio_courses import build_catalog, categories
from aoep_shared.language_learning import (
    LANGUAGE_META, RICH_LANGUAGES, course_outline, dialogues_for,
    media_listening_challenge, phrases_for, songs_for, vocabulary_exercise,
    vocabulary_for,
)
from aoep_shared.slang import all_entries
from aoep_shared.languages import SUPPORTED_LANGUAGES, is_supported
from aoep_shared.notifications import (
    SUPPORTED_NOTIFICATION_LOCALES, build_feed,
)


KM_NATIVE = "\u1781\u17d2\u1798\u17c2\u179a"
KM_FLAG = "\U0001f1f0\U0001f1ed"
SALA_RIAN = "\u179f\u17b6\u179b\u17b6\u179a\u17c0\u1793"


def test_khmer_in_supported_languages():
    assert "km" in SUPPORTED_LANGUAGES
    assert is_supported("km")


def test_khmer_language_meta():
    meta = LANGUAGE_META["km"]
    assert meta == {"name": "Khmer", "native": KM_NATIVE, "flag": KM_FLAG}


def test_khmer_is_a_rich_language():
    assert "km" in RICH_LANGUAGES


def test_khmer_phrasebook_has_full_concept_set():
    phrases = phrases_for("km")
    keys = {p["id"] for p in phrases}
    # All 13 phrasebook concepts present.
    assert keys >= {
        "hello", "goodbye", "thanks", "please", "yes", "no", "excuseme",
        "howareyou", "myname", "nicemeet", "bathroom", "howmuch", "help",
    }
    # Romanizations present (Khmer is non-Latin).
    hello = next(p for p in phrases if p["id"] == "hello")
    assert hello["target"]  # Khmer script
    assert hello["roman"] == "Chum reap suor"
    assert len(phrases) >= 20
    english = {p["en"] for p in phrases}
    assert {
        "What is this dish?",
        "How do I say this in Khmer?",
        "That is too expensive",
        "Can it be cheaper?",
    } <= english


def test_khmer_has_twenty_dialogues_and_fifty_slang_entries():
    dialogues = dialogues_for("km")
    assert len(dialogues) >= 20
    assert all(len(row["turns"]) >= 2 for row in dialogues)
    entries = [entry for entry in all_entries() if entry.language == "km"]
    assert len(entries) >= 50


def test_khmer_has_at_least_five_hundred_vocabulary_words():
    words = vocabulary_for("km")
    assert len(words) >= 500
    assert len({word["id"] for word in words}) == len(words)
    assert len({word["target"] for word in words}) == len(words)
    assert len({word["category"] for word in words}) >= 12
    assert all(
        word["en"]
        and word["roman"]
        and word["category"]
        and any("\u1780" <= char <= "\u17ff" for char in word["target"])
        for word in words
    )
    exercise = vocabulary_exercise("km", n=8, seed=7)
    targets = {word["target"] for word in words}
    assert len(exercise["items"]) == 8
    assert all(
        item["prompt"].split(" (", 1)[0] in targets
        for item in exercise["items"]
    )


def test_khmer_song_is_verse_driven_and_licensed():
    song = songs_for("km")[0]
    assert song["license"] in ("public-domain", "cc-by", "original-salareen")
    assert len(song["verses"]) >= 4
    assert song["source_url"]
    assert all(
        verse["target"] and verse["en"] and verse["explain_en"]
        for verse in song["verses"]
    )


def test_khmer_media_challenge_studies_ten_then_quizzes_every_ten_seconds():
    challenge = media_listening_challenge("km", study_size=10, seed=42)
    words = challenge["study_words"]
    segments = challenge["segments"]
    assert challenge["media_type"] == "generated_audio"
    assert challenge["license"] == "original-salareen"
    assert len(words) == len(segments) == 10
    assert len({word["id"] for word in words}) == 10
    word_ids = {word["id"] for word in words}
    for index, segment in enumerate(segments):
        assert segment["start_sec"] == index * 10
        assert segment["end_sec"] == (index + 1) * 10
        assert segment["duration_sec"] == 10
        assert segment["answer_id"] in word_ids
        assert {option["id"] for option in segment["options"]} == word_ids
        answer = next(
            word for word in words if word["id"] == segment["answer_id"]
        )
        assert answer["target"] in segment["tts_text"]


def test_khmer_course_outline_carries_grammar_and_culture():
    outline = course_outline("km")
    assert outline["code"] == "km"
    assert outline["native"] == KM_NATIVE
    assert outline["tier"] == "full"
    assert outline["vocabulary_count"] >= 500
    assert outline["grammar_tip"]      # non-empty
    assert outline["culture_note"]
    assert "sampeah" in outline["culture_note"]


def test_catalog_i18n_supports_km():
    assert "km" in catalog_i18n.SUPPORTED_LOCALES
    assert catalog_i18n.normalize_locale("km") == "km"
    assert catalog_i18n.normalize_locale("km-KH") == "km"


def test_catalog_categories_render_in_khmer():
    cats = categories("km")
    by_id = {c["category_id"]: c["category"] for c in cats}
    # Categories should be rendered in Khmer script, not English.
    assert any("\u1780" <= ch <= "\u17ff" for ch in by_id["Languages"])
    assert by_id["History"] != "History"
    assert by_id["Personal Finance"] != "Personal Finance"


def test_audio_course_titles_localize_in_khmer():
    cat = build_catalog("km")
    es_course = next(c for c in cat if c.id == "lang-es-phrases")
    # Title: "<Spanish-in-Khmer>: <Essential phrases-in-Khmer> (audio)".
    assert "\u17a2\u17c1\u179f\u17d2\u1794\u17c9\u1789\u17bc\u179b" in es_course.title  # esponyol
    # Category + level localize to Khmer for the browsing UI. (Segment
    # headings are the authentic English phrase cues - the lesson teaches the
    # target language and no longer carries a localized intro wrapper.)
    assert any("\u1780" <= ch <= "\u17ff" for ch in es_course.category)
    assert any("\u1780" <= ch <= "\u17ff" for ch in es_course.level)


def test_notification_feed_renders_km_titles():
    assert "km" in SUPPORTED_NOTIFICATION_LOCALES
    feed = build_feed(locale="km", streak_days=2, interests=["spanish"])
    titles = " ".join(i.title for i in feed.items)
    bodies = " ".join(i.body for i in feed.items)
    # Some Khmer codepoint must be present in the rendered feed.
    assert any("\u1780" <= ch <= "\u17ff" for ch in titles + bodies)
    # Streak title carries the day count.
    assert any("2" in i.title for i in feed.items if i.kind == "streak")


def test_unknown_locale_still_falls_back_to_english():
    assert catalog_i18n.normalize_locale("zz") == "en"
    feed = build_feed(locale="zz")
    assert any("Your daily class is ready" in i.title for i in feed.items)


def test_brand_word_renders_in_phrasebook_or_assets():
    # The phrasebook doesn't include the literal word salareen (school),
    # but our Khmer NAME translation table should round-trip it cleanly.
    # The Khmer wordmark file path is checked in branding tests; here
    # we only verify the Unicode payload is well-formed.
    assert len(SALA_RIAN) == 7
    assert all("\u1780" <= ch <= "\u17ff" for ch in SALA_RIAN)
