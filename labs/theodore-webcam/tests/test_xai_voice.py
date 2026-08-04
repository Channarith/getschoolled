"""xAI Grok voice agent wiring, exercised against a stubbed transport."""

from __future__ import annotations

import json

import pytest

from theodore_webcam.classroom import SessionRegistry
from theodore_webcam.config import XaiConfig, load_config
from theodore_webcam.cues import ClassMode
from theodore_webcam.xai_voice import XaiUnavailable, XaiVoiceAgent, execute_tool


class StubTransport:
    """Records calls and replays canned xAI responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "body": json.loads(body.decode()) if body else None,
                "timeout": timeout,
            }
        )
        status, payload = self.responses.pop(0)
        return status, json.dumps(payload).encode()


def configured_agent(transport=None, **overrides):
    config = XaiConfig(api_key="xai-test-key", **overrides)
    return XaiVoiceAgent(config, transport=transport)


def test_session_update_matches_the_xai_realtime_schema():
    agent = configured_agent()
    event = agent.session_update({"mode": "solo", "lesson_title": "Fractions"})

    assert event["type"] == "session.update"
    session = event["session"]
    assert session["voice"] == "eve"
    assert session["turn_detection"]["type"] == "server_vad"
    assert session["audio"]["input"]["format"]["type"] == "audio/pcm"
    assert session["audio"]["output"]["format"]["rate"] == 24000
    assert "Theodore" in session["instructions"]
    assert "solo self-teaching" in session["instructions"]
    tool_names = [t.get("name") for t in session["tools"]]
    assert "get_presence_state" in tool_names
    assert "recap_checkpoint" in tool_names


def test_instructions_change_for_group_classes():
    agent = configured_agent()
    text = agent.instructions({"mode": "group", "presence": "absent"})
    assert "group class" in text
    assert "quorum" in text
    assert "absent" in text


def test_realtime_url_pins_the_voice_model():
    agent = configured_agent()
    assert agent.realtime_url() == "wss://api.x.ai/v1/realtime?model=grok-voice-latest"


def test_start_session_mints_an_ephemeral_client_secret():
    transport = StubTransport([(200, {"value": "sk-ephemeral", "expires_at": 1893456000})])
    agent = configured_agent(transport, token_ttl_seconds=300)

    session = agent.start_session({"mode": "solo"})

    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.x.ai/v1/realtime/client_secrets"
    assert call["headers"]["Authorization"] == "Bearer xai-test-key"
    assert call["body"] == {"expires_after": {"seconds": 300}}

    assert session.ephemeral is True
    assert session.token == "sk-ephemeral"
    assert session.subprotocol == "xai-client-secret.sk-ephemeral"
    assert session.expires_at == 1893456000


def test_start_session_without_a_key_returns_an_unauthenticated_plan():
    agent = XaiVoiceAgent(XaiConfig())
    session = agent.start_session({"mode": "solo"})
    assert session.ephemeral is False
    assert session.token == ""
    assert session.session_update["type"] == "session.update"


def test_client_secret_error_is_surfaced():
    transport = StubTransport([(401, {"error": "invalid key"})])
    agent = configured_agent(transport)
    with pytest.raises(XaiUnavailable):
        agent.start_session()


def test_respond_calls_chat_completions():
    transport = StubTransport(
        [
            (
                200,
                {
                    "model": "grok-4-fast",
                    "choices": [
                        {"message": {"content": "Welcome back. We paused at slide 7."}}
                    ],
                },
            )
        ]
    )
    agent = configured_agent(transport)
    reply = agent.respond(
        "What did I miss?",
        context={"mode": "solo", "checkpoint": "slide 7", "presence": "present"},
        history=[{"role": "assistant", "content": "Earlier turn"}],
    )

    call = transport.calls[0]
    assert call["url"] == "https://api.x.ai/v1/chat/completions"
    assert call["body"]["model"] == "grok-4-fast"
    roles = [m["role"] for m in call["body"]["messages"]]
    assert roles == ["system", "assistant", "user"]
    assert reply.source == "xai"
    assert reply.text == "Welcome back. We paused at slide 7."


def test_respond_falls_back_when_xai_is_unreachable():
    def broken(*args, **kwargs):
        raise XaiUnavailable("network down")

    agent = configured_agent(broken)
    reply = agent.respond("hello", context={"mode": "solo", "checkpoint": "slide 7"})
    assert reply.source == "fallback"
    assert "slide 7" in reply.text


def test_respond_without_a_key_stays_silent_about_the_lesson_while_absent():
    agent = XaiVoiceAgent(XaiConfig())
    reply = agent.respond(
        "", context={"presence": "absent", "checkpoint": "slide 4"}
    )
    assert reply.source == "fallback"
    assert "Holding your place" in reply.text


def test_status_reports_configuration_mode():
    assert XaiVoiceAgent(XaiConfig()).status()["mode"] == "offline-fallback"
    assert configured_agent().status()["mode"] == "speech-to-speech"


def test_tools_can_read_and_steer_a_live_class(clock):
    registry = SessionRegistry(load_config({}), clock=clock)
    session = registry.create(mode=ClassMode.SOLO, lesson_title="Fractions", checkpoint="slide 7")
    session.add_participant("learner-1", "Maya")

    state = execute_tool(session, "get_presence_state")
    assert state["participant_id"] == "learner-1"
    assert state["state"] == "calibrating"
    assert state["lesson_paused"] is False

    assert execute_tool(session, "pause_lesson", {"reason": "learner away"})["lesson_paused"]
    assert session.lesson_paused is True

    recap = execute_tool(session, "recap_checkpoint", {"seconds_missed": 42})
    assert recap["checkpoint"] == "slide 7"
    assert recap["seconds_missed"] == 42
    assert session.lesson_paused is False

    assert "error" in execute_tool(session, "nonexistent_tool")
