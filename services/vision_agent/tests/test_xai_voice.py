"""Tests for aoep_shared.xai_grok_voice (GrokVoiceAgent + helpers).

All HTTP calls are intercepted via monkeypatch of ``_http_post`` so no real
xAI API key is needed.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(text: str = "Hello, student!", model: str = "grok-2-1212"):
    return {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "model": model,
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }


# ---------------------------------------------------------------------------
# xai_available
# ---------------------------------------------------------------------------

def test_xai_available_with_key():
    from aoep_shared.xai_grok_voice import xai_available
    assert xai_available("xai-somekey") is True


def test_xai_available_without_key():
    from aoep_shared.xai_grok_voice import xai_available
    assert xai_available("") is False
    assert xai_available("   ") is False


# ---------------------------------------------------------------------------
# GrokVoiceAgent — text query
# ---------------------------------------------------------------------------

def test_respond_to_query(monkeypatch):
    from aoep_shared import xai_grok_voice as xai_voice
    monkeypatch.setattr(xai_voice, "_http_post", lambda *a, **kw: _mock_response("Great question!"))

    agent = xai_voice.GrokVoiceAgent(api_key="xai-test")
    resp = agent.respond_to_query("What is photosynthesis?")
    assert resp.text == "Great question!"
    assert resp.model == "grok-2-1212"
    assert resp.usage_completion_tokens == 20


def test_respond_to_query_non_english(monkeypatch):
    from aoep_shared import xai_grok_voice as xai_voice
    calls = []
    def _capture(url, payload, key):
        calls.append(payload)
        return _mock_response("Bonjour!")
    monkeypatch.setattr(xai_voice, "_http_post", _capture)

    agent = xai_voice.GrokVoiceAgent(api_key="xai-test")
    resp = agent.respond_to_query("Bonjour", language="fr")
    assert "fr" in calls[0]["messages"][0]["content"]


def test_respond_to_query_no_key():
    from aoep_shared.xai_grok_voice import GrokVoiceAgent
    agent = GrokVoiceAgent(api_key="")
    with pytest.raises(NotImplementedError):
        agent.respond_to_query("test")


# ---------------------------------------------------------------------------
# GrokVoiceAgent — absence prompt
# ---------------------------------------------------------------------------

def test_generate_absence_prompt(monkeypatch):
    from aoep_shared import xai_grok_voice as xai_voice
    monkeypatch.setattr(xai_voice, "_http_post", lambda *a, **kw: _mock_response("We miss you!"))
    agent = xai_voice.GrokVoiceAgent(api_key="xai-test")
    resp = agent.generate_absence_prompt(30.0, lesson_title="Photosynthesis")
    assert resp.text == "We miss you!"
    # Absence prompt should NOT accumulate in history (no context pollution).
    assert len(agent._history) == 0


# ---------------------------------------------------------------------------
# GrokVoiceAgent — frame response
# ---------------------------------------------------------------------------

def test_respond_to_frame(monkeypatch):
    from aoep_shared import xai_grok_voice as xai_voice
    monkeypatch.setattr(xai_voice, "_http_post", lambda *a, **kw: _mock_response(
        "The student appears focused.", model="grok-2-vision-1212"
    ))
    agent = xai_voice.GrokVoiceAgent(api_key="xai-test")
    frame = b"\xff\xd8\xff"  # minimal JPEG magic bytes
    resp = agent.respond_to_frame(frame, presence_state="present_face", attention=0.8)
    assert "focused" in resp.text
    assert resp.model == "grok-2-vision-1212"


# ---------------------------------------------------------------------------
# GrokVoiceAgent — conversation history
# ---------------------------------------------------------------------------

def test_conversation_history_grows(monkeypatch):
    from aoep_shared import xai_grok_voice as xai_voice
    monkeypatch.setattr(xai_voice, "_http_post", lambda *a, **kw: _mock_response("Answer"))
    agent = xai_voice.GrokVoiceAgent(api_key="xai-test", max_history=3)
    for _ in range(3):
        agent.respond_to_query("question")
    assert len(agent._history) == 6  # 3 pairs (user + assistant)


def test_conversation_history_capped(monkeypatch):
    from aoep_shared import xai_grok_voice as xai_voice
    monkeypatch.setattr(xai_voice, "_http_post", lambda *a, **kw: _mock_response("A"))
    agent = xai_voice.GrokVoiceAgent(api_key="xai-test", max_history=2)
    for _ in range(10):
        agent.respond_to_query("q")
    assert len(agent._history) <= 4  # max_history * 2


def test_clear_history(monkeypatch):
    from aoep_shared import xai_grok_voice as xai_voice
    monkeypatch.setattr(xai_voice, "_http_post", lambda *a, **kw: _mock_response("A"))
    agent = xai_voice.GrokVoiceAgent(api_key="xai-test")
    agent.respond_to_query("question one")
    assert len(agent._history) > 0
    agent.clear_history()
    assert agent._history == []


# ---------------------------------------------------------------------------
# GrokVoiceAgent — session context
# ---------------------------------------------------------------------------

def test_solo_session_context():
    from aoep_shared.xai_grok_voice import GrokVoiceAgent
    agent = GrokVoiceAgent(
        api_key="xai-test",
        session_context={"class_type": "solo", "lesson_title": "Cell Biology"},
    )
    assert "SOLO" in agent._system
    assert "Cell Biology" in agent._system


def test_group_session_context():
    from aoep_shared.xai_grok_voice import GrokVoiceAgent
    agent = GrokVoiceAgent(
        api_key="xai-test",
        session_context={"class_type": "group", "student_name": "Aisha"},
    )
    assert "GROUP" in agent._system
    assert "Aisha" in agent._system


# ---------------------------------------------------------------------------
# _http_post raises NotImplementedError when key missing
# ---------------------------------------------------------------------------

def test_http_post_no_key():
    from aoep_shared.xai_grok_voice import _http_post
    with pytest.raises(NotImplementedError, match="XAI_API_KEY"):
        _http_post("https://api.x.ai/v1/chat/completions", {}, "")
