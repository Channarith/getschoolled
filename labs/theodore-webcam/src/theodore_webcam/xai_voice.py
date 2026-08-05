"""xAI Grok voice agents for Theodore.

Two surfaces, one agent:

1. Speech to speech (the real voice agent). The browser opens a WebSocket
   straight to ``wss://api.x.ai/v1/realtime`` so audio never round-trips
   through us, which is what keeps turn-taking sub-second. The API key stays
   server-side: this module mints a short-lived ephemeral client secret
   (``POST /v1/realtime/client_secrets``) and hands the browser the exact
   ``session.update`` payload to send on open, including the classroom tools
   Grok may call.

2. Text turns (``POST /v1/chat/completions``), used for typed questions and
   for the presence-driven lines Theodore speaks when a learner returns.

With no ``XAI_API_KEY`` the agent degrades to a deterministic reply grounded in
the learner's presence state, so the lab is fully demonstrable offline and the
teaching loop never hard-depends on a key.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import XaiConfig

Transport = Callable[[str, str, Dict[str, str], Optional[bytes], float], Tuple[int, bytes]]


class XaiUnavailable(RuntimeError):
    """Raised when the xAI API is not configured or not reachable."""


CLASSROOM_TOOLS: List[dict] = [
    {
        "type": "function",
        "name": "get_presence_state",
        "description": (
            "Check whether the learner is currently visible on their webcam, "
            "how long they have been away, and whether the lesson is paused. "
            "Call this before assuming someone is listening."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "participant_id": {
                    "type": "string",
                    "description": "Participant to check; omit for the current learner.",
                }
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "pause_lesson",
        "description": "Pause the lesson and bookmark the current checkpoint.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why the lesson is pausing."}
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "resume_lesson",
        "description": "Resume the lesson from the bookmarked checkpoint.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "type": "function",
        "name": "recap_checkpoint",
        "description": (
            "Summarise what the learner missed while they were away, then "
            "continue teaching from the checkpoint."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "seconds_missed": {
                    "type": "number",
                    "description": "How long the learner was away, in seconds.",
                }
            },
            "required": [],
        },
    },
]


def _default_transport(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[bytes],
    timeout: float,
) -> Tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise XaiUnavailable(f"xAI request failed: {exc.reason}") from exc


@dataclass
class VoiceSession:
    """Everything a browser needs to open a Grok voice session."""

    url: str
    model: str
    voice: str
    session_update: dict
    token: str = ""
    expires_at: int = 0
    subprotocol: str = ""
    ephemeral: bool = False

    def as_dict(self, *, include_token: bool = True) -> dict:
        data = {
            "url": self.url,
            "model": self.model,
            "voice": self.voice,
            "session_update": self.session_update,
            "expires_at": self.expires_at,
            "ephemeral": self.ephemeral,
        }
        if include_token:
            data["token"] = self.token
            data["subprotocol"] = self.subprotocol
        return data


@dataclass
class VoiceReply:
    text: str
    model: str
    source: str
    voice: str

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "model": self.model,
            "source": self.source,
            "voice": self.voice,
        }


BASE_PERSONA = (
    "You are Theodore, the AI teacher on the Salareen learning platform. "
    "You speak out loud, so keep replies to one or two short spoken sentences, "
    "warm and plain-spoken, never bulleted and never marked up. "
    "A webcam silhouette sensor tells you whether the learner is physically at "
    "their desk. Never lecture an empty chair: if presence says the learner is "
    "away, stop talking and wait. When they come back, greet them briefly, say "
    "what they missed, and carry on from the checkpoint."
)


class XaiVoiceAgent:
    """Client for the xAI Grok Voice Agent API, with an offline fallback."""

    def __init__(
        self,
        config: Optional[XaiConfig] = None,
        *,
        transport: Optional[Transport] = None,
    ) -> None:
        self.config = config or XaiConfig()
        self._transport = transport or _default_transport

    @property
    def configured(self) -> bool:
        return self.config.configured

    # -- prompt / session ---------------------------------------------

    def instructions(self, context: Optional[dict] = None) -> str:
        context = context or {}
        lines = [BASE_PERSONA]
        mode = context.get("mode")
        if mode == "group":
            lines.append(
                "This is a group class. If one learner steps away, keep teaching "
                "the room and catch that person up privately when they return. "
                "Only hold the whole class if attendance drops below quorum."
            )
        elif mode == "solo":
            lines.append(
                "This is a solo self-teaching session with one learner. If they "
                "step away, pause and hold their place rather than talking on."
            )
        lesson = context.get("lesson_title")
        if lesson:
            lines.append(f"Current lesson: {lesson}.")
        checkpoint = context.get("checkpoint")
        if checkpoint:
            lines.append(f"Current checkpoint: {checkpoint}.")
        presence = context.get("presence")
        if presence:
            lines.append(f"Live presence signal: {presence}.")
        return " ".join(lines)

    def tools(self) -> List[dict]:
        tools = list(CLASSROOM_TOOLS)
        if self.config.enable_web_search:
            tools.append({"type": "web_search"})
        return tools

    def session_update(self, context: Optional[dict] = None) -> dict:
        """The exact ``session.update`` event the client sends on open."""

        cfg = self.config
        return {
            "type": "session.update",
            "session": {
                "voice": cfg.voice,
                "instructions": self.instructions(context),
                "reasoning": {"effort": cfg.reasoning_effort},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": cfg.vad_threshold,
                    "silence_duration_ms": cfg.vad_silence_ms,
                    "prefix_padding_ms": cfg.vad_prefix_padding_ms,
                },
                "audio": {
                    "input": {"format": {"type": "audio/pcm", "rate": cfg.audio_rate}},
                    "output": {"format": {"type": "audio/pcm", "rate": cfg.audio_rate}},
                },
                "tools": self.tools(),
            },
        }

    def realtime_url(self) -> str:
        return f"{self.config.realtime_url}?model={self.config.voice_model}"

    def mint_client_secret(self) -> dict:
        """POST /v1/realtime/client_secrets — a short-lived browser token."""

        if not self.configured:
            raise XaiUnavailable("XAI_API_KEY is not set")
        payload = json.dumps(
            {"expires_after": {"seconds": self.config.token_ttl_seconds}}
        ).encode("utf-8")
        status, body = self._transport(
            "POST",
            f"{self.config.base_url}/realtime/client_secrets",
            {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            payload,
            self.config.request_timeout,
        )
        if status >= 400:
            raise XaiUnavailable(
                f"client_secrets failed ({status}): {body.decode('utf-8', 'replace')[:400]}"
            )
        try:
            data = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise XaiUnavailable(f"client_secrets returned non-JSON: {exc}") from exc
        if not data.get("value"):
            raise XaiUnavailable("client_secrets response had no token value")
        return data

    def start_session(self, context: Optional[dict] = None) -> VoiceSession:
        session = VoiceSession(
            url=self.realtime_url(),
            model=self.config.voice_model,
            voice=self.config.voice,
            session_update=self.session_update(context),
        )
        if not self.configured:
            return session
        secret = self.mint_client_secret()
        session.token = str(secret.get("value", ""))
        session.expires_at = int(secret.get("expires_at", 0) or 0)
        session.subprotocol = f"xai-client-secret.{session.token}"
        session.ephemeral = True
        return session

    # -- text turns ----------------------------------------------------

    def respond(
        self,
        transcript: str,
        *,
        context: Optional[dict] = None,
        history: Optional[List[dict]] = None,
    ) -> VoiceReply:
        transcript = (transcript or "").strip()
        if not self.configured:
            return VoiceReply(
                text=self._fallback_text(transcript, context),
                model="offline-fallback",
                source="fallback",
                voice=self.config.voice,
            )
        messages: List[dict] = [
            {"role": "system", "content": self.instructions(context)}
        ]
        for turn in history or []:
            role = turn.get("role")
            content = turn.get("content")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": transcript or "(no speech)"})

        payload = json.dumps(
            {
                "model": self.config.text_model,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 220,
            }
        ).encode("utf-8")
        try:
            status, body = self._transport(
                "POST",
                f"{self.config.base_url}/chat/completions",
                {
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                payload,
                self.config.request_timeout,
            )
        except XaiUnavailable:
            return VoiceReply(
                text=self._fallback_text(transcript, context),
                model="offline-fallback",
                source="fallback",
                voice=self.config.voice,
            )
        if status >= 400:
            return VoiceReply(
                text=self._fallback_text(transcript, context),
                model="offline-fallback",
                source="fallback",
                voice=self.config.voice,
            )
        try:
            data = json.loads(body.decode("utf-8"))
            text = data["choices"][0]["message"]["content"].strip()
        except (ValueError, KeyError, IndexError, TypeError, UnicodeDecodeError):
            return VoiceReply(
                text=self._fallback_text(transcript, context),
                model="offline-fallback",
                source="fallback",
                voice=self.config.voice,
            )
        return VoiceReply(
            text=text,
            model=str(data.get("model") or self.config.text_model),
            source="xai",
            voice=self.config.voice,
        )

    def _fallback_text(self, transcript: str, context: Optional[dict]) -> str:
        context = context or {}
        presence = str(context.get("presence") or "").lower()
        lesson = context.get("lesson_title") or "the lesson"
        checkpoint = context.get("checkpoint") or lesson
        if presence in {"absent", "stale", "drifting"}:
            return f"Holding your place at {checkpoint}. I'll pick up when you're back."
        if transcript:
            return (
                f"Good question. Let's take that against {checkpoint} — "
                "here's the short version, then we'll keep going."
            )
        return f"I'm with you on {lesson}. Ask me anything when you're ready."

    # -- status --------------------------------------------------------

    def status(self) -> dict:
        return {
            "configured": self.configured,
            "provider": "xai",
            "voice_model": self.config.voice_model,
            "text_model": self.config.text_model,
            "voice": self.config.voice,
            "realtime_url": self.config.realtime_url,
            "token_ttl_seconds": self.config.token_ttl_seconds,
            "tools": [t.get("name") or t.get("type") for t in self.tools()],
            "mode": "speech-to-speech" if self.configured else "offline-fallback",
            "checked_at": int(time.time()),
        }


def execute_tool(session: Any, name: str, arguments: Optional[dict] = None) -> dict:
    """Run a Grok function call against a live class session."""

    from .cues import ClassMode  # local import keeps this module import-light

    arguments = arguments or {}
    if name == "get_presence_state":
        participant_id = arguments.get("participant_id") or ""
        participants = session.participants
        if participant_id:
            participant = session.participant(participant_id)
        else:
            learners = session.learners()
            if not learners:
                return {"error": "no participants in session"}
            participant = learners[0]
        snapshot = participant.tracker.snapshot()
        return {
            "participant_id": participant.participant_id,
            "display_name": participant.display_name,
            "state": snapshot.state.value,
            "present": snapshot.present,
            "absent_seconds": round(snapshot.absent_seconds, 1),
            "lesson_paused": session.lesson_paused,
            "class_held": session.class_held,
            "roster_size": len(participants),
        }
    if name == "pause_lesson":
        session.lesson_paused = True
        return {"lesson_paused": True, "checkpoint": session.checkpoint}
    if name == "resume_lesson":
        session.lesson_paused = False
        return {"lesson_paused": False, "checkpoint": session.checkpoint}
    if name == "recap_checkpoint":
        session.lesson_paused = False
        return {
            "checkpoint": session.checkpoint or session.lesson_title,
            "seconds_missed": arguments.get("seconds_missed", 0),
            "mode": session.mode.value if isinstance(session.mode, ClassMode) else session.mode,
        }
    return {"error": f"unknown tool: {name}"}
