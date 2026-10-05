"""xAI Grok Voice Agent client (Speech-to-Speech realtime WebSocket).

Powers natural conversational voice for Theodore (AI host) and self-teach
coaching in the webcam lab. Uses the xAI Realtime API:

  wss://api.x.ai/v1/realtime?model=grok-voice-latest

Ephemeral client secrets (POST /v1/realtime/client_secrets) keep the API key
off browsers/mobile. When ``XAI_API_KEY`` is unset the helpers degrade to an
offline mock so local tests and demos keep working.

Pure stdlib ``urllib`` for HTTP (mirrors elevenlabs_tts); WebSocket connect is
optional and only used by the live bridge helper.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

API_BASE = "https://api.x.ai/v1"
REALTIME_WS = "wss://api.x.ai/v1/realtime"
DEFAULT_MODEL = "grok-voice-latest"
DEFAULT_VOICE = "eve"
CLIENT_SECRETS_PATH = "/realtime/client_secrets"

# Teaching personas for Salareen webcam lab sessions.
PERSONA_THEODORE = "theodore"
PERSONA_SELF_TEACH = "self_teach"
PERSONA_GROUP_HOST = "group_host"

_PERSONA_INSTRUCTIONS: Dict[str, str] = {
    PERSONA_THEODORE: (
        "You are Theodore, the Salareen AI host and tutor. Teach clearly, "
        "warmly, and Socratically. Keep answers grounded in the lesson slides "
        "when provided. If the learner appears distracted or briefly leaves, "
        "gently re-engage them without shaming. Prefer short spoken turns "
        "(1-3 sentences) then invite a question."
    ),
    PERSONA_SELF_TEACH: (
        "You are a Salareen self-teaching coach. The learner is teaching "
        "themselves the material; you help them explain concepts out loud, "
        "quiz their understanding, and correct misconceptions. Encourage them "
        "to lead; only intervene with hints when they stall. Keep turns short "
        "and conversational."
    ),
    PERSONA_GROUP_HOST: (
        "You are Theodore, hosting a small group live class on Salareen. "
        "Address the room collectively, call on individuals by first name when "
        "given, manage turn-taking for Q&A, and keep the class moving. If a "
        "learner goes absent (webcam empty), pause briefly and welcome them "
        "back when they return."
    ),
}


class XaiVoiceError(RuntimeError):
    """Raised when an xAI Voice API call fails."""


def xai_configured(api_key: Optional[str] = None) -> bool:
    key = api_key if api_key is not None else os.environ.get("XAI_API_KEY", "")
    return bool((key or "").strip())


def _api_key(explicit: Optional[str] = None) -> str:
    key = (explicit if explicit is not None else os.environ.get("XAI_API_KEY", "")).strip()
    return key


def _http_post(
    url: str,
    *,
    data: bytes,
    headers: Dict[str, str],
    timeout: float,
) -> bytes:
    """POST ``data`` and return the raw response body. Isolated for testing."""
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise XaiVoiceError(f"xAI HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise XaiVoiceError(f"xAI network error: {exc}") from exc


@dataclass
class EphemeralToken:
    """Short-lived client secret for browser/mobile realtime WebSocket auth."""

    value: str
    expires_at: int  # unix seconds
    mock: bool = False
    model: str = DEFAULT_MODEL

    @property
    def websocket_protocol(self) -> str:
        """Value for the browser ``sec-websocket-protocol`` header list."""
        return f"xai-client-secret.{self.value}"

    @property
    def websocket_url(self) -> str:
        return f"{REALTIME_WS}?model={self.model}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "expires_at": self.expires_at,
            "mock": self.mock,
            "model": self.model,
            "websocket_url": self.websocket_url,
            "websocket_protocol": self.websocket_protocol,
        }


@dataclass
class VoiceSessionConfig:
    """session.update payload for Theodore / self-teach / group host."""

    persona: str = PERSONA_THEODORE
    voice: str = DEFAULT_VOICE
    model: str = DEFAULT_MODEL
    instructions: str = ""
    lesson_context: str = ""
    learner_names: List[str] = field(default_factory=list)
    silence_duration_ms: int = 700
    idle_timeout_ms: Optional[int] = 20000
    tools: List[Dict[str, Any]] = field(default_factory=list)

    def resolved_instructions(self) -> str:
        base = (self.instructions or "").strip() or _PERSONA_INSTRUCTIONS.get(
            self.persona, _PERSONA_INSTRUCTIONS[PERSONA_THEODORE]
        )
        parts = [base]
        if self.lesson_context.strip():
            parts.append(f"Lesson context:\n{self.lesson_context.strip()}")
        if self.learner_names:
            names = ", ".join(n.strip() for n in self.learner_names if n.strip())
            if names:
                parts.append(f"Learners in this session: {names}.")
        return "\n\n".join(parts)

    def session_update_event(self) -> Dict[str, Any]:
        turn: Dict[str, Any] = {
            "type": "server_vad",
            "silence_duration_ms": int(self.silence_duration_ms),
        }
        if self.idle_timeout_ms is not None:
            turn["idle_timeout_ms"] = int(self.idle_timeout_ms)
        session: Dict[str, Any] = {
            "voice": self.voice,
            "instructions": self.resolved_instructions(),
            "turn_detection": turn,
            "audio": {
                "input": {"format": {"type": "audio/pcm", "rate": 24000}},
                "output": {"format": {"type": "audio/pcm", "rate": 24000}},
            },
        }
        if self.tools:
            session["tools"] = list(self.tools)
        return {"type": "session.update", "session": session}


def mint_ephemeral_token(
    *,
    api_key: Optional[str] = None,
    expires_seconds: int = 300,
    model: str = DEFAULT_MODEL,
    timeout: float = 15.0,
    allow_mock: bool = True,
    session: Optional[Dict[str, Any]] = None,
) -> EphemeralToken:
    """Mint a short-lived client secret for the realtime Voice API.

    When no API key is configured and ``allow_mock`` is True, returns a mock
    token so lab UIs can exercise the handshake offline.
    """
    key = _api_key(api_key)
    expires_seconds = max(30, min(3600, int(expires_seconds)))
    if not key:
        if not allow_mock:
            raise XaiVoiceError("XAI_API_KEY is not configured")
        return EphemeralToken(
            value=f"mock-{uuid.uuid4().hex}",
            expires_at=int(time.time()) + expires_seconds,
            mock=True,
            model=model,
        )

    url = f"{API_BASE}{CLIENT_SECRETS_PATH}"
    request_payload: Dict[str, Any] = {
        "expires_after": {"seconds": expires_seconds}
    }
    if session:
        # Bind browser credentials to the server-selected persona, model,
        # audio formats, VAD and tool policy. A token that only carries an
        # expiry lets a modified browser replace all of those settings.
        request_payload["session"] = dict(session)
    payload = json.dumps(request_payload).encode("utf-8")
    raw = _http_post(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=timeout,
    )
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        # Never embed the response body — a malformed reply could carry the
        # minted token into logs.
        raise XaiVoiceError("invalid JSON from xAI client_secrets") from exc
    if not isinstance(data, dict):
        raise XaiVoiceError("client_secrets response was not an object")
    raw_value = data.get("value") or data.get("client_secret") or ""
    value = raw_value.strip() if isinstance(raw_value, str) else ""
    if not value:
        raise XaiVoiceError("client_secrets response missing value")
    expires_at = int(data.get("expires_at") or (time.time() + expires_seconds))
    return EphemeralToken(value=value, expires_at=expires_at, mock=False, model=model)


def build_voice_session(
    mode: str,
    *,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    lesson_context: str = "",
    learner_names: Optional[Sequence[str]] = None,
    instructions: str = "",
) -> VoiceSessionConfig:
    """Map webcam-lab teaching mode -> VoiceSessionConfig."""
    mode_key = (mode or PERSONA_THEODORE).strip().lower()
    persona_map = {
        "solo": PERSONA_THEODORE,
        "theodore": PERSONA_THEODORE,
        "theodore_solo": PERSONA_THEODORE,
        "group": PERSONA_GROUP_HOST,
        "theodore_group": PERSONA_GROUP_HOST,
        "group_host": PERSONA_GROUP_HOST,
        "self": PERSONA_SELF_TEACH,
        "self_teach": PERSONA_SELF_TEACH,
        "self-teach": PERSONA_SELF_TEACH,
    }
    persona = persona_map.get(mode_key, PERSONA_THEODORE)
    return VoiceSessionConfig(
        persona=persona,
        voice=voice or DEFAULT_VOICE,
        model=model or DEFAULT_MODEL,
        instructions=instructions,
        lesson_context=lesson_context or "",
        learner_names=list(learner_names or []),
    )


def presence_tool_schema() -> Dict[str, Any]:
    """Optional function tool so Grok can query webcam presence mid-lesson."""
    return {
        "type": "function",
        "name": "get_learner_presence",
        "description": (
            "Return the latest webcam presence for a learner: live, "
            "silhouette_only (body visible but face turned away), absent, or unknown."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "participant_id": {
                    "type": "string",
                    "description": "Learner participant id in the lab session.",
                }
            },
            "required": ["participant_id"],
        },
    }
