from __future__ import annotations

from theodore_webcam_lab.types import ClassMode
from theodore_webcam_lab.voice_agents import SUPPORTED_LANGUAGES, XaiVoiceAgent


def test_local_fallback_when_no_api_key():
    agent = XaiVoiceAgent(api_key="")
    response = agent.respond(
        learner_message="I keep missing this math step.",
        class_mode=ClassMode.SOLO,
    )
    assert response.provider == "local-fallback"
    assert response.fallback_used is True
    assert "math" in response.message
    assert response.latency_ms >= 0
    assert response.tts_engine_chain == ["elevenlabs", "edge-tts", "device"]
    assert response.should_stream_audio is True


def test_xai_response_when_transport_succeeds(monkeypatch):
    agent = XaiVoiceAgent(api_key="test-key", model="grok-4")

    def _fake_transport(payload: dict, *, timeout_s=None) -> dict:
        assert payload["model"] == "grok-4"
        return {
            "choices": [
                {"message": {"content": "Great question. Let's solve it together."}}
            ]
        }

    monkeypatch.setattr(agent, "_transport", _fake_transport)
    response = agent.respond(
        learner_message="Can you explain inertia again?",
        class_mode=ClassMode.GROUP,
        context="Physics review session",
    )
    assert response.provider == "xai"
    assert response.fallback_used is False
    assert response.message.startswith("Great question.")
    assert response.latency_ms >= 0
    assert response.cache_hit is False


def test_respond_uses_short_ttl_cache_for_repeated_turn(monkeypatch):
    agent = XaiVoiceAgent(api_key="test-key", model="grok-4", cache_ttl_s=60)
    calls = {"count": 0}

    def _fake_transport(payload: dict, *, timeout_s=None) -> dict:
        calls["count"] += 1
        return {"choices": [{"message": {"content": "Fast response."}}]}

    monkeypatch.setattr(agent, "_transport", _fake_transport)
    first = agent.respond(
        learner_message="Explain photosynthesis quickly",
        class_mode=ClassMode.SOLO,
        session_id="session-1",
    )
    second = agent.respond(
        learner_message="Explain photosynthesis quickly",
        class_mode=ClassMode.SOLO,
        session_id="session-1",
    )
    assert first.message == "Fast response."
    assert second.message == "Fast response."
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert calls["count"] == 1


def test_supported_languages_cover_26_language_codes():
    languages = XaiVoiceAgent.supported_languages()
    assert len(languages) == 26
    assert len({item.code for item in languages}) == 26
    assert [item.code for item in languages] == [item.code for item in SUPPORTED_LANGUAGES]


def test_ask_question_fallback_for_supported_language():
    agent = XaiVoiceAgent(api_key="")
    result = agent.ask_question(
        class_mode=ClassMode.GROUP,
        language_code="es",
        topic="gravity",
        difficulty="easy",
        context="middle school",
    )
    assert result.provider == "local-fallback"
    assert result.language_code == "es"
    assert result.fallback_used is True
    assert "gravity" in result.question
    assert result.latency_ms >= 0


def test_absorb_audio_answer_fallback_scores_transcript():
    agent = XaiVoiceAgent(api_key="")
    result = agent.absorb_audio_answer(
        class_mode=ClassMode.SOLO,
        language_code="fr",
        question="What is photosynthesis?",
        audio_transcript="Photosynthesis turns sunlight into plant energy with chlorophyll.",
        expected_answer="plants use sunlight and chlorophyll to produce energy",
    )
    assert result.provider == "local-fallback"
    assert result.language_code == "fr"
    assert result.understood is True
    assert result.correctness_score > 0.35
    assert result.latency_ms >= 0


def test_rejects_unsupported_language_code():
    agent = XaiVoiceAgent(api_key="")
    try:
        agent.ask_question(
            class_mode=ClassMode.SOLO,
            language_code="xx",
            topic="fractions",
        )
    except ValueError as exc:
        assert "Unsupported language code" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported language code")
