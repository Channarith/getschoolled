"""xAI (Grok) voice agent: chat responses, streaming, offline fallback, realtime."""

from __future__ import annotations

import json

from webcam_classroom.config import WebcamLabConfig
from webcam_classroom.xai_voice import (
    SELF_COACH,
    THEODORE,
    XaiVoiceAgent,
    build_voice_agent_session,
)


def _cfg(**kw) -> WebcamLabConfig:
    base = dict(xai_api_key="", xai_text_model="grok-4.5",
                xai_voice_model="grok-voice-latest", xai_voice="eve")
    base.update(kw)
    return WebcamLabConfig(**base)


def test_offline_fallback_when_no_key():
    agent = XaiVoiceAgent(_cfg(), persona=THEODORE)
    assert agent.configured is False
    line = agent.respond("Explain variables", context="learner ana stepped away (absent from webcam)")
    assert "pause" in line.lower() or "stepped away" in line.lower()


def test_fallback_reacts_to_return_and_distraction():
    agent = XaiVoiceAgent(_cfg(), persona=THEODORE)
    back = agent.respond("welcome", context="learner is back / returned to the webcam")
    assert "welcome back" in back.lower() or "continue" in back.lower()
    distracted = agent.respond("refocus", context="learner is present but distracted / looking away")
    assert distracted


def test_self_coach_persona_differs():
    agent = XaiVoiceAgent(_cfg(), persona=SELF_COACH)
    assert "coach" in agent.system_prompt().lower() or "self-teaching" in agent.system_prompt().lower()


def test_blocking_response_via_injected_transport():
    captured = {}

    def transport(payload, stream):
        captured["payload"] = payload
        captured["stream"] = stream
        return {"choices": [{"message": {"content": "Variables store values."}}]}

    agent = XaiVoiceAgent(_cfg(), persona=THEODORE, transport=transport)
    assert agent.configured is True
    out = agent.respond("What is a variable?", context="lesson: python basics")
    assert out == "Variables store values."
    # Payload shaping: model + system prompt + live context + user turn.
    assert captured["payload"]["model"] == "grok-4.5"
    roles = [m["role"] for m in captured["payload"]["messages"]]
    assert roles[0] == "system"
    assert roles[-1] == "user"
    assert any("Live context" in m["content"] for m in captured["payload"]["messages"])
    assert captured["stream"] is False


def test_streaming_response_via_injected_transport():
    def transport(payload, stream):
        assert stream is True
        for piece in ("Hello ", "there ", "learner."):
            yield json.dumps({"choices": [{"delta": {"content": piece}}]})

    agent = XaiVoiceAgent(_cfg(), persona=THEODORE, transport=transport)
    chunks = list(agent.respond_stream("hi"))
    assert "".join(chunks) == "Hello there learner."


def test_streaming_empty_stream_falls_back():
    def transport(payload, stream):
        return iter(())  # no deltas

    agent = XaiVoiceAgent(_cfg(), persona=THEODORE, transport=transport)
    chunks = list(agent.respond_stream("keep going", context=""))
    assert chunks and chunks[0]  # produced the fallback line


def test_build_voice_agent_session_with_key():
    cfg = _cfg(xai_api_key="sk-test", xai_realtime_url="wss://api.x.ai/v1/realtime",
               xai_voice_model="grok-voice-latest", xai_voice="eve")
    sess = build_voice_agent_session(cfg, persona=THEODORE)
    assert sess["url"] == "wss://api.x.ai/v1/realtime?model=grok-voice-latest"
    assert sess["headers"]["Authorization"] == "Bearer sk-test"
    su = sess["session_update"]
    assert su["type"] == "session.update"
    assert su["session"]["voice"] == "eve"
    assert su["session"]["turn_detection"] == {"type": "server_vad"}
    assert "Theodore" in su["session"]["instructions"]


def test_build_voice_agent_session_without_key_omits_auth():
    sess = build_voice_agent_session(_cfg(), persona=SELF_COACH, voice="nova")
    assert "Authorization" not in sess["headers"]
    assert sess["session_update"]["session"]["voice"] == "nova"
