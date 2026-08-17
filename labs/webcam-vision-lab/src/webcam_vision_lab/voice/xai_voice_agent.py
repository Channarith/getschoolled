"""xAI Grok Speech-to-Speech (realtime voice agent) client helpers.

Docs: https://docs.x.ai/developers/model-capabilities/audio/voice-agent
WebSocket: wss://api.x.ai/v1/realtime?model=grok-voice-latest
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional


DEFAULT_REALTIME_URL = "wss://api.x.ai/v1/realtime"
DEFAULT_MODEL = "grok-voice-latest"
DEFAULT_VOICE = "ara"


@dataclass
class XaiVoiceAgentConfig:
    api_key: str = ""
    model: str = DEFAULT_MODEL
    voice: str = DEFAULT_VOICE
    instructions: str = ""
    turn_detection: dict[str, Any] = field(
        default_factory=lambda: {"type": "server_vad", "silence_duration_ms": 600}
    )
    tools: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> XaiVoiceAgentConfig:
        return cls(
            api_key=(os.environ.get("XAI_API_KEY") or "").strip(),
            model=(os.environ.get("XAI_VOICE_MODEL") or DEFAULT_MODEL).strip(),
            voice=(os.environ.get("XAI_VOICE_NAME") or DEFAULT_VOICE).strip(),
        )

    def realtime_url(self) -> str:
        return f"{DEFAULT_REALTIME_URL}?model={self.model}"

    def websocket_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ValueError("XAI_API_KEY is required for voice agent connections")
        return {"Authorization": f"Bearer {self.api_key}"}

    def configured(self) -> bool:
        return bool(self.api_key)


def build_session_update(config: XaiVoiceAgentConfig) -> dict[str, Any]:
    """First message after WebSocket connect — mirrors xAI session.update."""
    session: dict[str, Any] = {
        "voice": config.voice,
        "instructions": config.instructions or "You are a helpful assistant.",
        "turn_detection": config.turn_detection,
    }
    if config.tools:
        session["tools"] = config.tools
    return {"type": "session.update", "session": session}


def build_input_audio_append(pcm16_chunk: bytes) -> dict[str, Any]:
    """Append base64 PCM16 audio to the input buffer."""
    import base64

    return {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(pcm16_chunk).decode("ascii"),
    }


async def connect_voice_agent(config: XaiVoiceAgentConfig):
    """Async context manager yielding a connected xAI realtime WebSocket."""
    import websockets

    ws = await websockets.connect(
        config.realtime_url(),
        additional_headers=config.websocket_headers(),
    )
    await ws.send(json.dumps(build_session_update(config)))
    return ws


def ephemeral_token_request_payload(
    config: XaiVoiceAgentConfig,
) -> dict[str, Any]:
    """Body for POST /v1/realtime/client_secrets (browser-safe auth)."""
    return {
        "session": {
            "model": config.model,
            "voice": config.voice,
            "instructions": config.instructions,
            "turn_detection": config.turn_detection,
        }
    }
