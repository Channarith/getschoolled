"""Regression test for the 2026-08-17 audit (speech gateway).

- MED-7  An ElevenLabs read timeout (bare TimeoutError, not ElevenLabsError)
         escaped the fallback chain and 500'd the /tts request instead of
         falling through to edge-tts / the 501 client-voice signal.
"""

from fastapi.testclient import TestClient

from speech_gw.main import app

client = TestClient(app)


def test_elevenlabs_timeout_falls_through_instead_of_500(monkeypatch):
    from aoep_shared import cosyvoice_tts, elevenlabs_tts
    from aoep_shared.meeting import natural_tts

    monkeypatch.setattr(cosyvoice_tts, "cosyvoice_configured", lambda *a, **k: False)
    monkeypatch.setattr(elevenlabs_tts, "elevenlabs_configured", lambda *a, **k: True)

    def slow_read(*a, **k):
        raise TimeoutError("read timed out")

    monkeypatch.setattr(elevenlabs_tts, "synthesize", slow_read)
    monkeypatch.setattr(natural_tts, "synthesize_neural", lambda *a, **k: False)

    r = client.post("/tts", json={"text": "hello world"})
    # No server engine left -> 501 (client uses the device voice), never 500.
    assert r.status_code == 501
