"""Pre-translated course library and the async batch writer."""

import asyncio

from aoep_shared.course_translation_batch import CourseJob, translate_catalog
from aoep_shared.course_translation_library import (
    TARGET_LANGUAGES,
    find_translation,
    reference_for_class,
    save_translation,
)
from aoep_shared.languages import SUPPORTED_LANGUAGES


def test_target_languages_are_the_26_non_english_codes():
    assert len(SUPPORTED_LANGUAGES) == 27
    assert "en" not in TARGET_LANGUAGES
    assert len(TARGET_LANGUAGES) == 26
    assert "km" in TARGET_LANGUAGES


def test_library_stays_inside_one_class(tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_COURSE_TRANSLATION_DIR", str(tmp_path))
    save_translation(
        {
            "course_id": "audio-ancient-egypt",
            "title": "El antiguo Egipto",
            "category": "History",
            "language": "es",
            "segments": [
                {"heading": "El Nilo", "text": "El Nilo se desbordaba cada año."},
                {"heading": "Las pirámides", "text": "Las pirámides eran tumbas."},
            ],
        }
    )
    save_translation(
        {
            "course_id": "audio-food",
            "title": "Seguridad alimentaria",
            "category": "Cooking & Food",
            "language": "es",
            "segments": [{"heading": "Manos", "text": "Lávate las manos antes de cocinar."}],
        }
    )
    hit = reference_for_class(
        course_id="audio-ancient-egypt",
        title="Ancient Egypt",
        category="History",
        language="es",
        query="Nile flood",
    )
    assert hit["hit"] is True
    assert "Nilo" in hit["text"]
    assert "Manos" not in hit["text"]
    other = find_translation(title="Seguridad alimentaria", category="History", language="es")
    assert other is None
    missed = reference_for_class(
        course_id="audio-ancient-egypt",
        language="es",
        query="stock market dividends",
    )
    assert missed["hit"] is True
    assert "Nilo" in missed["text"]
    assert "Manos" not in missed["text"]
    absent = reference_for_class(course_id="missing-course", language="es", query="Nile")
    assert absent["hit"] is False


def test_batch_writes_and_skips(tmp_path):
    jobs = [
        CourseJob(
            "audio-ancient-egypt",
            "Ancient Egypt",
            "History",
            [{"heading": "The Nile", "text": "The Nile flooded every year."}],
        )
    ]

    async def fake(text: str, source: str, target: str) -> str:
        assert source == "en"
        return f"{target}:{text}"

    first = asyncio.run(
        translate_catalog(jobs, ["es", "km"], fake, concurrency=2, root=tmp_path)
    )
    assert first == {"written": 2, "skipped": 0, "failed": 0}
    stored = find_translation(course_id="audio-ancient-egypt", language="km", root=tmp_path)
    assert stored["segments"][0]["text"].startswith("km:")
    second = asyncio.run(
        translate_catalog(jobs, ["es"], fake, concurrency=1, root=tmp_path)
    )
    assert second["skipped"] == 1
    assert second["written"] == 0
