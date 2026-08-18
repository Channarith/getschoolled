"""Khmer cert localization: curated coverage, avatar keys, neural TTS cache."""

from __future__ import annotations

import re

from theodore_course_studio.avatar_director import avatar_script_for_slide
from theodore_course_studio.cert_i18n import CURATED, coverage, translate_cert_slide
from theodore_course_studio.certification_prep import build_cert_course
from theodore_course_studio import neural_tts
from theodore_course_studio.slide_keys import ALL_CERT_SLIDE_KEYS

KHMER_RE = re.compile(r"[\u1780-\u17ff]")


def _has_khmer(text: str) -> bool:
    return bool(KHMER_RE.search(text or ""))


def test_km_coverage_is_complete():
    assert coverage("km") == (62, 62)
    assert coverage("km-KH") == (62, 62)


def test_all_cert_slide_keys_match_curated_km():
    assert ALL_CERT_SLIDE_KEYS == set(CURATED["km"].keys())
    assert len(ALL_CERT_SLIDE_KEYS) == 62


def test_every_km_translation_has_khmer_in_title_body_say():
    for slide_key, tr in CURATED["km"].items():
        blob = f"{tr.title}\n{tr.body}\n{tr.say}"
        assert _has_khmer(blob), f"{slide_key} missing Khmer in title/body/say"
        assert _has_khmer(tr.title), f"{slide_key} title lacks Khmer"
        assert _has_khmer(tr.body), f"{slide_key} body lacks Khmer"
        assert _has_khmer(tr.say), f"{slide_key} say lacks Khmer"


def test_translate_cert_slide_round_trip():
    key = next(iter(CURATED["km"]))
    tr = translate_cert_slide(key, "km")
    assert tr is not None
    assert tr.title == CURATED["km"][key].title
    assert translate_cert_slide("no-such-key", "km") is None
    assert translate_cert_slide(key, "zz") is None


def test_build_cert_course_km_has_spoken_language_and_khmer_titles():
    course = build_cert_course(lesson_id="ca-dmv-basics", language="km")
    assert course.language == "km"
    assert course.profile_adaptations.get("spoken_language") == "km"
    assert course.profile_adaptations.get("translation_source") == "curated"
    assert course.slides
    for slide in course.slides:
        assert slide.slide_key
        assert _has_khmer(slide.title), slide.slide_key
        assert _has_khmer(slide.narration or slide.body), slide.slide_key


def test_avatar_cues_resolve_by_slide_key_when_title_is_khmer():
    course = build_cert_course(lesson_id="ca-dmv-basics", language="en")
    slide = course.slides[0]
    assert slide.slide_key
    # Drop the pre-attached explicit script so lookup runs; keep slide_key.
    khmer_title = CURATED["km"][slide.slide_key].title
    localized = slide.model_copy(
        update={"title": khmer_title, "avatar_script": None}
    )
    assert localized.title != slide.title
    script = avatar_script_for_slide(localized)
    assert script.source == "curated"


def test_neural_tts_khmer_voices():
    assert neural_tts.voice_for("km") == "km-KH-SreymomNeural"
    assert neural_tts.voice_for("km", gender="male") == "km-KH-PisethNeural"
    assert "km" in neural_tts.VOICES


def test_neural_tts_serves_cached_khmer_clip_when_engine_off(monkeypatch, tmp_path):
    monkeypatch.setenv("COURSE_STUDIO_TTS_CACHE", str(tmp_path))
    monkeypatch.setenv("COURSE_STUDIO_TTS", "off")
    text = "សួស្តី ពិភពលោក"
    voice = neural_tts.voice_for("km")
    rate = neural_tts.rate_percent(1.0)
    path = neural_tts.clip_path(text, voice=voice, rate=rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    fake = b"ID3fake-mp3-bytes-for-khmer-cache"
    path.write_bytes(fake)
    assert neural_tts.synthesize(text, "km") == fake
