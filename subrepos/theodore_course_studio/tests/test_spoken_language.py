"""The voice must speak the language the slide words are actually in.

Translation coverage is per-slide, so a "Khmer" course legitimately contains
English slides. Tagging the whole course Khmer made the Khmer voice read those
English slides aloud, and appending the English lead-in/nudge put English at the
end of every translated slide. These tests pin both halves of that invariant.
"""

from __future__ import annotations

import re
import urllib.parse as urlparse

import pytest

from theodore_course_studio.cert_i18n import CURATED, SCAFFOLD, scaffold_for
from theodore_course_studio.cert_multimodal import (
    format_body_with_examples,
    narration_with_examples,
)
from theodore_course_studio.certification_prep import build_cert_course, list_cert_courses
from theodore_course_studio.profile_adapt import adapt_slide
from theodore_course_studio.types import LearnerProfileScores
from theodore_course_studio.voice_agent import VoiceTurn

KHMER_RE = re.compile(r"[\u1780-\u17ff]")
# A long run of Latin letters is a spoken English sentence; short runs are the
# proper nouns the curated Khmer keeps in English on purpose ("Alameda County",
# "STEC", sign legends like "One Way").
ENGLISH_SENTENCE_RE = re.compile(r"[A-Za-z][A-Za-z' ,\-]{45,}")

CERT_LESSON_IDS = [
    row.lesson_id if hasattr(row, "lesson_id") else row["lesson_id"]
    for row in list_cert_courses()
]


def _has_khmer(text: str) -> bool:
    return bool(KHMER_RE.search(text or ""))


def test_every_curated_language_has_scaffolding():
    """Otherwise its slides get English connectives spliced into the audio."""
    assert set(CURATED) <= set(SCAFFOLD), "curated language missing SCAFFOLD entry"


def test_khmer_scaffolding_is_khmer():
    scaffold = scaffold_for("km")
    assert scaffold is not None
    for phrase in (
        scaffold.examples_heading,
        scaffold.examples_lead,
        scaffold.practice_nudge,
    ):
        assert _has_khmer(phrase), phrase


def test_scaffolding_falls_back_by_region_tag():
    assert scaffold_for("km-KH") is scaffold_for("km")
    assert scaffold_for("zz") is None


def test_narration_omits_connectives_rather_than_speaking_english():
    """An unscaffolded language gets a bare line, never an English tail."""
    said = narration_with_examples("ABC", ("one", "two"), "zz")
    assert said == "ABC one two"
    assert "Here are a few friendly examples." not in said


def test_narration_and_body_use_the_slide_language_scaffolding():
    say = narration_with_examples("សូស្តី។", ("ឧ១", "ឧ២"), "km")
    assert not ENGLISH_SENTENCE_RE.search(say), say
    assert scaffold_for("km").practice_nudge in say  # type: ignore[union-attr]

    body = format_body_with_examples("សូស្តី។", ("ឧ១",), "km")
    assert "Examples:" not in body
    assert scaffold_for("km").examples_heading in body  # type: ignore[union-attr]

    # English is unchanged — the default keeps existing callers working.
    assert "Examples:" in format_body_with_examples("Rule.", ("a",))
    assert "Here are a few friendly examples." in narration_with_examples("Say.", ("a",))


@pytest.mark.parametrize("lesson_id", CERT_LESSON_IDS)
def test_each_slide_declares_the_language_of_its_own_words(lesson_id):
    course = build_cert_course(lesson_id=lesson_id, language="km")
    assert course.slides
    for slide in course.slides:
        assert slide.spoken_language in {"km", "en"}, slide.slide_key
        assert _has_khmer(slide.narration) == (slide.spoken_language == "km"), (
            f"{slide.slide_key}: spoken_language={slide.spoken_language} "
            f"does not match the narration script"
        )


@pytest.mark.parametrize("lesson_id", CERT_LESSON_IDS)
def test_translated_slides_never_carry_an_english_sentence(lesson_id):
    course = build_cert_course(lesson_id=lesson_id, language="km")
    for slide in course.slides:
        if slide.spoken_language != "km":
            continue
        leak = ENGLISH_SENTENCE_RE.search(slide.narration)
        assert not leak, f"{slide.slide_key} narrates English: {leak.group()!r}"


def test_partially_translated_course_keeps_english_slides_on_an_english_voice():
    """The reported bug: a Khmer voice reading the untranslated slides."""
    course = build_cert_course(lesson_id="alameda-food-hygiene", language="km")
    langs = {slide.spoken_language for slide in course.slides}
    assert langs == {"km", "en"}, "expected a partially curated lesson here"
    assert course.profile_adaptations["spoken_language"] == "km"


def test_adapt_slide_keeps_english_coaching_out_of_translated_narration():
    course = build_cert_course(lesson_id="ca-dmv-basics", language="km")
    slide = course.slides[0]
    assert slide.spoken_language == "km"
    # Worst case: every coaching branch wants to fire.
    profile = LearnerProfileScores(
        fatigue=0.9,
        attention=0.2,
        confusion=0.9,
        literacy=0.2,
        accessibility_need=0.9,
        pace_preference=0.2,
        engagement=0.9,
    )
    turn = adapt_slide(slide, profile)
    assert turn.spoken_language == "km"
    leak = ENGLISH_SENTENCE_RE.search(turn.narration)
    assert not leak, f"English coaching leaked into Khmer narration: {leak!r}"
    # The delivery is still adapted, just without the English asides.
    assert "shorten_for_fatigue_or_low_attention" in turn.adaptations_applied


def test_adapt_slide_still_coaches_english_slides():
    course = build_cert_course(lesson_id="ca-dmv-basics", language="en")
    turn = adapt_slide(course.slides[0], LearnerProfileScores(confusion=0.9))
    assert turn.spoken_language == "en"
    assert "Let's take this slowly." in turn.narration


def test_khmer_narration_shortens_on_the_khmer_full_stop():
    """Splitting on "." alone left Khmer slides at full length."""
    course = build_cert_course(lesson_id="ca-dmv-basics", language="km")
    slide = course.slides[0]
    turn = adapt_slide(slide, LearnerProfileScores(fatigue=0.9))
    assert len(turn.narration) < len(slide.narration)
    assert turn.narration.endswith("។")


def test_offline_voice_fallback_is_reported_as_english():
    """The fallback line is English no matter which language was requested."""
    from theodore_course_studio.teach import _voice_turn_language

    fallback = VoiceTurn(message="[Khmer] Let's take this...", language_code="km")
    assert fallback.fallback_used is True
    assert _voice_turn_language(fallback, "km") == "en"

    real = VoiceTurn(
        provider="xai", message="សូស្តី", language_code="km", fallback_used=False
    )
    assert _voice_turn_language(real, "en") == "km"


def _tts_language(payload: dict) -> str:
    url = (payload.get("tts") or {}).get("get_url", "")
    query = urlparse.parse_qs(urlparse.urlparse(url).query)
    return (query.get("language") or [""])[0]


def test_teach_session_sends_each_slide_to_a_matching_voice():
    """End-to-end: the TTS URL language tracks the words on screen."""
    from fastapi.testclient import TestClient

    from theodore_course_studio.main import app

    client = TestClient(app)
    built = client.post(
        "/api/studio/courses/certification",
        json={"lesson_id": "alameda-food-hygiene", "language": "km"},
    )
    assert built.status_code == 200
    course_id = built.json()["course_id"]

    started = client.post(
        "/api/studio/teach/start",
        json={"session_id": "spoken-lang-test", "course_id": course_id, "language": "km"},
    )
    assert started.status_code == 200

    payload = started.json()
    seen: set[int] = set()
    while payload["turn"]["slide_index"] not in seen:
        turn = payload["turn"]
        seen.add(turn["slide_index"])
        expected = "km" if _has_khmer(turn["narration"]) else "en"
        assert payload["spoken_language"] == expected, turn["slide_index"]
        assert _tts_language(payload) == expected, turn["slide_index"]
        advanced = client.post(
            "/api/studio/teach/advance", json={"session_id": "spoken-lang-test"}
        )
        assert advanced.status_code == 200
        payload = advanced.json()

    assert len(seen) > 1
