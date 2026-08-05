"""Tests for the xAI (Grok) voice agent: fallback + mocked real transport."""

from __future__ import annotations

from webcam_recognition.config import LabConfig
from webcam_recognition.voice_agent import (
    ClassroomContext,
    XAIVoiceAgent,
    _XAIError,
)


def test_fallback_when_no_key():
    agent = XAIVoiceAgent(LabConfig(xai_api_key=""))
    assert agent.configured is False
    reply = agent.respond(ClassroomContext(event="arrived", learner_name="Sam"))
    assert reply.source == "fallback"
    assert "Sam" in reply.text
    assert reply.persona == "Theodore"
    assert reply.ssml.startswith("<speak>")


def test_fallback_left_event_mentions_pause():
    agent = XAIVoiceAgent(LabConfig(xai_api_key=""))
    reply = agent.respond(ClassroomContext(event="left", away_seconds=12))
    assert reply.source == "fallback"
    assert reply.text  # non-empty, natural


def test_fallback_group_left_mentions_group():
    agent = XAIVoiceAgent(LabConfig(xai_api_key=""))
    reply = agent.respond(ClassroomContext(class_mode="group", event="left"))
    assert "group" in reply.text.lower()


def test_fallback_answers_user_message():
    agent = XAIVoiceAgent(LabConfig(xai_api_key=""))
    reply = agent.respond(ClassroomContext(), user_message="What is a fraction?")
    assert reply.source == "fallback"
    assert reply.text


def test_system_prompt_reflects_mode():
    agent = XAIVoiceAgent(LabConfig())
    theo = agent.system_prompt(ClassroomContext(teaching_mode="theodore", class_mode="solo"))
    selfp = agent.system_prompt(ClassroomContext(teaching_mode="self", class_mode="group"))
    assert "leading the lesson" in theo
    assert "one-on-one" in theo
    assert "supportive tutor" in selfp
    assert "group class" in selfp


def test_real_transport_is_used_when_configured(monkeypatch):
    agent = XAIVoiceAgent(LabConfig(xai_api_key="sk-test", xai_model="grok-2-latest"))
    assert agent.configured is True
    captured = {}

    def fake_transport(payload, *, stream):
        captured["payload"] = payload
        captured["stream"] = stream
        return {"choices": [{"message": {"content": "Hello class, let us begin!"}}]}

    monkeypatch.setattr(agent, "_transport", fake_transport)
    reply = agent.respond(ClassroomContext(event="arrived"))
    assert reply.source == "xai"
    assert reply.text == "Hello class, let us begin!"
    assert captured["payload"]["model"] == "grok-2-latest"
    assert captured["stream"] is False


def test_falls_back_when_transport_errors(monkeypatch):
    agent = XAIVoiceAgent(LabConfig(xai_api_key="sk-test"))

    def boom(payload, *, stream):
        raise _XAIError("network down")

    monkeypatch.setattr(agent, "_transport", boom)
    reply = agent.respond(ClassroomContext(event="arrived", learner_name="Kim"))
    assert reply.source == "fallback"
    assert "Kim" in reply.text


def test_stream_yields_deltas(monkeypatch):
    agent = XAIVoiceAgent(LabConfig(xai_api_key="sk-test"))

    def fake_transport(payload, *, stream):
        assert stream is True
        return [
            '{"choices":[{"delta":{"content":"Hi "}}]}',
            '{"choices":[{"delta":{"content":"there"}}]}',
        ]

    monkeypatch.setattr(agent, "_transport", fake_transport)
    out = "".join(agent.respond_stream(ClassroomContext(event="arrived")))
    assert out == "Hi there"


def test_stream_falls_back_on_error(monkeypatch):
    agent = XAIVoiceAgent(LabConfig(xai_api_key="sk-test"))

    def boom(payload, *, stream):
        raise _XAIError("down")

    monkeypatch.setattr(agent, "_transport", boom)
    out = "".join(agent.respond_stream(ClassroomContext(event="left")))
    assert out
