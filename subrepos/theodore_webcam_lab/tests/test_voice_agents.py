from __future__ import annotations

from theodore_webcam_lab.types import ClassMode
from theodore_webcam_lab.voice_agents import (
    SUPPORTED_LANGUAGES,
    XAI_DEFAULT_MODEL,
    XaiVoiceAgent,
)


def test_default_model_is_a_current_canonical_slug(monkeypatch):
    """xAI retired the grok-2 family outright and redirects the grok-4-0709/"grok-4"
    aliases to grok-4.3. Depending on a retired slug means depending on a redirect
    that can be withdrawn, so the default must name a live model."""
    for key in ("XAI_MODEL", "XAI_FAST_MODEL"):
        monkeypatch.delenv(key, raising=False)
    assert not XAI_DEFAULT_MODEL.startswith("grok-2")
    assert XAI_DEFAULT_MODEL != "grok-4"

    agent = XaiVoiceAgent.from_env()
    assert agent.model == XAI_DEFAULT_MODEL
    assert agent.fast_model == XAI_DEFAULT_MODEL


def test_blank_model_env_does_not_defeat_the_default(monkeypatch):
    """An exported-but-empty XAI_MODEL used to win and send an empty model."""
    monkeypatch.setenv("XAI_MODEL", "  ")
    monkeypatch.setenv("XAI_FAST_MODEL", "")
    agent = XaiVoiceAgent.from_env()
    assert agent.model == XAI_DEFAULT_MODEL
    assert agent.fast_model == XAI_DEFAULT_MODEL


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
    # Distinct models on purpose: respond() defaults to fast_mode, so it must send
    # the FAST model. Both used to default to "grok-4", so passing only `model`
    # asserted nothing about which knob the call actually honoured.
    agent = XaiVoiceAgent(api_key="test-key", model="full-model", fast_model="fast-model")

    def _fake_transport(payload: dict, *, timeout_s=None) -> dict:
        assert payload["model"] == "fast-model"
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
    )
    second = agent.respond(
        learner_message="Explain photosynthesis quickly",
        class_mode=ClassMode.SOLO,
    )
    assert first.message == "Fast response."
    assert second.message == "Fast response."
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert calls["count"] == 1


def test_supported_languages_cover_26_language_codes():
    """Original 26 languages must still be present; list now extends beyond them."""
    languages = XaiVoiceAgent.supported_languages()
    codes = {item.code for item in languages}
    original_26 = {
        "en", "es", "fr", "de", "it", "pt", "nl", "sv", "no", "da",
        "fi", "pl", "cs", "sk", "ro", "hu", "el", "tr", "ru", "uk",
        "ar", "he", "hi", "id", "vi", "th",
    }
    assert original_26.issubset(codes), f"Missing original languages: {original_26 - codes}"
    # Must also include the newly added East/Southeast-Asian languages.
    assert {"zh-CN", "ja", "ko", "km", "my", "tl"}.issubset(codes)
    # No duplicate codes.
    assert len(codes) == len(languages)


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
