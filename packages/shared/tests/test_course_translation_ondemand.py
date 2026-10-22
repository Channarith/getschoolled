"""On-demand course translation: switched off by default, capped, never mixed."""

from __future__ import annotations

import pytest
from aoep_shared import audio_courses as audio
from aoep_shared import course_translation_ondemand as od


@pytest.fixture(autouse=True)
def _fresh(monkeypatch, tmp_path):
    monkeypatch.setenv("AOEP_COURSE_TRANSLATION_DIR", str(tmp_path))
    od.set_store_for_tests(od._MemoryKV())
    audio._TRANSLATED_COURSES.clear()
    yield
    od.set_store_for_tests(None)


def _course():
    return next(c for c in audio.build_catalog("en", "en") if not c.id.startswith("lang-"))


def _segments(course):
    return [{"heading": s.heading, "text": s.text, "kind": s.kind} for s in course.segments]


def fake(text, source, target):
    return f"[{target}] {text}"


def test_off_by_default_nothing_is_requested(monkeypatch):
    monkeypatch.delenv("AOEP_ON_DEMAND_TRANSLATION", raising=False)
    c = _course()
    assert od.request_course_translation(c.id, c.title, _segments(c), "fr", fake, background=False) is False


def test_translates_once_then_serves_the_saved_copy(monkeypatch):
    monkeypatch.setenv("AOEP_ON_DEMAND_TRANSLATION", "1")
    c = _course()
    assert od.request_course_translation(c.id, c.title, _segments(c), "fr", fake, background=False)
    assert od.get_cached(c.id, "fr", len(c.segments))
    # a second ask does nothing and does not translate again
    calls = []
    assert od.request_course_translation(
        c.id, c.title, _segments(c), "fr", lambda *a: calls.append(a), background=False) is False
    assert not calls
    served = audio.get_course(c.id, locale="en", training_locale="fr")
    assert served.body_locale == "fr" and served.segments[1].text.startswith("[fr] ")


def test_a_failed_segment_saves_nothing_so_languages_never_mix(monkeypatch):
    monkeypatch.setenv("AOEP_ON_DEMAND_TRANSLATION", "1")
    c = _course()
    seen = {"n": 0}

    def flaky(text, source, target):
        seen["n"] += 1
        return None if seen["n"] == 5 else f"[{target}] {text}"

    od.request_course_translation(c.id, c.title, _segments(c), "fr", flaky, background=False)
    assert od.get_cached(c.id, "fr", len(c.segments)) is None


def test_daily_limit_stops_new_translations(monkeypatch):
    monkeypatch.setenv("AOEP_ON_DEMAND_TRANSLATION", "1")
    monkeypatch.setenv("AOEP_ON_DEMAND_DAILY_LIMIT", "1")
    cs = [c for c in audio.build_catalog("en", "en") if not c.id.startswith("lang-")][:2]
    assert od.request_course_translation(cs[0].id, cs[0].title, _segments(cs[0]), "fr", fake, background=False)
    assert not od.request_course_translation(cs[1].id, cs[1].title, _segments(cs[1]), "fr", fake, background=False)


def test_nllb_is_tried_first_and_grok_is_the_failover(monkeypatch):
    monkeypatch.setattr(od, "nllb_translate", lambda t, s, g: None)
    monkeypatch.setattr(od, "grok_translate", lambda t, s, g: f"grok {t}")
    assert od.chain_translate("hi", "en", "fr") == "grok hi"
    monkeypatch.setattr(od, "nllb_translate", lambda t, s, g: f"nllb {t}")
    assert od.chain_translate("hi", "en", "fr") == "nllb hi"
