"""/audio/search: courses with the languages each is READY in (shippable translations only)."""
import pytest
from aoep_shared import audio_search
from aoep_shared import translation_v2 as v2
from curriculum.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def _empty_library(tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_COURSE_TRANSLATION_DIR", str(tmp_path))
    audio_search.clear_cache()
    yield
    audio_search.clear_cache()


def test_search_lists_the_catalog_with_live_tts_and_no_ready_languages_when_nothing_is_translated():
    body = client.get("/audio/search", params={"language": "es"}).json()
    assert body["language"] == "es" and body["audio_mode"] == "live_tts"
    assert body["total"] >= 200
    assert all(c["ready_languages"] == [] and c["english_only"] is True and c["ready"] is False for c in body["courses"])
    assert body["ready_in_language"] == 0


def test_search_filters_by_query_and_can_hide_english_only():
    found = client.get("/audio/search", params={"language": "en", "q": "roman empire"}).json()
    assert found["total"] >= 1 and any("roman" in c["title"].lower() for c in found["courses"])
    hidden = client.get("/audio/search", params={"language": "fr", "include_english": "false"}).json()
    assert hidden["total"] == 0   # nothing is translated in this empty library


def test_search_lists_a_language_only_after_a_shippable_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(v2, "judge_record", lambda *a, **k: {"verdict": v2.SHIP, "reasons": []})
    src = next(s for s in v2.audio_sources() if s.course_id == "audio-the-roman-empire")
    from aoep_shared.course_translation_library import save_translation

    save_translation({
        "course_id": src.course_id, "language": "es", "title": "El Imperio Romano", "category": "Historia",
        "segments": [{"heading": f"H{i}", "text": f"T{i}"} for i in range(len(src.segments))],
        "provenance": {"pipeline": v2.PIPELINE_VERSION, "source_sha256": src.sha},
    }, tmp_path)
    body = client.get("/audio/search", params={"language": "es"}).json()
    first = body["courses"][0]
    assert first["id"] == "audio-the-roman-empire" and first["ready"] is True and first["ready_languages"] == ["es"]
    assert first["title_local"] == "El Imperio Romano"


def test_search_limit_is_capped():
    body = client.get("/audio/search", params={"limit": 100000}).json()
    assert body["limit"] == 500 and len(body["courses"]) <= 500
