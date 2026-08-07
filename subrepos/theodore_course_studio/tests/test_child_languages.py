from __future__ import annotations

import json

from theodore_course_studio.child_i18n import (
    SOUND_SPECIFIC_TOPICS,
    translate_beats,
)
from theodore_course_studio.early_learning import EarlyLevel, build_early_course
from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.teach import TeachEngine

ENGLISH_BEATS = (
    ("Red", "Red is bright.", "This is red.", "Find something red."),
    ("Blue", "Blue is cool.", "This is blue.", "Point at the sky."),
)


def test_spanish_lesson_text_is_actually_spanish():
    course = build_early_course(
        level=EarlyLevel.PRE_K, topic_id="colors", language="es"
    )
    assert course.language == "es"
    assert course.profile_adaptations["translation_source"] == "curated"
    assert course.profile_adaptations["spoken_language"] == "es"
    joined = " ".join(s.narration for s in course.slides)
    # The old bug: Spanish selected, English words sent to a Spanish voice.
    assert "This is red" not in joined
    assert "rojo" in joined.lower()


def test_spanish_pictures_use_translated_labels():
    course = build_early_course(
        level=EarlyLevel.PRE_K, topic_id="colors", language="es"
    )
    from urllib.parse import unquote

    red = course.slides[1]
    assert red.title == "Rojo"
    assert "Rojo" in unquote(red.picture_url.split(",", 1)[1])


def test_phonics_is_localized_not_literally_translated():
    """'A is for apple' must not become 'A is for manzana' (manzana starts with M)."""
    course = build_early_course(
        level=EarlyLevel.KINDERGARTEN, topic_id="letter_sounds", language="es"
    )
    text = " ".join(s.body for s in course.slides).lower()
    assert "manzana" not in text
    assert "avión" in text  # A really does start with the /a/ sound here
    assert course.profile_adaptations["sound_specific"] is True


def test_sound_specific_lesson_refuses_machine_translation():
    result = translate_beats(
        topic_id="letter_sounds",
        language="ja",  # no curated Japanese phonics variant
        beats=ENGLISH_BEATS,
        allow_xai=True,
    )
    assert result.source == "english"
    assert "not machine translated" in result.note
    assert "letter_sounds" in SOUND_SPECIFIC_TOPICS


def test_untranslated_language_is_reported_and_speaks_english(tmp_path):
    """Never speak English words with a foreign voice — say so instead."""
    course = build_early_course(
        level=EarlyLevel.PRE_K,
        topic_id="colors",
        language="ja",
        data_dir=tmp_path / "data",
        allow_xai_translation=False,  # simulate no key / no network
    )
    assert course.language == "ja"
    assert course.profile_adaptations["translation_source"] == "english"
    # Audio must follow the WORDS (English), not the requested language.
    assert course.profile_adaptations["spoken_language"] == "en"
    assert "XAI_API_KEY" in course.profile_adaptations["translation_note"]


def test_teach_speaks_the_language_of_the_words(tmp_path):
    builder = CourseBuilder(data_dir=tmp_path / "data")
    spanish = build_early_course(
        level=EarlyLevel.PRE_K, topic_id="colors", language="es"
    )
    builder.save_course(spanish)
    payload = TeachEngine(builder).start(
        session_id="es-1", course_id=spanish.course_id, language="es"
    )
    assert payload["spoken_language"] == "es"
    assert payload["tts"]["language"] == "es"
    assert "language=es" in payload["tts"]["get_url"]
    assert "rojo" in payload["turn"]["narration"].lower() or "colores" in payload[
        "turn"
    ]["narration"].lower()


def test_teach_falls_back_to_english_audio_when_untranslated(tmp_path):
    builder = CourseBuilder(data_dir=tmp_path / "data")
    course = build_early_course(
        level=EarlyLevel.PRE_K,
        topic_id="colors",
        language="ja",
        data_dir=tmp_path / "data",
        allow_xai_translation=False,
    )
    builder.save_course(course)
    payload = TeachEngine(builder).start(
        session_id="ja-1", course_id=course.course_id, language="ja"
    )
    assert payload["language"] == "ja"
    assert payload["spoken_language"] == "en"
    assert "language=en" in payload["tts"]["get_url"]
    assert payload["translation_source"] == "english"


def test_xai_translation_is_used_and_cached(tmp_path, monkeypatch):
    """Real Grok path: correct request shape, result cached for offline reuse."""
    from io import BytesIO

    calls = {"n": 0}
    captured: dict = {}

    class _Resp:
        def __init__(self, payload: bytes) -> None:
            self._buf = BytesIO(payload)

        def read(self):
            return self._buf.read()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        calls["n"] += 1
        captured["auth"] = req.headers.get("Authorization")
        captured["body"] = json.loads(req.data.decode("utf-8"))
        rows = [
            {"i": 0, "title": "Rouge", "words": "Rouge est vif.",
             "say": "Ceci est rouge.", "activity": "Trouve quelque chose de rouge."},
            {"i": 1, "title": "Bleu", "words": "Bleu est frais.",
             "say": "Ceci est bleu.", "activity": "Montre le ciel."},
        ]
        payload = {"choices": [{"message": {"content": json.dumps(rows)}}]}
        return _Resp(json.dumps(payload).encode("utf-8"))

    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "theodore_course_studio.child_i18n.urllib.request.urlopen", fake_urlopen
    )

    data_dir = tmp_path / "data"
    first = translate_beats(
        topic_id="colors_demo",
        language="fr",
        beats=ENGLISH_BEATS,
        data_dir=data_dir,
    )
    assert first.source == "xai"
    assert first.beats[0].title == "Rouge"
    assert captured["auth"] == "Bearer test-key"
    assert "French" in captured["body"]["messages"][0]["content"]
    assert calls["n"] == 1

    # Second call must hit the on-disk cache, not the network.
    second = translate_beats(
        topic_id="colors_demo",
        language="fr",
        beats=ENGLISH_BEATS,
        data_dir=data_dir,
    )
    assert second.source == "xai"
    assert second.beats[0].title == "Rouge"
    assert calls["n"] == 1


def test_translation_failure_degrades_to_english(monkeypatch):
    def boom(*_a, **_k):
        raise OSError("Connection reset by peer")

    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "theodore_course_studio.child_i18n.urllib.request.urlopen", boom
    )
    result = translate_beats(
        topic_id="colors_demo", language="fr", beats=ENGLISH_BEATS
    )
    assert result.source == "english"
    assert result.beats[0].title == "Red"
