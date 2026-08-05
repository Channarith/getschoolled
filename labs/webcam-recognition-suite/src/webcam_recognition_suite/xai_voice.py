"""xAI Grok Voice Agent client for Theodore natural speech.

Uses the Speech-to-Speech realtime WebSocket API:
  wss://api.x.ai/v1/realtime?model=grok-voice-latest

Offline tests use :class:`MockXaiVoiceAgent` (no network, no API key).
Live connections require ``XAI_API_KEY`` (server-side only).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence


DEFAULT_WS_URL = "wss://api.x.ai/v1/realtime"
DEFAULT_MODEL = "grok-voice-latest"
DEFAULT_VOICE = "eve"


@dataclass
class XaiVoiceConfig:
    api_key: str = ""
    model: str = DEFAULT_MODEL
    voice: str = DEFAULT_VOICE
    ws_url: str = DEFAULT_WS_URL
    instructions: str = (
        "You are Theodore, the Salareen AI teaching host. Speak clearly, "
        "warmly, and briefly. Encourage questions. If the learner is absent "
        "from camera, pause kindly and invite them back."
    )
    turn_detection: Optional[dict] = field(
        default_factory=lambda: {"type": "server_vad"}
    )

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "XaiVoiceConfig":
        e = env if env is not None else os.environ

        def _get(key: str, default: str = "") -> str:
            raw = e.get(key, default) if hasattr(e, "get") else default
            return (raw or default).strip() if isinstance(raw, str) else default

        instructions = _get("XAI_VOICE_INSTRUCTIONS", "")
        return cls(
            api_key=_get("XAI_API_KEY", ""),
            model=_get("XAI_VOICE_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL,
            voice=_get("XAI_VOICE_NAME", DEFAULT_VOICE) or DEFAULT_VOICE,
            ws_url=_get("XAI_VOICE_WS_URL", DEFAULT_WS_URL) or DEFAULT_WS_URL,
            instructions=instructions or cls().instructions,
        )

    @property
    def realtime_url(self) -> str:
        base = (self.ws_url or DEFAULT_WS_URL).rstrip("/")
        model = self.model or DEFAULT_MODEL
        sep = "&" if "?" in base else "?"
        if "model=" in base:
            return base
        return f"{base}{sep}model={model}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["api_key"] = "***" if self.api_key else ""
        return d


def build_session_update(config: XaiVoiceConfig, *, tools: Optional[list] = None) -> dict:
    """Build the ``session.update`` client event for Grok Voice Agent."""
    session: Dict[str, Any] = {
        "voice": config.voice or DEFAULT_VOICE,
        "instructions": config.instructions,
        "turn_detection": config.turn_detection,
    }
    if tools:
        session["tools"] = list(tools)
    return {"type": "session.update", "session": session}


def build_text_turn(text: str) -> List[dict]:
    """Client events to speak/respond to a text prompt (manual turn)."""
    return [
        {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        },
        {"type": "response.create"},
    ]


def build_theodore_tools() -> list:
    """Function tools Theodore can call during a live class voice session."""
    return [
        {
            "type": "function",
            "name": "report_presence_hold",
            "description": "Pause the class because a learner is absent from camera.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seat_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["seat_id"],
            },
        },
        {
            "type": "function",
            "name": "advance_slide",
            "description": "Advance to the next lesson slide when the learner is ready.",
            "parameters": {
                "type": "object",
                "properties": {"confirm": {"type": "boolean"}},
                "required": ["confirm"],
            },
        },
    ]


@dataclass
class XaiVoiceSession:
    """Buffer of client/server voice-agent events (live or mock)."""

    config: XaiVoiceConfig
    events_sent: List[dict] = field(default_factory=list)
    events_received: List[dict] = field(default_factory=list)
    connected: bool = False
    mode: str = "mock"  # mock | live

    def connect_mock(self) -> None:
        self.mode = "mock"
        self.connected = True
        update = build_session_update(self.config, tools=build_theodore_tools())
        self.events_sent.append(update)
        self.events_received.append(
            {
                "type": "session.updated",
                "session": update["session"],
            }
        )

    def say_as_theodore(self, line: str) -> List[dict]:
        """Queue a teaching line as a user prompt so the voice agent replies."""
        if not self.connected:
            raise RuntimeError("voice session not connected")
        prompts = build_text_turn(
            f"[Theodore teaching cue] Speak this to the class naturally:\n{line}"
        )
        self.events_sent.extend(prompts)
        if self.mode == "mock":
            reply = {
                "type": "response.output_text.delta",
                "delta": line,
            }
            done = {"type": "response.done", "status": "completed"}
            self.events_received.extend([reply, done])
            return [reply, done]
        return []

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "connected": self.connected,
            "config": self.config.to_dict(),
            "events_sent": self.events_sent,
            "events_received": self.events_received,
        }


class MockXaiVoiceAgent:
    """Deterministic offline stand-in for the Grok Voice Agent WebSocket."""

    def __init__(self, config: Optional[XaiVoiceConfig] = None) -> None:
        self.config = config or XaiVoiceConfig(api_key="")
        self.session = XaiVoiceSession(config=self.config)

    def connect(self) -> XaiVoiceSession:
        self.session.connect_mock()
        return self.session

    def speak(self, line: str) -> str:
        self.session.say_as_theodore(line)
        return line

    @property
    def available(self) -> bool:
        return True


def try_live_session(config: Optional[XaiVoiceConfig] = None) -> XaiVoiceSession:
    """Open a live WebSocket session when ``XAI_API_KEY`` is set.

    Raises ``RuntimeError`` when the key is missing or ``websockets`` is not
    installed. Callers should fall back to :class:`MockXaiVoiceAgent`.
    """
    cfg = config or XaiVoiceConfig.from_env()
    if not (cfg.api_key or "").strip():
        raise RuntimeError("XAI_API_KEY is not set")
    try:
        import websockets  # type: ignore  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("websockets package required for live xAI voice") from exc

    # Live connect is intentionally synchronous-setup only here; the async
    # pump lives in agent-runtime / speech_gw when promoted. For the lab we
    # record the intended handshake events so demos can print them.
    session = XaiVoiceSession(config=cfg, mode="live")
    session.connected = True
    update = build_session_update(cfg, tools=build_theodore_tools())
    session.events_sent.append(update)
    session.events_sent.append(
        {
            "type": "lab.note",
            "text": (
                f"Live handshake prepared for {cfg.realtime_url}. "
                "Use websockets.connect with Authorization Bearer XAI_API_KEY."
            ),
        }
    )
    return session


Transport = Callable[[Sequence[dict]], List[dict]]
