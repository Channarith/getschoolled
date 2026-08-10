from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from theodore_audio_translation_lab.audio_policy import (
    AudioPolicy,
    get_policy,
    reset_policy,
)
from theodore_audio_translation_lab.main import app
from theodore_audio_translation_lab.providers import _PHRASEBOOK, TranslationEngine
from theodore_audio_translation_lab.quality_telemetry import SessionQualityStore

client = TestClient(app)


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_policy_exposes_more_than_twenty_knobs():
    policy = AudioPolicy()
    knobs = policy.knob_names()
    assert len(knobs) >= 28
    # A representative sample of the newly-added quality/latency knobs.
    for name in (
        "mt_timeout_s",
        "xai_timeout_s",
        "asr_timeout_s",
        "theodore_max_sentences",
        "ws_heartbeat_s",
        "interim_translate_default",
        "latency_target_p50_ms",
        "latency_target_p95_ms",
        "phrasebook_min_confidence",
        "gate_attack_ms",
        "gate_release_ms",
        "agc_target_db",
        "vad_hangover_ms",
        "max_upload_bytes",
        "whisper_temperature",
    ):
        assert name in knobs


def test_public_dict_is_flat_plus_nested_compressor():
    payload = AudioPolicy().public_dict()
    for name in AudioPolicy().knob_names():
        assert name in payload
    assert payload["compressor"]["ratio"] == 4
    assert payload["browser_constraints"]["noiseSuppression"] is True


def test_patched_coerces_types_and_ignores_unknown_keys():
    policy = AudioPolicy()
    patched = policy.patched(
        {"capture_window_ms": "1500", "theodore_temperature": 0.9, "bogus": 1}
    )
    assert patched.capture_window_ms == 1500
    assert isinstance(patched.capture_window_ms, int)
    assert patched.theodore_temperature == 0.9
    assert not hasattr(patched, "bogus")
    # Original unchanged (frozen + copy semantics).
    assert policy.capture_window_ms == 1200


def test_patch_policy_api_updates_live_and_resets():
    reset_policy()
    before = client.get("/api/audio-policy")
    assert before.status_code == 200
    patched = client.patch(
        "/api/audio-policy",
        json={"capture_window_ms": 800, "latency_target_p50_ms": 700},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["capture_window_ms"] == 800
    assert body["latency_target_p50_ms"] == 700
    assert get_policy().capture_window_ms == 800
    # Reset restores environment defaults.
    reset_back = client.patch("/api/audio-policy", json={"reset": True})
    assert reset_back.json()["capture_window_ms"] == 1200
    reset_policy()


def test_telemetry_store_reports_more_than_twenty_keys():
    store = SessionQualityStore()
    sid = "tele-1"
    store.record_transcript(sid, is_final=True, end_of_turn=True, language="en", role="learner")
    store.record_transcript(sid, is_final=False, language="en", role="learner")
    store.record_asr(sid, latency_ms=800, language="en")
    store.record_mt(sid, latency_ms=600, provider="offline-phrasebook", target_language="es")
    store.record_mt(sid, latency_ms=900, provider="source-fallback", target_language="fr")
    store.record_theodore(sid, latency_ms=120, fallback=True)
    store.record_gate(sid, uploaded=True, noise_floor_db=-60, peak_db=-25, speech_ratio=0.4, window_ms=1200)
    store.record_gate(sid, uploaded=False, speech_ratio=0.02)
    store.record_upload(sid, accepted=True, bytes_size=2048)
    store.record_viewers(sid, 3)

    snap = store.snapshot(sid)
    assert len(snap) >= 20
    assert snap["transcripts_final"] == 1
    assert snap["transcripts_interim"] == 1
    assert snap["end_of_turn_count"] == 1
    assert snap["asr_latency_ms_avg"] == 800
    assert snap["mt_latency_ms_count"] == 2
    assert snap["phrasebook_hits"] == 1
    assert snap["source_fallback_count"] == 1
    assert snap["theodore_fallback_count"] == 1
    assert snap["gate_skips"] == 1
    assert snap["uploads_accepted"] == 1
    assert snap["ws_viewers_peak"] == 3
    assert "es" in snap["languages_seen"]
    assert 0.0 <= snap["quality_score_0_1"] <= 1.0


def test_telemetry_endpoints_track_translation_activity():
    sid = unique("teleapi")
    client.post(
        "/api/sessions",
        json={"session_id": sid, "source_language": "en", "target_languages": ["es"]},
    )
    client.post(
        f"/api/sessions/{sid}/transcript",
        json={"text": "I need help", "source_language": "en", "is_final": True},
    )
    tele = client.get(f"/api/sessions/{sid}/telemetry")
    assert tele.status_code == 200
    data = tele.json()
    assert data["transcripts_final"] == 1
    assert data["mt_latency_ms_count"] == 1
    assert data["phrasebook_hits"] == 1
    overview = client.get("/api/telemetry/overview")
    assert overview.status_code == 200
    assert overview.json()["totals"]["sessions"] >= 1


def test_phrasebook_has_at_least_forty_entries_and_classroom_phrases():
    assert len(_PHRASEBOOK) >= 40
    engine = TranslationEngine()
    assert engine.translate("Thank you", "en", "fr").text == "Merci"
    assert engine.translate("I don't understand", "en", "zh").text == "我不明白"
    assert engine.translate("Hello", "en", "km").text == "សួស្តី"


def test_whisper_audio_marks_end_of_turn(monkeypatch):
    """Silence-ended server-Whisper windows must trigger Theodore (end_of_turn)."""
    from theodore_audio_translation_lab import main as main_mod
    from theodore_audio_translation_lab.models import AudioTranscription

    captured = {}

    def fake_transcribe(payload, *, filename, content_type, language):
        return AudioTranscription(
            text="I need help",
            language="en",
            confidence=0.9,
            provider="test-whisper",
            duration_ms=700,
        )

    original_process = main_mod.hub.process_transcript

    async def spy_process(session_id, item):
        captured["end_of_turn"] = item.end_of_turn
        return await original_process(session_id, item)

    monkeypatch.setattr(main_mod.asr, "base_url", "http://whisper:9000", raising=False)
    monkeypatch.setattr(main_mod.asr, "transcribe", fake_transcribe, raising=False)
    monkeypatch.setattr(main_mod.hub, "process_transcript", spy_process, raising=False)

    sid = unique("eot")
    resp = client.post(
        f"/api/sessions/{sid}/audio",
        data={"source_language": "en", "speaker_id": "learner"},
        files={"audio": ("chunk.webm", b"fake-audio", "audio/webm")},
    )
    assert resp.status_code == 200
    assert captured["end_of_turn"] is True
