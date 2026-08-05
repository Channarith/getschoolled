"""xAI (Grok) voice agents for Theodore's replies and natural communication.

Two integration surfaces, both matching xAI's public API shape:

  * :class:`XaiVoiceAgent` - generates the teacher's spoken reply text via Grok
    **chat completions** (OpenAI-compatible: ``POST {base}/chat/completions`` with
    a ``Bearer`` key). Blocking (:meth:`respond`) and streaming
    (:meth:`respond_stream`, SSE ``data:`` deltas so TTS can start on the first
    tokens). The HTTP call is isolated in ``_transport`` for easy mocking.

  * :func:`build_voice_agent_session` - builds the wiring for xAI's **Realtime
    Voice Agent API** (speech-to-speech over a WebSocket:
    ``wss://api.x.ai/v1/realtime?model=grok-voice-latest``). Returns the URL,
    auth headers, and the ``session.update`` payload (voice, instructions,
    ``server_vad`` turn detection) a client opens the socket with. Pure and
    fully unit-testable - no socket is opened here.

Offline-safe: with no ``XAI_API_KEY`` set (or if the endpoint is unreachable),
:class:`XaiVoiceAgent` returns a grounded, deterministic fallback line so the
class always "speaks" without a network or key.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Sequence

from .config import WebcamLabConfig

# Personas: the same voice agent plays Theodore (an AI teacher leading a class)
# or a self-teaching coach (the learner drives; the agent supports).
THEODORE = "theodore"
SELF_COACH = "self_coach"

_SYSTEM_PROMPTS = {
    THEODORE: (
        "You are Theodore, a warm, concise AI teacher for the Salareen platform. "
        "You are transparent that you are an AI, not a human. Speak naturally, in "
        "short spoken sentences suitable for text-to-speech. React kindly to what "
        "the learner's webcam shows (present, distracted, stepped away) without "
        "being creepy or judgemental, and keep the lesson moving."
    ),
    SELF_COACH: (
        "You are a supportive AI study coach for a self-teaching learner on the "
        "Salareen platform. The learner sets the pace; you encourage, check "
        "understanding, and offer the next small step. Speak naturally in short "
        "spoken sentences suitable for text-to-speech. Be transparent that you are "
        "an AI."
    ),
}


@dataclass
class ChatTurn:
    role: str
    content: str


class XaiVoiceError(RuntimeError):
    """Raised when the xAI endpoint call fails (before the offline fallback)."""


class XaiVoiceAgent:
    """Grok-backed teacher voice with an offline grounded fallback."""

    def __init__(
        self,
        config: Optional[WebcamLabConfig] = None,
        *,
        persona: str = THEODORE,
        transport=None,
        timeout: float = 30.0,
    ) -> None:
        self.config = config or WebcamLabConfig.from_env()
        self.persona = persona if persona in _SYSTEM_PROMPTS else THEODORE
        self._timeout = timeout
        # Injectable transport for tests: a callable(payload, stream) -> dict|iter.
        self._transport_override = transport

    @property
    def configured(self) -> bool:
        return self.config.xai_configured or self._transport_override is not None

    def system_prompt(self) -> str:
        return _SYSTEM_PROMPTS[self.persona]

    # --- public API -------------------------------------------------------- #
    def respond(
        self,
        prompt: str,
        *,
        context: Optional[str] = None,
        history: Optional[Sequence[ChatTurn]] = None,
        temperature: float = 0.6,
        max_tokens: int = 220,
    ) -> str:
        """Return a spoken reply. Falls back to a grounded line when offline."""
        messages = self._messages(prompt, context, history)
        if not self.configured:
            return self._fallback(prompt, context)
        payload = self._payload(messages, temperature=temperature, max_tokens=max_tokens, stream=False)
        try:
            raw = self._transport(payload, stream=False)
            text = _extract_message(raw)
            return text or self._fallback(prompt, context)
        except XaiVoiceError:
            return self._fallback(prompt, context)

    def respond_stream(
        self,
        prompt: str,
        *,
        context: Optional[str] = None,
        history: Optional[Sequence[ChatTurn]] = None,
        temperature: float = 0.6,
        max_tokens: int = 220,
    ) -> Iterable[str]:
        """Yield incremental spoken chunks (SSE deltas). Offline -> one fallback chunk."""
        messages = self._messages(prompt, context, history)
        if not self.configured:
            yield self._fallback(prompt, context)
            return
        payload = self._payload(messages, temperature=temperature, max_tokens=max_tokens, stream=True)
        got = False
        try:
            for line in self._transport(payload, stream=True):
                delta = _extract_delta(line)
                if delta:
                    got = True
                    yield delta
        except XaiVoiceError:
            if not got:
                yield self._fallback(prompt, context)
            return
        if not got:
            yield self._fallback(prompt, context)

    # --- message + payload shaping ---------------------------------------- #
    def _messages(
        self, prompt: str, context: Optional[str], history: Optional[Sequence[ChatTurn]]
    ) -> List[ChatTurn]:
        msgs: List[ChatTurn] = [ChatTurn("system", self.system_prompt())]
        if context:
            msgs.append(ChatTurn("system", f"Live context: {context}"))
        for turn in history or []:
            msgs.append(turn)
        msgs.append(ChatTurn("user", prompt))
        return msgs

    def _payload(
        self, messages: Sequence[ChatTurn], *, temperature: float, max_tokens: int, stream: bool
    ) -> dict:
        return {
            "model": self.config.xai_text_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    # --- transport (isolated for tests) ----------------------------------- #
    def _transport(self, payload: dict, *, stream: bool):
        if self._transport_override is not None:
            return self._transport_override(payload, stream)
        base = (self.config.xai_base_url or "").rstrip("/")
        if not base:
            raise XaiVoiceError("XAI_BASE_URL is not configured")
        url = f"{base}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        key = (self.config.xai_api_key or "").strip()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=self._timeout)  # noqa: S310
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:  # noqa: BLE001
                pass
            raise XaiVoiceError(f"xAI HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise XaiVoiceError(f"xAI unreachable: {exc.reason}") from exc
        if not stream:
            body = resp.read()
            return json.loads(body.decode("utf-8"))
        return _iter_sse(resp)

    # --- offline grounded fallback ---------------------------------------- #
    def _fallback(self, prompt: str, context: Optional[str]) -> str:
        """A natural, deterministic spoken line grounded in the moment.

        Keyed off the live context so the teacher still reacts sensibly to
        presence changes even with no Grok endpoint (mirrors the platform's
        RAG-grounded tutor fallback).
        """
        ctx = (context or "").lower()
        theo = self.persona == THEODORE
        if "stepped away" in ctx or "absent" in ctx:
            return (
                "I notice you've stepped away, so I'll pause here and pick up "
                "right where we left off when you're back."
                if theo
                else "Looks like you stepped away. No rush - I'll be right here when you return."
            )
        if "back" in ctx or "returned" in ctx:
            return (
                "Welcome back. Let's continue from where we paused."
                if theo
                else "Great, you're back. Ready to keep going when you are."
            )
        if "distracted" in ctx or "looking away" in ctx:
            return (
                "Whenever you're ready, look back at the screen and we'll keep going."
                if theo
                else "Take your time - come back to it when you can focus."
            )
        # Generic reply: echo the intent of the prompt in a natural spoken line.
        cleaned = " ".join((prompt or "").split())
        if not cleaned:
            return (
                "Let's keep going." if theo else "You're doing well - what's next for you?"
            )
        return (
            f"Good question. Here's the short version: {cleaned}"
            if theo
            else f"Nice - let's work through that: {cleaned}"
        )


# --------------------------------------------------------------------------- #
# SSE + response parsing (mirrors the platform's OpenAI-compatible parsing)
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Realtime Voice Agent (speech-to-speech) session wiring
# --------------------------------------------------------------------------- #
def build_voice_agent_session(
    config: Optional[WebcamLabConfig] = None,
    *,
    persona: str = THEODORE,
    instructions: Optional[str] = None,
    voice: Optional[str] = None,
    turn_detection: str = "server_vad",
) -> dict:
    """Build the connection wiring for xAI's Realtime Voice Agent API.

    Returns ``{url, headers, session_update}``:
      * ``url``   -> ``{realtime}?model={voice_model}`` (a wss:// endpoint).
      * ``headers`` -> Authorization bearer (omitted when no key is set).
      * ``session_update`` -> the ``session.update`` message a client sends first
        to select the voice, teacher instructions, and turn detection.

    Nothing is dialled here; opening the WebSocket is the client's job.
    """
    cfg = config or WebcamLabConfig.from_env()
    persona = persona if persona in _SYSTEM_PROMPTS else THEODORE
    model = cfg.xai_voice_model
    base = (cfg.xai_realtime_url or "").rstrip("/")
    url = f"{base}?model={model}"
    headers = {}
    key = (cfg.xai_api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    session_update = {
        "type": "session.update",
        "session": {
            "voice": voice or cfg.xai_voice,
            "instructions": instructions or _SYSTEM_PROMPTS[persona],
            "turn_detection": {"type": turn_detection},
        },
    }
    return {"url": url, "headers": headers, "session_update": session_update}
