"""xAI Grok Voice Agents client + offline mock for the webcam lab.

Realtime Speech-to-Speech endpoint:
  wss://api.x.ai/v1/realtime?model=grok-voice-latest

Auth: Bearer XAI_API_KEY (server-side). When the key is missing, OfflineVoiceAgent
keeps the teaching loop testable without network.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


DEFAULT_MODEL = "grok-voice-latest"
DEFAULT_VOICE = "eve"
DEFAULT_WS_URL = "wss://api.x.ai/v1/realtime"


class VoiceAgent(Protocol):
    backend_name: str

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def speak_text(self, text: str) -> Dict[str, Any]: ...
    async def update_instructions(self, instructions: str) -> None: ...


@dataclass
class OfflineVoiceAgent:
    """Deterministic local stand-in for xAI voice (tests / no API key)."""

    instructions: str = "You are Theodore, a helpful AI teacher."
    voice: str = DEFAULT_VOICE
    backend_name: str = "offline"
    spoken: List[str] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    connected: bool = False

    async def connect(self) -> None:
        self.connected = True
        self.events.append({"type": "session.created", "backend": self.backend_name})

    async def close(self) -> None:
        self.connected = False
        self.events.append({"type": "session.closed"})

    async def update_instructions(self, instructions: str) -> None:
        self.instructions = instructions
        self.events.append({"type": "session.update", "instructions": instructions})

    async def speak_text(self, text: str) -> Dict[str, Any]:
        if not self.connected:
            await self.connect()
        self.spoken.append(text)
        result = {
            "type": "response.done",
            "backend": self.backend_name,
            "voice": self.voice,
            "text": text,
            "audio_b64": None,
        }
        self.events.append(result)
        return result


@dataclass
class XaiVoiceAgent:
    """Thin WebSocket client for xAI Speech-to-Speech voice agents.

    Network I/O is isolated so tests can monkeypatch ``_connect_ws``.
    """

    api_key: str
    model: str = DEFAULT_MODEL
    voice: str = DEFAULT_VOICE
    instructions: str = "You are Theodore, a helpful AI teacher."
    ws_base: str = DEFAULT_WS_URL
    backend_name: str = "xai"
    events: List[Dict[str, Any]] = field(default_factory=list)
    _ws: Any = field(default=None, repr=False)

    @classmethod
    def from_env(cls, *, instructions: str = "") -> "XaiVoiceAgent":
        key = os.environ.get("XAI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("XAI_API_KEY is not set")
        return cls(
            api_key=key,
            model=os.environ.get("XAI_VOICE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            voice=os.environ.get("XAI_VOICE_ID", DEFAULT_VOICE).strip() or DEFAULT_VOICE,
            instructions=instructions or "You are Theodore, a helpful AI teacher.",
        )

    @property
    def ws_url(self) -> str:
        return f"{self.ws_base}?model={self.model}"

    async def _connect_ws(self):
        import websockets  # lazy optional dep

        return await websockets.connect(
            self.ws_url,
            additional_headers={"Authorization": f"Bearer {self.api_key}"},
        )

    async def connect(self) -> None:
        if self._ws is not None:
            return
        self._ws = await self._connect_ws()
        await self._send(
            {
                "type": "session.update",
                "session": {
                    "voice": self.voice,
                    "instructions": self.instructions,
                    "turn_detection": {"type": "server_vad"},
                    "audio": {
                        "input": {"format": {"type": "audio/pcm", "rate": 24000}},
                        "output": {"format": {"type": "audio/pcm", "rate": 24000}},
                    },
                },
            }
        )
        self.events.append({"type": "session.connected", "model": self.model})

    async def close(self) -> None:
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        self.events.append({"type": "session.closed"})

    async def update_instructions(self, instructions: str) -> None:
        self.instructions = instructions
        if self._ws is None:
            return
        await self._send(
            {
                "type": "session.update",
                "session": {"instructions": instructions, "voice": self.voice},
            }
        )

    async def speak_text(self, text: str) -> Dict[str, Any]:
        """Send a text turn and collect response events until response.done."""
        if self._ws is None:
            await self.connect()
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )
        await self._send({"type": "response.create"})
        collected: List[Dict[str, Any]] = []
        transcript_parts: List[str] = []
        audio_chunks = 0
        assert self._ws is not None
        async for raw in self._ws:
            event = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
            if isinstance(event, bytes):
                event = json.loads(event.decode("utf-8"))
            collected.append(event)
            et = event.get("type", "")
            if et in ("response.output_audio.delta", "response.audio.delta"):
                audio_chunks += 1
            if et in (
                "response.output_audio_transcript.delta",
                "response.audio_transcript.delta",
            ):
                transcript_parts.append(str(event.get("delta") or ""))
            if et in ("response.done", "response.completed", "error"):
                break
        result = {
            "type": "response.done",
            "backend": self.backend_name,
            "voice": self.voice,
            "text": "".join(transcript_parts) or text,
            "audio_chunks": audio_chunks,
            "events": collected,
        }
        self.events.append({"type": "speak_text", "input": text, "result_type": result["type"]})
        return result

    async def _send(self, payload: Dict[str, Any]) -> None:
        assert self._ws is not None
        await self._ws.send(json.dumps(payload))


def build_voice_agent(
    *,
    use_xai: bool = False,
    instructions: str = "",
    api_key: Optional[str] = None,
) -> VoiceAgent:
    """Factory: live xAI when requested + key present, else offline mock."""
    key = (api_key if api_key is not None else os.environ.get("XAI_API_KEY", "")).strip()
    instr = instructions or "You are Theodore, a helpful AI teacher."
    if use_xai and key:
        return XaiVoiceAgent(
            api_key=key,
            model=os.environ.get("XAI_VOICE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            voice=os.environ.get("XAI_VOICE_ID", DEFAULT_VOICE).strip() or DEFAULT_VOICE,
            instructions=instr,
        )
    return OfflineVoiceAgent(instructions=instr)
