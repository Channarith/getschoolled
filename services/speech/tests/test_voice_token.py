"""Speech gateway xAI Grok Voice token endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from speech_gw.main import app

client = TestClient(app)


def _set_xai(monkeypatch, *, key: str, model: str = "grok-voice-latest", voice: str = "eve"):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    cfg = app.state.config.model_copy(
        update={"xai_api_key": key, "xai_voice_model": model, "xai_voice_id": voice}
    )
    monkeypatch.setattr(app.state, "config", cfg)


def test_voice_status_unconfigured(monkeypatch):
    _set_xai(monkeypatch, key="")
    r = client.get("/voice/status")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["engine"] == "none"
    assert "XAI_API_KEY" in body["hint"]


def test_voice_status_configured(monkeypatch):
    _set_xai(monkeypatch, key="xai-test-key")
    r = client.get("/voice/status")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["engine"] == "xai-grok-voice"
    assert body["model"] == "grok-voice-latest"
    assert body["voice"] == "eve"


def test_voice_token_requires_key(monkeypatch):
    _set_xai(monkeypatch, key="")
    r = client.post("/voice/token", json={"mode": "solo", "lesson_context": "Fractions"})
    assert r.status_code == 503


def test_voice_token_mints(monkeypatch):
    from aoep_shared import xai_realtime as xr

    _set_xai(monkeypatch, key="xai-test-key")

    class FakeTok:
        mock = False
        value = "ephem-xyz"
        expires_at = 1_700_000_000
        model = "grok-voice-latest"

        def to_dict(self):
            return {
                "value": self.value,
                "expires_at": self.expires_at,
                "mock": False,
                "model": self.model,
                "websocket_url": "wss://api.x.ai/v1/realtime?model=grok-voice-latest",
                "websocket_protocol": f"xai-client-secret.{self.value}",
            }

    minted = {}

    def fake_mint(**kwargs):
        minted.update(kwargs)
        return FakeTok()

    monkeypatch.setattr(xr, "mint_ephemeral_token", fake_mint)
    r = client.post(
        "/voice/token",
        json={
            "mode": "theodore_solo",
            "lesson_context": "Intro to fractions",
            "learner_names": ["Ada"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token"]["value"] == "ephem-xyz"
    assert body["session_update"]["type"] == "session.update"
    assert "Theodore" in body["session_update"]["session"]["instructions"]
    assert body["engine"] == "xai-grok-voice"
    assert minted["session"]["model"] == "grok-voice-latest"
    assert minted["session"]["tools"][0]["name"] == "get_learner_presence"
