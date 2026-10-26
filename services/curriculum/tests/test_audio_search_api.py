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


# ---- partial / synonym search and the whole catalog (owner feedback: "cp" -> CPR, "mac" -> machine vision) ----
def _titles(body, key="courses"):
    return [c["title"] for c in body[key]]


def test_empty_query_lists_every_catalog_course_including_the_language_lessons():
    from aoep_shared.audio_courses import build_catalog

    body = client.get("/audio/search", params={"language": "en"}).json()
    assert body["total"] == len(build_catalog("en"))   # 271, not only the 222 the translation pipeline covers
    assert any(c["id"].startswith("lang-") and c["audio"] is True for c in body["courses"])
    assert body["planned"] == []   # coming-soon topics are only sent when asked for


def test_partial_queries_find_planned_topics_as_coming_soon():
    for q in ("cp", "cpr"):
        body = client.get("/audio/search", params={"q": q, "include_planned": "true"}).json()
        assert "First Aid and CPR" in _titles(body, "planned"), q
        first = body["planned"][0]
        assert first["planned"] is True and first["audio"] is False and first["ready"] is False
    body = client.get("/audio/search", params={"q": "first", "include_planned": "true"}).json()
    assert "Ada Lovelace, First Programmer" in _titles(body) and "First Aid and CPR" in _titles(body, "planned")


def test_synonyms_find_computer_vision_and_machine_learning():
    vision = client.get("/audio/search", params={"q": "machine vision", "include_planned": "true"}).json()
    assert "Computer Vision Basics" in _titles(vision, "planned")
    assert "How to Write a CV" not in _titles(vision) + _titles(vision, "planned")   # no 'CV' false positive
    for q in ("mac", "ml"):
        body = client.get("/audio/search", params={"q": q}).json()
        assert "Intro to Machine Learning" in _titles(body), q


def test_two_letter_queries_do_not_match_inside_words():
    body = client.get("/audio/search", params={"q": "ai", "include_planned": "true"}).json()
    assert "Cloud Computing Explained" not in _titles(body)
    assert "What Is Artificial Intelligence" in _titles(body)


def test_planned_topics_that_duplicate_a_real_course_are_dropped():
    body = client.get("/audio/search", params={"q": "machine learning", "include_planned": "true"}).json()
    assert "Introduction to Machine Learning" not in _titles(body, "planned")   # the real course is "Intro to Machine Learning"


def test_the_alias_table_is_served_for_the_client():
    body = client.get("/audio/search", params={"limit": 1}).json()
    assert any("cpr" in g and "first aid" in g for g in body["aliases"])
