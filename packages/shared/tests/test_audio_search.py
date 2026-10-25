"""The On the Go search lists a language for a course only when the translation is shippable (current, validated, same shape)."""
from __future__ import annotations

import json

import pytest

from aoep_shared import audio_search as search
from aoep_shared import translation_v2 as v2
from aoep_shared.course_translation_library import save_translation, translation_path


def _source(cid: str, title: str = "The Roman Empire", n: int = 2) -> v2.CourseSource:
    return v2.CourseSource(
        course_id=cid, title=title, category="History",
        segments=[{"heading": f"Part {i}", "text": f"English text {i}"} for i in range(1, n + 1)],
    )


def _write(root, src: v2.CourseSource, lang: str, *, sha: str | None = None, segments: int | None = None, provenance: bool = True,
           title: str = "El Imperio Romano"):
    n = len(src.segments) if segments is None else segments
    record = {
        "course_id": src.course_id, "language": lang, "title": title, "category": "Historia",
        "segments": [{"heading": f"Parte {i}", "text": f"Texto {i}"} for i in range(1, n + 1)],
    }
    if provenance:
        record["provenance"] = {"pipeline": v2.PIPELINE_VERSION, "source_sha256": sha or src.sha}
    return save_translation(record, root)


@pytest.fixture(autouse=True)
def _fresh_cache():
    search.clear_cache()
    yield
    search.clear_cache()


@pytest.fixture
def ship(monkeypatch):
    monkeypatch.setattr(v2, "judge_record", lambda *a, **k: {"verdict": v2.SHIP, "reasons": []})


def _ids(result, lang_ready=True):
    return [c["id"] for c in result["courses"] if c["ready"] == lang_ready]


def test_language_family_reduces_accents_and_aliases():
    assert search.language_family("en-GB") == "en"
    assert search.language_family("zh-HK") == "yue"
    assert search.language_family("yue") == "yue"
    assert search.language_family("Singlish") == "en"
    assert search.language_family("fil") == "tl"
    assert search.language_family("pt_BR") == "pt"
    assert search.language_family("") == ""


def test_only_current_validated_files_are_listed(tmp_path, ship):
    src = _source("audio-a")
    _write(tmp_path, src, "es")
    out = search.search(language="es", sources=[src], meta={}, root=tmp_path, languages=["es", "fr"])
    row = out["courses"][0]
    assert row["ready_languages"] == ["es"] and row["ready"] is True and row["english_only"] is False
    assert row["title_local"] == "El Imperio Romano"
    assert out["ready_counts"] == {"es": 1, "fr": 0}


def test_missing_provenance_is_not_listed(tmp_path, ship):
    src = _source("audio-a")
    _write(tmp_path, src, "es", provenance=False)
    row = search.search(language="es", sources=[src], meta={}, root=tmp_path, languages=["es"])["courses"][0]
    assert row["ready_languages"] == [] and row["english_only"] is True and row["ready"] is False


def test_translation_of_old_english_is_not_listed(tmp_path, ship):
    src = _source("audio-a")
    _write(tmp_path, src, "es", sha="0" * 64)
    row = search.search(language="es", sources=[src], meta={}, root=tmp_path, languages=["es"])["courses"][0]
    assert row["ready_languages"] == []


def test_validator_hold_or_reject_is_not_listed(tmp_path, monkeypatch):
    src = _source("audio-a")
    _write(tmp_path, src, "es")
    monkeypatch.setattr(v2, "judge_record", lambda *a, **k: {"verdict": "hold", "reasons": ["untranslated segment"]})
    row = search.search(language="es", sources=[src], meta={}, root=tmp_path, languages=["es"])["courses"][0]
    assert row["ready_languages"] == []


def test_partial_file_with_fewer_segments_is_not_listed(tmp_path, ship):
    src = _source("audio-a", n=3)
    _write(tmp_path, src, "es", segments=2)
    row = search.search(language="es", sources=[src], meta={}, root=tmp_path, languages=["es"])["courses"][0]
    assert row["ready_languages"] == []


def test_file_filed_under_the_wrong_language_is_not_listed(tmp_path, ship):
    src = _source("audio-a")
    path = _write(tmp_path, src, "es")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["language"] = "fr"
    path.write_text(json.dumps(data), encoding="utf-8")
    row = search.search(language="es", sources=[src], meta={}, root=tmp_path, languages=["es"])["courses"][0]
    assert row["ready_languages"] == []


def test_corrupt_file_is_not_listed_and_does_not_crash(tmp_path, ship):
    src = _source("audio-a")
    path = translation_path("audio-a", "es", tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    row = search.search(language="es", sources=[src], meta={}, root=tmp_path, languages=["es"])["courses"][0]
    assert row["ready_languages"] == []


def test_ready_courses_rank_first_and_english_only_can_be_hidden(tmp_path, ship):
    ready, plain = _source("audio-ready", "Ancient Egypt"), _source("audio-plain", "Aardvarks")
    _write(tmp_path, ready, "es")
    out = search.search(language="es", sources=[plain, ready], meta={}, root=tmp_path, languages=["es"])
    assert [c["id"] for c in out["courses"]] == ["audio-ready", "audio-plain"]
    assert out["ready_in_language"] == 1
    only = search.search(language="es", include_english=False, sources=[plain, ready], meta={}, root=tmp_path, languages=["es"])
    assert [c["id"] for c in only["courses"]] == ["audio-ready"]


def test_english_requests_treat_every_course_as_ready(tmp_path, ship):
    src = _source("audio-a")
    out = search.search(language="en-GB", sources=[src], meta={}, root=tmp_path, languages=["es"])
    assert out["language"] == "en" and out["courses"][0]["ready"] is True


def test_query_matches_title_local_title_and_tags(tmp_path, ship):
    a, b = _source("audio-a", "The Roman Empire"), _source("audio-b", "Black Holes")
    _write(tmp_path, a, "es")
    meta = {"audio-b": {"category": "Science", "subject": "space", "tags": ["astronomy"], "segments": 2}}
    assert [c["id"] for c in search.search(language="es", q="imperio", sources=[a, b], meta=meta, root=tmp_path, languages=["es"])["courses"]] == ["audio-a"]
    assert [c["id"] for c in search.search(language="es", q="astro", sources=[a, b], meta=meta, root=tmp_path, languages=["es"])["courses"]] == ["audio-b"]
    assert search.search(language="es", q="zzz", sources=[a, b], meta=meta, root=tmp_path, languages=["es"])["courses"] == []


def test_verdict_cache_follows_the_file(tmp_path, ship):
    src = _source("audio-a")
    kwargs = dict(language="es", sources=[src], meta={}, root=tmp_path, languages=["es"])
    assert search.search(**kwargs)["courses"][0]["ready_languages"] == []
    _write(tmp_path, src, "es")
    assert search.search(**kwargs)["courses"][0]["ready_languages"] == ["es"]
    _write(tmp_path, src, "es", sha="1" * 64)   # rewritten from other English: must not reuse the old "ok"
    assert search.search(**kwargs)["courses"][0]["ready_languages"] == []


def test_extra_languages_yue_and_tl_are_supported(tmp_path, ship):
    src = _source("audio-a")
    _write(tmp_path, src, "yue", title="羅馬帝國")
    out = search.search(language="zh-HK", sources=[src], meta={}, root=tmp_path, languages=["yue", "tl"])
    assert out["language"] == "yue" and out["courses"][0]["ready_languages"] == ["yue"]
    assert out["courses"][0]["title_local"] == "羅馬帝國"
