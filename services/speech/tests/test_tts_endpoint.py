"""Speech gateway /tts: ElevenLabs -> edge-tts -> 501 fallback chain."""

from __future__ import annotations

from fastapi.testclient import TestClient

from speech_gw.main import app

client = TestClient(app)


def test_tts_requires_text():
    r = client.post("/tts", json={"text": "  ", "language": "en"})
    assert r.status_code == 400


def test_tts_uses_elevenlabs_when_configured(monkeypatch):
    from aoep_shared import elevenlabs_tts

    monkeypatch.setattr(elevenlabs_tts, "elevenlabs_configured", lambda *a, **k: True)
    monkeypatch.setattr(
        elevenlabs_tts, "synthesize",
        lambda text, **kw: b"\xff\xfb" + b"A" * 5000,
    )
    r = client.post("/tts", json={"text": "Welcome to the lesson", "voice_style": "warm"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.headers["x-tts-engine"] == "elevenlabs"
    assert len(r.content) > 256


def test_tts_falls_back_to_edge_then_501(monkeypatch):
    from aoep_shared import elevenlabs_tts
    from aoep_shared.meeting import natural_tts

    monkeypatch.setattr(elevenlabs_tts, "elevenlabs_configured", lambda *a, **k: False)
    # edge-tts not available in the offline test env -> synthesize_neural False.
    monkeypatch.setattr(natural_tts, "synthesize_neural", lambda *a, **k: False)
    r = client.post("/tts", json={"text": "hello", "language": "en"})
    assert r.status_code == 501


def test_tts_status_reports_engine(monkeypatch):
    from aoep_shared import elevenlabs_tts

    monkeypatch.setattr(elevenlabs_tts, "elevenlabs_configured", lambda *a, **k: True)
    r = client.get("/tts/status")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True and body["engine"] == "elevenlabs"
