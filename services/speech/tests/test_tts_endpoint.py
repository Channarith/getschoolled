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


def test_tts_voices_catalog():
    r = client.get("/tts/voices")
    assert r.status_code == 200
    groups = r.json()["groups"]
    langs = {g["language"] for g in groups}
    assert {"en", "es", "zh"} <= langs
    en = next(g for g in groups if g["language"] == "en")["voices"]
    accents = {v["accent"] for v in en}
    assert {"British", "Australian", "Texan (US South)"} <= accents


def test_tts_voice_selects_accented_edge_voice(monkeypatch):
    """Choosing a British voice renders with the British edge-tts voice."""
    from aoep_shared import elevenlabs_tts
    from aoep_shared.meeting import natural_tts

    monkeypatch.setattr(elevenlabs_tts, "elevenlabs_configured", lambda *a, **k: False)
    captured = {}

    def fake_neural(text, out_path, *, language="en", voice="", rate="+0%"):
        captured["voice"] = voice
        captured["text"] = text
        from pathlib import Path
        Path(out_path).write_bytes(b"\xff\xfb" + b"Z" * 4000)
        return True

    monkeypatch.setattr(natural_tts, "synthesize_neural", fake_neural)
    r = client.post("/tts", json={"text": "Hello class", "voice": "en_gb_f"})
    assert r.status_code == 200
    assert r.headers["x-tts-engine"] == "edge-tts"
    assert captured["voice"] == "en-GB-SoniaNeural"


def test_tts_applies_regional_slang(monkeypatch):
    """A Texan voice rewrites the narration with Texan slang before TTS."""
    from aoep_shared import elevenlabs_tts
    from aoep_shared.meeting import natural_tts

    monkeypatch.setattr(elevenlabs_tts, "elevenlabs_configured", lambda *a, **k: False)
    captured = {}

    def fake_neural(text, out_path, *, language="en", voice="", rate="+0%"):
        captured["text"] = text
        from pathlib import Path
        Path(out_path).write_bytes(b"\xff\xfb" + b"Z" * 4000)
        return True

    monkeypatch.setattr(natural_tts, "synthesize_neural", fake_neural)
    r = client.post("/tts", json={"text": "Welcome! Nice work getting here.", "voice": "en_us_tx_m"})
    assert r.status_code == 200
    # Texan dialect replaces "Nice work" -> "Good on y'all", "Welcome!" -> "Howdy ..."
    assert "Good on y'all" in captured["text"] or "Howdy" in captured["text"]
