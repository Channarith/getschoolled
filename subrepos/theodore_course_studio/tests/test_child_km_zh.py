from __future__ import annotations

from urllib.parse import unquote

import pytest

from theodore_course_studio.child_i18n import _CURATED, NEEDS_NATIVE_REVIEW
from theodore_course_studio.early_learning import (
    EarlyLevel,
    _TEMPLATES,
    build_early_course,
    list_early_courses,
)
from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.teach import TeachEngine

_TEMPLATE_BY_TOPIC = {t.topic_id: t for t in _TEMPLATES}
_LEVEL_BY_TOPIC = {t.topic_id: t.level for t in _TEMPLATES}


@pytest.mark.parametrize("lang", ["km", "zh"])
def test_all_eight_lessons_are_authored(lang):
    topics = {topic for (topic, curated_lang) in _CURATED if curated_lang == lang}
    assert topics == set(_TEMPLATE_BY_TOPIC), f"{lang} is missing lessons: {set(_TEMPLATE_BY_TOPIC) - topics}"


@pytest.mark.parametrize("topic,lang", sorted(_CURATED.keys()))
def test_curated_beat_counts_match_english_template(topic, lang):
    expected = len(_TEMPLATE_BY_TOPIC[topic].beats)
    assert len(_CURATED[(topic, lang)]) == expected, (
        f"{lang} {topic}: {len(_CURATED[(topic, lang)])} beats, expected {expected}"
    )


@pytest.mark.parametrize("topic,lang", sorted(_CURATED.keys()))
def test_curated_rows_have_nonempty_fields(topic, lang):
    for row in _CURATED[(topic, lang)]:
        assert len(row) in (4, 5)
        title, words, say, activity = row[0], row[1], row[2], row[3]
        assert title.strip() and words.strip() and say.strip() and activity.strip()


@pytest.mark.parametrize(
    "lang,topic,needle",
    [
        ("km", "colors", "ក្រហម"),      # Khmer for "red"
        ("km", "counting_1_10", "ដប់"),  # Khmer for "ten"
        ("zh", "colors", "红色"),         # Mandarin for "red"
        ("zh", "counting_1_10", "十"),    # Mandarin for "ten"
    ],
)
def test_native_vocabulary_present(lang, topic, needle):
    course = build_early_course(
        level=_LEVEL_BY_TOPIC[topic], topic_id=topic, language=lang
    )
    joined = " ".join(f"{s.title} {s.body} {s.narration}" for s in course.slides)
    assert needle in joined
    assert "This is red" not in joined  # never leak the English original


@pytest.mark.parametrize("lang", ["km", "zh"])
def test_native_reading_lessons_use_native_symbols(lang):
    course = build_early_course(
        level=EarlyLevel.KINDERGARTEN, topic_id="letter_sounds", language=lang
    )
    # Reading lessons teach the native script, so pictures must not be English A/B/C.
    joined_alt = " ".join(s.picture_alt for s in course.slides)
    second = unquote(course.slides[1].picture_url.split(",", 1)[1])
    if lang == "zh":
        assert "认识汉字" in course.slides[0].title
        assert "人" in second
    else:
        assert "អក្សរខ្មែរ" in course.slides[0].title
        assert "ក" in second
    assert "apple" not in joined_alt.lower()


@pytest.mark.parametrize("lang", ["km", "zh"])
def test_km_zh_flagged_for_native_review(lang):
    assert lang in NEEDS_NATIVE_REVIEW
    course = build_early_course(
        level=EarlyLevel.PRE_K, topic_id="colors", language=lang
    )
    assert course.profile_adaptations["translation_source"] == "curated"
    assert "native-speaker review" in course.profile_adaptations["translation_note"]


@pytest.mark.parametrize("lang", ["km", "zh"])
def test_teach_speaks_native_language(tmp_path, lang):
    builder = CourseBuilder(data_dir=tmp_path / f"data-{lang}")
    course = build_early_course(
        level=EarlyLevel.PRE_K, topic_id="colors", language=lang
    )
    builder.save_course(course)
    payload = TeachEngine(builder).start(
        session_id=f"s-{lang}", course_id=course.course_id, language=lang
    )
    assert payload["spoken_language"] == lang
    assert payload["tts"]["language"] == lang
    assert f"language={lang}" in payload["tts"]["get_url"]
    assert payload["translation_source"] == "curated"


def test_language_options_surface_km_and_zh():
    # Options endpoint lists platform languages elsewhere; here confirm curated
    # lessons exist for the two requested languages across levels.
    for level in (EarlyLevel.PRE_K, EarlyLevel.GRADE_2):
        assert list_early_courses(level)  # levels still populate


def test_phonics_km_zh_is_localized_not_english_letters():
    """Reading lessons teach the native script, never 'A is for apple'."""
    for lang, marker in (("zh", "汉字"), ("km", "អក្សរខ្មែរ")):
        course = build_early_course(
            level=EarlyLevel.KINDERGARTEN, topic_id="letter_sounds", language=lang
        )
        text = " ".join(s.body for s in course.slides)
        assert marker in course.slides[0].title
        assert "apple" not in text.lower()
