"""xAI (Grok) voice agent for natural classroom communication.

The agent speaks as the platform's AI teacher (default persona "Theodore"). It
calls xAI's OpenAI-compatible chat-completions endpoint (``https://api.x.ai/v1``)
when ``XAI_API_KEY`` is configured, and otherwise falls back to a deterministic,
context-grounded reply so the teaching loop always responds -- offline, in CI, or
when the network is restricted (the platform's offline-first convention).

The HTTP call is isolated in :meth:`_transport` (stdlib urllib) so tests mock it
without a running endpoint. Both blocking :meth:`respond` and streaming
:meth:`respond_stream` (SSE ``data:`` deltas) are supported so text-to-speech can
start on the first tokens for low-latency voice.

"Voice" here means natural spoken language: the agent produces the words; a TTS
layer (ElevenLabs / edge-tts / on-device, already in the platform) renders audio.
:meth:`respond` returns a :class:`VoiceReply` carrying the text plus a ``ssml``
hint and the voice/persona so the caller can hand it straight to TTS.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional

from .config import LabConfig


@dataclass
class AgentTurn:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class VoiceReply:
    text: str
    persona: str
    model: str
    source: str  # "xai" | "fallback"
    ssml: str = ""
    voice: str = "warm-teacher"

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "persona": self.persona,
            "model": self.model,
            "source": self.source,
            "ssml": self.ssml,
            "voice": self.voice,
        }


@dataclass
class ClassroomContext:
    """Structured context handed to the agent so replies stay grounded."""

    class_mode: str = "solo"       # solo | group
    teaching_mode: str = "theodore"  # theodore | self
    event: str = ""                # arrived | left | returned | attention_low | ...
    learner_name: str = ""
    topic: str = ""
    headcount: int = 0
    away_seconds: float = 0.0
    extra: dict = field(default_factory=dict)


class XAIVoiceAgent:
    """Conversational agent backed by xAI Grok (OpenAI-compatible)."""

    def __init__(self, config: Optional[LabConfig] = None) -> None:
        from .config import load_lab_config

        self._config = config or load_lab_config()
        self._base_url = (self._config.xai_base_url or "").rstrip("/")
        self._model = self._config.xai_model
        self._api_key = (self._config.xai_api_key or "").strip()
        self._timeout = self._config.xai_timeout_s
        self.persona = self._config.agent_name

    # --- public API -------------------------------------------------------- #
    @property
    def configured(self) -> bool:
        """True when a real xAI call will be attempted (key + base URL set)."""
        return bool(self._api_key and self._base_url)

    def system_prompt(self, ctx: ClassroomContext) -> str:
        role = (
            "You are leading the lesson"
            if ctx.teaching_mode == "theodore"
            else "You are a supportive tutor helping a self-directed learner"
        )
        room = (
            "a one-on-one class" if ctx.class_mode == "solo" else "a group class"
        )
        return (
            f"You are {self.persona}, a warm, encouraging AI teacher in {room}. "
            f"{role}. Speak naturally and briefly (1-2 short sentences), like a "
            "kind human teacher talking out loud. Never mention cameras, "
            "detection, or that you are an AI model. Be specific and human."
        )

    def respond(
        self,
        ctx: ClassroomContext,
        *,
        user_message: str = "",
        history: Optional[List[AgentTurn]] = None,
        temperature: float = 0.6,
        max_tokens: int = 160,
    ) -> VoiceReply:
        messages = self._build_messages(ctx, user_message, history)
        if self.configured:
            try:
                raw = self._transport(
                    self._payload(messages, temperature, max_tokens, stream=False),
                    stream=False,
                )
                text = _extract_message(raw)
                if text:
                    return self._reply(text, source="xai")
            except _XAIError:
                # Fall through to the deterministic reply -- never break the loop.
                pass
        return self._reply(self._fallback(ctx, user_message), source="fallback")

    def respond_stream(
        self,
        ctx: ClassroomContext,
        *,
        user_message: str = "",
        history: Optional[List[AgentTurn]] = None,
        temperature: float = 0.6,
        max_tokens: int = 160,
    ) -> Iterable[str]:
        """Yield reply text incrementally (for low-latency TTS)."""
        messages = self._build_messages(ctx, user_message, history)
        if self.configured:
            try:
                got = False
                for line in self._transport(
                    self._payload(messages, temperature, max_tokens, stream=True),
                    stream=True,
                ):
                    delta = _extract_delta(line)
                    if delta:
                        got = True
                        yield delta
                if got:
                    return
            except _XAIError:
                pass
        yield self._fallback(ctx, user_message)

    # --- message + payload construction ------------------------------------ #
    def _build_messages(
        self,
        ctx: ClassroomContext,
        user_message: str,
        history: Optional[List[AgentTurn]],
    ) -> List[AgentTurn]:
        messages: List[AgentTurn] = [AgentTurn("system", self.system_prompt(ctx))]
        messages.append(AgentTurn("user", _context_brief(ctx, user_message)))
        if history:
            messages = [messages[0], *history, messages[1]]
        return messages

    def _payload(self, messages, temperature, max_tokens, *, stream):
        return {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    def _reply(self, text: str, *, source: str) -> VoiceReply:
        clean = " ".join(text.split()).strip()
        return VoiceReply(
            text=clean,
            persona=self.persona,
            model=self._model,
            source=source,
            ssml=f"<speak>{clean}</speak>",
        )

    # --- deterministic fallback (offline-safe, always available) ----------- #
    def _fallback(self, ctx: ClassroomContext, user_message: str) -> str:
        name = ctx.learner_name.strip()
        who = f" {name}" if name else ""
        if user_message.strip():
            return (
                f"Great question{who}. Let's work through it together, one step "
                "at a time."
            )
        event = ctx.event
        if event == "arrived":
            return f"Welcome{who}! Wonderful to see you. Let's get started."
        if event == "left":
            secs = int(ctx.away_seconds)
            tail = f" (about {secs}s)" if secs else ""
            if ctx.class_mode == "group":
                return (
                    "Looks like someone stepped away from the group -- I'll pause "
                    f"the key point{tail} so no one misses it."
                )
            return (
                f"I'll pause here{tail} -- take your time, and I'll be right here "
                "when you're back."
            )
        if event == "returned":
            return (
                f"Welcome back{who}! Here's a quick recap, then we'll pick up "
                "right where we left off."
            )
        if event == "attention_low":
            return (
                f"Let's make this stick{who} -- can you tell me in your own words "
                "what we just covered?"
            )
        topic = ctx.topic.strip()
        if topic:
            return f"Let's keep going with {topic}{who}. You're doing well."
        return f"Let's keep going{who}. You're doing well."

    # --- transport (isolated for tests) ------------------------------------ #
    def _transport(self, payload: dict, *, stream: bool):
        if not self._base_url:
            raise _XAIError("XAI_BASE_URL is not configured")
        url = f"{self._base_url}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=self._timeout)  # noqa: S310
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            raise _XAIError(f"xAI HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise _XAIError(f"xAI unreachable: {exc.reason}") from exc
        if not stream:
            return json.loads(resp.read().decode("utf-8"))
        return _iter_sse(resp)


class _XAIError(RuntimeError):
    """Internal: any failure talking to xAI (triggers the fallback)."""


def _context_brief(ctx: ClassroomContext, user_message: str) -> str:
    parts = [
        f"class_mode={ctx.class_mode}",
        f"teaching_mode={ctx.teaching_mode}",
    ]
    if ctx.event:
        parts.append(f"event={ctx.event}")
    if ctx.learner_name:
        parts.append(f"learner={ctx.learner_name}")
    if ctx.topic:
        parts.append(f"topic={ctx.topic}")
    if ctx.class_mode == "group":
        parts.append(f"headcount={ctx.headcount}")
    if ctx.away_seconds:
        parts.append(f"away_seconds={int(ctx.away_seconds)}")
    brief = "Classroom context: " + ", ".join(parts) + "."
    if user_message.strip():
        return f"{brief}\nThe learner said: {user_message.strip()}"
    return brief + "\nSay the right thing to the class now."


def _iter_sse(resp) -> Iterator[str]:
    for raw in resp:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data:"):
            continue
        chunk = line[len("data:"):].strip()
        if chunk == "[DONE]":
            break
        yield chunk


def _extract_message(raw: dict) -> str:
    try:
        return (raw["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return ""


def _extract_delta(chunk: str) -> str:
    try:
        obj = json.loads(chunk)
        return obj["choices"][0].get("delta", {}).get("content") or ""
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return ""
