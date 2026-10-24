"""An unsupported language is the caller's mistake (400), not an upstream outage (502)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from speech_gw.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_unsupported_language_is_400():
    r = client.get("/tts/engine", params={"language": "zz-not-a-language"})
    assert r.status_code == 400
    assert "Unsupported language" in r.json()["detail"]


def test_supported_language_still_resolves():
    r = client.get("/tts/engine", params={"language": "en"})
    assert r.status_code == 200
