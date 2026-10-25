import asyncio

from aoep_shared.course_translation_batch import CourseJob, translate_catalog
from aoep_shared.course_translation_library import (
    EXTRA_TRANSLATION_LANGUAGES,
    TARGET_LANGUAGES,
)
from aoep_shared.languages import SUPPORTED_LANGUAGES
from aoep_shared.nllb import flores_code
from aoep_shared.translation import is_pair_supported


def test_cantonese_is_not_mandarin():
    assert flores_code("yue") == "yue_Hant"
    assert flores_code("zh") == "zho_Hans"
    assert flores_code("yue") != flores_code("zh")


def test_cantonese_is_translatable_and_outside_the_platform_list():
    assert "yue" not in SUPPORTED_LANGUAGES
    assert len(SUPPORTED_LANGUAGES) == 27
    assert "yue" not in TARGET_LANGUAGES
    assert len(TARGET_LANGUAGES) == 26
    assert EXTRA_TRANSLATION_LANGUAGES == ("yue", "tl")
    assert is_pair_supported("en", "yue") is True
    assert is_pair_supported("en", "klingon") is False


def test_batch_writes_cantonese_as_its_own_file(tmp_path):
    seen: list[str] = []

    async def translator(text: str, source: str, target: str) -> str:
        seen.append(target)
        return "我係學生"

    job = CourseJob(
        "audio-intro-to-machine-learning",
        "Intro to Machine Learning",
        "AI",
        [{"heading": "Start", "text": "I am a student.", "kind": "narration"}],
    )
    counts = asyncio.run(
        translate_catalog([job], ["yue"], translator, concurrency=1, root=tmp_path)
    )
    assert counts["written"] == 1
    assert seen == ["yue", "yue", "yue"]
    saved = (tmp_path / "audio-intro-to-machine-learning" / "yue.json").read_text(
        encoding="utf-8"
    )
    assert '"language": "yue"' in saved
    assert "我係學生" in saved


def test_batch_still_rejects_an_unknown_language():
    async def translator(text: str, source: str, target: str) -> str:
        return "x"

    job = CourseJob("c", "T", "Cat", [{"heading": "H", "text": "Hello.", "kind": "narration"}])
    try:
        asyncio.run(translate_catalog([job], ["klingon"], translator, concurrency=1))
    except ValueError as exc:
        assert "unsupported target language" in str(exc)
    else:
        raise AssertionError("klingon should be rejected")
