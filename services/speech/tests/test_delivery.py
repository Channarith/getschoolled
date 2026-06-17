"""Phase 2 - multilingual delivery routing tests."""

from fastapi.testclient import TestClient

from aoep_shared.translation import (
    is_pair_supported,
    plan_delivery,
    tts_engine_for,
    unsupported_languages,
)
from speech_gw.main import app

client = TestClient(app)


def test_pair_support_and_engine():
    assert is_pair_supported("en", "sw") is True
    assert is_pair_supported("en", "klingon") is False
    assert tts_engine_for("en") == "xtts"
    # sw (Swahili) is supported for ASR/MT but needs the TTS fallback.
    assert tts_engine_for("sw") == "cloud-tts-fallback"


def test_plan_delivery_mixed_room():
    plans = plan_delivery(
        "en",
        [("a", "en"), ("b", "es"), ("c", "sw"), ("d", "klingon")],
    )
    by_id = {p.student_id: p for p in plans}
    assert by_id["a"].translate is False               # same as lesson
    assert by_id["b"].translate is True and by_id["b"].translation_supported
    assert by_id["b"].tts_engine == "xtts"
    assert by_id["c"].translate is True and by_id["c"].tts_engine == "cloud-tts-fallback"
    assert by_id["d"].supported is False and by_id["d"].tts_engine == "none"


def test_unsupported_languages_helper():
    assert unsupported_languages(["en", "xx", "es", "zz"]) == ["xx", "zz"]


def test_delivery_plan_api():
    r = client.post(
        "/delivery/plan",
        json={"lesson_language": "en", "students": [
            {"student_id": "s1", "language": "fr"},
            {"student_id": "s2", "language": "sw"},
        ]},
    )
    assert r.status_code == 200, r.text
    plans = {p["student_id"]: p for p in r.json()["plans"]}
    assert plans["s1"]["translate"] is True
    assert plans["s2"]["tts_engine"] == "cloud-tts-fallback"


def test_translate_validates_pair_then_needs_model():
    bad = client.post("/translate", json={"text": "hi", "source": "en", "target": "zz"})
    assert bad.status_code == 422
    # Valid pair, but the NLLB model is not loaded in this environment -> 503.
    ok = client.post("/translate", json={"text": "hi", "source": "en", "target": "es"})
    assert ok.status_code == 503


def test_invalid_lesson_language_422():
    r = client.post("/delivery/plan", json={"lesson_language": "zz", "students": []})
    assert r.status_code == 422
