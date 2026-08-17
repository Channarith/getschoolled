from __future__ import annotations

from theodore_course_studio.studio_languages import (
    LANGUAGE_NAMES,
    SUPPORTED_LANGUAGES,
    language_instruction,
    list_languages,
    normalize_language,
)
from theodore_course_studio.voice_agent import CourseStudioVoiceAgent


def test_platform_languages_cover_full_set():
    assert len(SUPPORTED_LANGUAGES) == 27
    assert "en" in SUPPORTED_LANGUAGES
    assert "km" in SUPPORTED_LANGUAGES  # brand language
    assert "zh" in SUPPORTED_LANGUAGES
    rows = list_languages()
    assert len(rows) == 27
    assert all(r["code"] in LANGUAGE_NAMES for r in rows)


def test_normalize_language_aliases():
    assert normalize_language("es-419") == "es"
    assert normalize_language("EN") == "en"
    assert normalize_language("nope") == "en"
    assert "Spanish" in language_instruction("es")


def test_voice_agent_offline_fallback(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    agent = CourseStudioVoiceAgent(api_key="")
    assert agent.available is False
    status = agent.status()
    assert status["provider"] == "local-fallback"
    assert status["offline_ok"] is True
    turn = agent.respond(
        session_id="s1",
        learner_message="Explain active listening",
        language_code="es",
    )
    assert turn.fallback_used is True
    assert turn.provider == "local-fallback"
    assert turn.language_code == "es"
    assert "Spanish" in turn.message or turn.language_name == "Spanish"


def test_voice_agent_live_xai_path(monkeypatch):
    """With a key AND reachable API, the xAI reply is used (HTTP mocked)."""
    import json
    from io import BytesIO

    agent = CourseStudioVoiceAgent(api_key="test-key", model="grok-2-1212")
    assert agent.available is True

    captured: dict = {}

    class _Resp:
        def __init__(self, payload: bytes) -> None:
            self._buf = BytesIO(payload)

        def read(self):
            return self._buf.read()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        captured["url"] = req.full_url
        captured["auth"] = req.headers.get("Authorization")
        captured["body"] = json.loads(req.data.decode("utf-8"))
        payload = {
            "choices": [
                {"message": {"content": "Escucha activa: repite lo que oíste."}}
            ]
        }
        return _Resp(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "theodore_course_studio.voice_agent.urllib.request.urlopen", fake_urlopen
    )
    # Skip the aoep_shared path so the direct client is exercised.
    monkeypatch.setattr(
        CourseStudioVoiceAgent, "_try_shared_agent", lambda *a, **k: None
    )

    turn = agent.respond(
        session_id="live1",
        learner_message="Explain active listening",
        language_code="es",
    )
    assert turn.provider == "xai"
    assert turn.fallback_used is False
    assert "Escucha activa" in turn.message
    assert captured["url"].endswith("/chat/completions")
    assert captured["auth"] == "Bearer test-key"
    # Language instruction must reach the model.
    system = captured["body"]["messages"][0]["content"]
    assert "Spanish" in system


def test_voice_agent_falls_back_when_api_unreachable(monkeypatch):
    agent = CourseStudioVoiceAgent(api_key="test-key")

    def boom(*_a, **_k):
        raise OSError("Connection reset by peer")

    monkeypatch.setattr(
        "theodore_course_studio.voice_agent.urllib.request.urlopen", boom
    )
    monkeypatch.setattr(
        CourseStudioVoiceAgent, "_try_shared_agent", lambda *a, **k: None
    )
    turn = agent.respond(session_id="s2", learner_message="Hello", language_code="km")
    assert turn.provider == "local-fallback"
    assert turn.fallback_used is True
    assert turn.language_name == "Khmer"


def test_languages_and_voice_api():
    from fastapi.testclient import TestClient
    from theodore_course_studio.main import app

    client = TestClient(app)
    langs = client.get("/api/studio/languages")
    assert langs.status_code == 200
    assert langs.json()["count"] == 27
    voice = client.get("/api/studio/voice/status")
    assert voice.status_code == 200
    assert "voice" in voice.json()
    health = client.get("/health")
    assert health.json()["languages"] == 27
    page = client.get("/studio")
    assert "teach-lang" in page.text
    assert "Ask Theodore" in page.text
    assert "xAI" in page.text or "voice-status" in page.text
