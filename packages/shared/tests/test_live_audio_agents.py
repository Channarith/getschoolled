from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from aoep_shared import live_audio_agents as live
from aoep_shared.xai_realtime import EphemeralToken


def test_status_only_advertises_native_audio_when_configured(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    status = live.provider_status()
    assert status["available"] is False
    assert status["default"] == ""
    assert all(not row["available"] for row in status["providers"].values())
    assert "TTS" not in status["providers"]

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    status = live.provider_status()
    assert status["default"] == "gemini"
    assert status["providers"]["gemini"]["input_rate"] == 16000

    monkeypatch.setenv("XAI_API_KEY", "xai-secret")
    status = live.provider_status()
    assert status["default"] == "xai"
    assert status["providers"]["xai"]["input_rate"] == 24000


def test_gemini_token_is_one_use_v1alpha_and_never_returns_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "do-not-leak")
    request = {}

    def fake(url, payload, headers, *, timeout=15.0):
        request.update(url=url, payload=payload, headers=headers, timeout=timeout)
        return {"name": "auth_tokens/short-lived", "expireTime": "later"}

    monkeypatch.setattr(live, "_post_json", fake)
    token = live.mint_provider_token(
        "gemini",
        context="Fractions",
        instructions="Teach with questions.",
    )
    assert request["url"].endswith("/v1alpha/auth_tokens")
    assert request["payload"]["uses"] == 1
    assert request["payload"]["bidiGenerateContentSetup"]["tools"] == []
    assert request["headers"]["x-goog-api-key"] == "do-not-leak"
    serialized = json.dumps(token)
    assert "do-not-leak" not in serialized
    assert "access_token=auth_tokens/short-lived" in token["websocket_url"]
    setup = token["setup"]["setup"]
    assert setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert setup["systemInstruction"]["parts"][0]["text"].startswith(
        "Teach with questions."
    )
    assert token["input_rate"] == 16000
    assert token["output_rate"] == 24000


def test_xai_token_uses_ephemeral_protocol_and_native_pcm(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-secret")
    monkeypatch.setattr(
        live,
        "mint_ephemeral_token",
        lambda **_kwargs: EphemeralToken(
            value="short-lived", expires_at=1234, model="grok-voice-latest"
        ),
    )
    token = live.mint_provider_token(
        "xai", context="Geometry", instructions="Keep it spoken."
    )
    assert token["websocket_protocol"] == "xai-client-secret.short-lived"
    assert token["setup"]["type"] == "session.update"
    assert token["setup"]["session"]["audio"]["input"]["format"]["rate"] == 24000
    assert token["input_rate"] == token["output_rate"] == 24000
    assert "xai-secret" not in json.dumps(token)


def test_inject_client_is_idempotent():
    page = "<html><body><h1>Lab</h1></body></html>"
    once = live.inject_client(page)
    twice = live.inject_client(once)
    assert once == twice
    assert once.count("/api/live-audio/client.js") == 1
    assert once.index("/api/live-audio/client.js") < once.index("</body>")


def test_routes_expose_status_client_and_reject_unconfigured_token(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    app = FastAPI()
    live.install_live_audio_routes(app, lab_name="Test Lab")
    client = TestClient(app)

    status = client.get("/api/live-audio/status")
    assert status.status_code == 200
    assert status.json()["available"] is False
    script = client.get("/api/live-audio/client.js")
    assert script.status_code == 200
    assert "input_audio_buffer.append" in script.text
    assert "realtimeInput" in script.text
    assert 'fetch("/tts' not in script.text
    token = client.post("/api/live-audio/token", json={"provider": "xai"})
    assert token.status_code == 503
    assert "not configured" in token.json()["detail"]
    denied = client.post(
        "/api/live-audio/token",
        json={"provider": "xai"},
        headers={"origin": "https://evil.example", "host": "testserver"},
    )
    assert denied.status_code == 403


def test_browser_client_parses_and_has_gapless_barge_in():
    script = live.CLIENT_JS
    result = subprocess.run(
        ["node", "--check", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    source = script.read_text()
    assert "state.nextPlayAt" in source
    assert "input_audio_buffer.speech_started" in source
    assert "server.interrupted" in source
    assert "echoCancellation:true" in source
    assert "noiseSuppression:true" in source
    assert "AudioWorkletNode" in source
    assert "createMediaStreamDestination" in source
    assert "__THEODORE_LIVE_AUDIO_ACTIVE__" in source
