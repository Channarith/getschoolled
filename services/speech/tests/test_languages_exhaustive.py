"""Exhaustive per-language coverage: every one of the platform's supported
languages must work across the speech surfaces (language learning course,
phrases, delivery routing, TTS engine, and a vocabulary exercise).

Parametrized over aoep_shared.languages.SUPPORTED_LANGUAGES so the count grows
automatically as we add languages, and a regression in any single language is
caught for that language specifically.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aoep_shared.languages import SUPPORTED_LANGUAGES
from speech_gw.main import app

client = TestClient(app)


def test_languages_endpoint_lists_all():
    body = client.get("/languages").json()
    assert body["count"] == len(SUPPORTED_LANGUAGES)
    assert set(body["languages"]) == set(SUPPORTED_LANGUAGES)


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_learn_course_for_every_language(lang):
    r = client.get(f"/learn/{lang}/course")
    assert r.status_code == 200, f"{lang}: {r.text}"


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_phrases_for_every_language(lang):
    r = client.get(f"/learn/{lang}/phrases")
    assert r.status_code == 200
    assert r.json()["language"] == lang


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_tts_engine_for_every_language(lang):
    r = client.get("/tts/engine", params={"language": lang})
    assert r.status_code == 200
    assert r.json()["engine"]   # an engine name is always resolved


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_delivery_plan_for_every_language(lang):
    r = client.post("/delivery/plan", json={
        "lesson_language": "en",
        "students": [{"student_id": "s1", "language": lang}],
    })
    assert r.status_code == 200, f"{lang}: {r.text}"
    plan = r.json()["plans"][0]
    assert plan["language"] == lang and plan["supported"] is True


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_vocabulary_exercise_for_every_language(lang):
    r = client.post("/learn/exercise", json={"language": lang, "skill": "vocabulary", "n": 3})
    assert r.status_code == 200, f"{lang}: {r.text}"
