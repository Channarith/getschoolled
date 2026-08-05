"""xAI Grok realtime voice agent client (natural spoken communication).

Theodore's voice: instead of a one-shot TTS render per line, a realtime
speech-to-speech agent holds a natural conversation — it hears the learner,
responds with sub-second latency, and stays in persona.

Wire protocol (OpenAI Realtime-compatible, per https://docs.x.ai):

- Server-side: ``wss://{host}/v1/realtime?model=<model>`` with
  ``Authorization: Bearer $XAI_API_KEY``. Configure with ``session.update``
  (voice, instructions, ``turn_detection`` server VAD), send text turns with
  ``conversation.item.create`` + ``response.create``.
- Browser/mobile: the server mints an ephemeral token via
  ``POST {base}/v1/realtime/client_secrets`` and the client connects with the
  ``xai-client-secret.<token>`` websocket subprotocol, so the API key never
  ships to a device.

Offline-first per platform convention: with no ``XAI_API_KEY`` the client
reports ``configured() == False`` and callers fall back to the existing speech
chain (ElevenLabs -> edge-tts -> on-device) and the Nemotron/local LLM tutor.
HTTP is stdlib ``urllib`` isolated in ``_http_post`` so tests mock one method;
the websocket import is lazy so the package never hard-requires ``websockets``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

DEFAULT_BASE_URL = "https://api.x.ai/v1"
DEFAULT_REALTIME_URL = "wss://api.x.ai/v1/realtime"
DEFAULT_VOICE_MODEL = "grok-voice-latest"
DEFAULT_TEXT_MODEL = "grok-3-latest"
DEFAULT_VOICE = "eve"
DEFAULT_EPHEMERAL_TTL_S = 300

# Theodore's persona for the voice agent. Kept aligned with the live-room
# welcome (aoep_shared.live_room.PRE_CLASS_WELCOME): transparent about being
# an AI teacher, encouraging questions.
THEODORE_VOICE_INSTRUCTIONS = (
    "You are Theodore, an AI teacher hosting a live class on the Salareen "
    "learning platform. Be warm, concise, and encouraging. Be transparent that "
    "you are an AI teacher, not a human. Explain concepts step by step, check "
    "understanding often, and welcome questions and corrections. Keep spoken "
    "replies short and natural — one to three sentences unless the learner "
    "asks for a deep dive."
)

SELF_TEACHING_VOICE_INSTRUCTIONS = (
    "You are a friendly study companion on the Salareen learning platform. "
    "The learner is studying on their own; answer questions, quiz them on "
    "request, and offer brief recaps when they return from a break. Keep "
    "spoken replies short and natural."
)


class XAIVoiceError(RuntimeError):
    """Raised when an xAI voice-agent call fails."""


@dataclass
class VoiceAgentConfig:
    """Connection + persona settings for one voice agent."""

    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    realtime_url: str = DEFAULT_REALTIME_URL
    voice_model: str = DEFAULT_VOICE_MODEL
    text_model: str = DEFAULT_TEXT_MODEL
    voice: str = DEFAULT_VOICE
    instructions: str = THEODORE_VOICE_INSTRUCTIONS
    turn_detection: Optional[Dict[str, Any]] = field(
        default_factory=lambda: {"type": "server_vad", "silence_duration_ms": 600}
    )

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "VoiceAgentConfig":
        source: Mapping[str, str] = os.environ if env is None else env

        def get(key: str, default: str) -> str:
            value = source.get(key)
            return value.strip() if value and value.strip() else default

        return cls(
            api_key=get("XAI_API_KEY", ""),
            base_url=get("XAI_BASE_URL", DEFAULT_BASE_URL),
            realtime_url=get("XAI_REALTIME_URL", DEFAULT_REALTIME_URL),
            voice_model=get("XAI_VOICE_MODEL", DEFAULT_VOICE_MODEL),
            text_model=get("XAI_TEXT_MODEL", DEFAULT_TEXT_MODEL),
            voice=get("XAI_VOICE", DEFAULT_VOICE),
        )

    @classmethod
    def from_app_config(cls, config: Any) -> "VoiceAgentConfig":
        """Build from the platform ``AppConfig`` (aoep_shared.config)."""
        return cls(
            api_key=(getattr(config, "xai_api_key", "") or "").strip(),
            base_url=getattr(config, "xai_base_url", "") or DEFAULT_BASE_URL,
            realtime_url=getattr(config, "xai_realtime_url", "") or DEFAULT_REALTIME_URL,
            voice_model=getattr(config, "xai_voice_model", "") or DEFAULT_VOICE_MODEL,
            text_model=getattr(config, "xai_text_model", "") or DEFAULT_TEXT_MODEL,
            voice=getattr(config, "xai_voice", "") or DEFAULT_VOICE,
        )

    def configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class EphemeralToken:
    """Short-lived client credential for browser/mobile websocket auth."""

    value: str
    expires_at: Optional[float] = None

    @property
    def subprotocol(self) -> str:
        """The websocket subprotocol a browser/mobile client connects with."""
        return f"xai-client-secret.{self.value}"


class XAIVoiceAgent:
    """Realtime voice agent session against the xAI Grok Voice API."""

    def __init__(self, config: Optional[VoiceAgentConfig] = None) -> None:
        self.config = config or VoiceAgentConfig.from_env()
        self._timeout = 30.0

    # --- introspection ----------------------------------------------------- #
    def configured(self) -> bool:
        """True when an API key is present; False => caller uses fallback chain."""
        return self.config.configured()

    def realtime_url(self) -> str:
        base = self.config.realtime_url.rstrip("/")
        return f"{base}?model={self.config.voice_model}"

    # --- payload builders (pure; unit-tested without network) -------------- #
    def session_update_payload(
        self,
        *,
        instructions: Optional[str] = None,
        voice: Optional[str] = None,
        tools: Optional[List[dict]] = None,
    ) -> dict:
        session: Dict[str, Any] = {
            "voice": voice or self.config.voice,
            "instructions": instructions or self.config.instructions,
            "turn_detection": self.config.turn_detection,
        }
        if tools:
            session["tools"] = tools
        return {"type": "session.update", "session": session}

    @staticmethod
    def text_turn_payload(text: str) -> List[dict]:
        """The two events that inject a text turn and ask for a response."""
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

    # --- ephemeral tokens (browser/mobile onboarding) ---------------------- #
    def mint_ephemeral_token(
        self, *, expires_s: int = DEFAULT_EPHEMERAL_TTL_S
    ) -> EphemeralToken:
        """Mint a short-lived token so clients never see the API key."""
        if not self.configured():
            raise XAIVoiceError(
                "XAI_API_KEY is not configured; cannot mint ephemeral tokens"
            )
        payload = {"expires_after": {"seconds": int(expires_s)}}
        raw = self._http_post(
            f"{self.config.base_url.rstrip('/')}/realtime/client_secrets", payload
        )
        # xAI follows the OpenAI Realtime shape; accept the token at the top
        # level or nested under client_secret for forward compatibility.
        value = raw.get("value") or (raw.get("client_secret") or {}).get("value") or ""
        if not value:
            raise XAIVoiceError("xAI client_secrets response carried no token")
        expires_at = raw.get("expires_at") or (
            raw.get("client_secret") or {}
        ).get("expires_at")
        return EphemeralToken(
            value=value, expires_at=float(expires_at) if expires_at else None
        )

    # --- text fallback (chat completions; also the testable path) ---------- #
    def respond(
        self,
        messages: Iterable[Dict[str, str]],
        *,
        max_tokens: int = 256,
    ) -> str:
        """Text-in/text-out reply via xAI's OpenAI-compatible chat endpoint.

        Used when a full duplex audio session is unnecessary (e.g. rendering a
        single line through the platform TTS chain) and by tests to verify the
        integration without a websocket.
        """
        if not self.configured():
            raise XAIVoiceError(
                "XAI_API_KEY is not configured; use the platform TTS/LLM fallback"
            )
        payload = {
            "model": self.config.text_model,
            "messages": list(messages),
            "max_tokens": max_tokens,
            "stream": False,
        }
        raw = self._http_post(
            f"{self.config.base_url.rstrip('/')}/chat/completions", payload
        )
        try:
            return (raw["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise XAIVoiceError("xAI chat response had no message content") from exc

    # --- realtime websocket (server-side duplex audio) --------------------- #
    async def connect(self, *, instructions: Optional[str] = None):
        """Open a realtime session; returns a connected websocket.

        The caller then sends ``session_update_payload()`` and streams audio /
        text turns. ``websockets`` is imported lazily and the key is required,
        so this raises ``NotImplementedError``/``XAIVoiceError`` instead of
        failing obscurely when the offline environment can't host a session.
        """
        if not self.configured():
            raise NotImplementedError(
                "XAI_API_KEY is not configured; realtime voice is unavailable. "
                "Fall back to the platform speech chain (ElevenLabs/edge-tts)."
            )
        try:
            import websockets  # lazy: optional [voice] extra
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise NotImplementedError(
                "The 'websockets' package is required for realtime voice; "
                "install aoep-webcam-vision[voice]."
            ) from exc
        ws = await websockets.connect(
            self.realtime_url(),
            additional_headers={
                "Authorization": f"Bearer {self.config.api_key}"
            },
        )
        await ws.send(json.dumps(self.session_update_payload(instructions=instructions)))
        return ws

    # --- transport (isolated for tests) ------------------------------------ #
    def _http_post(self, url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=self._timeout)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            raise XAIVoiceError(f"xAI HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise XAIVoiceError(f"xAI unreachable: {exc.reason}") from exc
        return json.loads(resp.read().decode("utf-8"))


def voice_agent_from_app_config(config: Any) -> XAIVoiceAgent:
    """Build an agent from the platform AppConfig (factory-friendly helper)."""
    return XAIVoiceAgent(VoiceAgentConfig.from_app_config(config))
