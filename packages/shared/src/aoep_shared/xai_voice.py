"""xAI Grok voice agent client for natural communication in teaching sessions.

Integrates xAI's Grok model (https://docs.x.ai/api) as a conversational voice
agent inside webcam teaching sessions. Grok handles natural dialogue responses
for both Theodore (AI teacher) and self-teaching scenarios.

The module is deliberately thin (stdlib urllib only, no third-party deps) so it
can run inside any service without adding heavy packages. Audio synthesis falls
back gracefully to the platform's existing ElevenLabs → edge-tts chain when the
xAI audio endpoint is not available (or the key is not set).

Architecture:
- ``XAIVoiceClient``   — HTTP client wrapping the xAI Chat Completions API.
- ``VoiceAgentSession`` — stateful conversation session for one participant.
- ``TeacherVoiceAgent`` — Theodore-specific wrapper with teaching persona.
- ``SelfTeachVoiceAgent`` — student self-teaching Socratic coach wrapper.

Audio
-----
xAI's beta audio endpoint (model ``grok-2-audio-*``) returns both a text
transcript and a base64-encoded audio segment (MP3) in a single call. When the
audio endpoint is not reachable the client falls back to text-only and the caller
is expected to run TTS via the platform speech gateway.

Configuration (env):
- XAI_API_KEY      — secret; enables the Grok voice agent path.
- XAI_BASE_URL     — override API root (default https://api.x.ai/v1).
- XAI_MODEL        — model slug (default grok-4.3).
- XAI_AUDIO_MODEL  — audio model slug (default grok-2-audio; empty to disable).
- XAI_MAX_TOKENS   — default 512.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterator, List, Optional

# --------------------------------------------------------------------------- #
# Data types
# --------------------------------------------------------------------------- #

@dataclass
class VoiceAgentResponse:
    """Response from a single voice agent turn."""

    text: str                        # The agent's text response.
    audio_b64: Optional[str] = None  # Base64 MP3 audio (when audio endpoint used).
    model: str = ""
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def has_audio(self) -> bool:
        return bool(self.audio_b64)

    def audio_bytes(self) -> Optional[bytes]:
        """Decode audio_b64 to raw MP3 bytes (or None)."""
        if self.audio_b64:
            return base64.b64decode(self.audio_b64)
        return None


@dataclass
class ConversationMessage:
    role: str   # "system" | "user" | "assistant"
    content: str


# --------------------------------------------------------------------------- #
# Low-level HTTP client
# --------------------------------------------------------------------------- #

class XAIVoiceClient:
    """Thin wrapper around the xAI Chat Completions API.

    Uses stdlib ``urllib`` only — no ``requests`` or ``httpx`` dependency.
    """

    _DEFAULT_BASE = "https://api.x.ai/v1"
    _DEFAULT_MODEL = "grok-4.3"
    _DEFAULT_AUDIO_MODEL = "grok-2-audio"
    _DEFAULT_MAX_TOKENS = 512
    _TIMEOUT_S = 30

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        audio_model: str = "",
        max_tokens: int = 0,
    ) -> None:
        self._api_key = api_key
        self._base_url = (base_url or self._DEFAULT_BASE).rstrip("/")
        self._model = model or self._DEFAULT_MODEL
        self._audio_model = audio_model if audio_model is not None else self._DEFAULT_AUDIO_MODEL
        self._max_tokens = max_tokens or self._DEFAULT_MAX_TOKENS

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def chat(
        self,
        messages: List[ConversationMessage],
        *,
        audio: bool = False,
        temperature: float = 0.7,
    ) -> VoiceAgentResponse:
        """Send a chat request and return a ``VoiceAgentResponse``.

        When ``audio=True`` and ``XAI_AUDIO_MODEL`` is set, attempts the audio
        endpoint for a combined text+audio response. Falls back to text-only on
        any error.

        Raises ``NotImplementedError`` when no API key is configured.
        """
        if not self.available:
            raise NotImplementedError(
                "xAI API key not configured (XAI_API_KEY). "
                "Set the key to enable the Grok voice agent; without it "
                "Theodore uses the platform's built-in LLM + TTS chain."
            )
        use_audio = audio and bool(self._audio_model)
        try:
            return self._call_api(messages, use_audio=use_audio, temperature=temperature)
        except NotImplementedError:
            raise
        except Exception:  # noqa: BLE001
            if use_audio:
                # Audio failed — retry text-only.
                return self._call_api(messages, use_audio=False, temperature=temperature)
            raise

    def stream_chat(
        self,
        messages: List[ConversationMessage],
        *,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Stream a text response token by token (Server-Sent Events).

        Yields text delta strings. Audio is not available in streaming mode.
        Raises ``NotImplementedError`` when no key configured.
        """
        if not self.available:
            raise NotImplementedError("xAI API key not configured (XAI_API_KEY).")

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": self._max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        url = f"{self._base_url}/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._TIMEOUT_S) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:]
                    if chunk == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                        delta = (
                            obj.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue
        except urllib.error.URLError as exc:
            raise ConnectionError(f"xAI API unreachable: {exc}") from exc

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _call_api(
        self,
        messages: List[ConversationMessage],
        *,
        use_audio: bool,
        temperature: float,
    ) -> VoiceAgentResponse:
        model = self._audio_model if use_audio else self._model
        payload: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": self._max_tokens,
            "temperature": temperature,
        }
        if use_audio:
            payload["audio"] = {"format": "mp3"}

        url = f"{self._base_url}/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._TIMEOUT_S) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise ConnectionError(
                f"xAI API error {exc.code}: {err_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(f"xAI API unreachable: {exc}") from exc

        choice = body.get("choices", [{}])[0]
        message = choice.get("message", {})
        text = message.get("content") or message.get("text") or ""

        audio_b64: Optional[str] = None
        if use_audio:
            audio_block = message.get("audio", {})
            audio_b64 = audio_block.get("data") if isinstance(audio_block, dict) else None

        usage = body.get("usage", {})
        return VoiceAgentResponse(
            text=text,
            audio_b64=audio_b64,
            model=body.get("model", model),
            finish_reason=choice.get("finish_reason", "stop"),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )


# --------------------------------------------------------------------------- #
# Conversation session
# --------------------------------------------------------------------------- #

class VoiceAgentSession:
    """Stateful multi-turn conversation session for one participant.

    Maintains conversation history and provides a simple ``reply()`` interface
    that returns a ``VoiceAgentResponse``.
    """

    def __init__(
        self,
        client: XAIVoiceClient,
        system_prompt: str = "",
        max_history_turns: int = 20,
    ) -> None:
        self._client = client
        self._system = system_prompt
        self._max_turns = max_history_turns
        self._history: List[ConversationMessage] = []

    def reply(
        self,
        user_text: str,
        *,
        audio: bool = False,
        temperature: float = 0.7,
    ) -> VoiceAgentResponse:
        """Append user turn, get assistant response, update history."""
        self._history.append(ConversationMessage(role="user", content=user_text))
        messages = self._build_messages()
        response = self._client.chat(messages, audio=audio, temperature=temperature)
        self._history.append(
            ConversationMessage(role="assistant", content=response.text)
        )
        # Trim history to avoid context bloat.
        if len(self._history) > self._max_turns * 2:
            self._history = self._history[-(self._max_turns * 2):]
        return response

    def stream_reply(
        self,
        user_text: str,
        *,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Stream a reply token-by-token; history is updated when complete."""
        self._history.append(ConversationMessage(role="user", content=user_text))
        messages = self._build_messages()
        full = ""
        for token in self._client.stream_chat(messages, temperature=temperature):
            full += token
            yield token
        self._history.append(ConversationMessage(role="assistant", content=full))

    def clear(self) -> None:
        self._history.clear()

    def _build_messages(self) -> List[ConversationMessage]:
        msgs: List[ConversationMessage] = []
        if self._system:
            msgs.append(ConversationMessage(role="system", content=self._system))
        msgs.extend(self._history)
        return msgs


# --------------------------------------------------------------------------- #
# Teaching personas
# --------------------------------------------------------------------------- #

_THEODORE_SYSTEM = """\
You are Theodore, an AI teacher powered by Grok on the Salareen education platform.
Your role is to guide learners through course content with warmth, clarity, and
encouragement. You speak naturally and concisely — like a knowledgeable, patient
tutor speaking aloud (not writing an essay). Keep responses under 3 sentences
unless a thorough explanation is explicitly requested.

Context: you are in a live webcam session. You can see whether the student is
present, their engagement level, and whether they appear confused or disengaged.
React naturally — if they step away, offer to pause; if they seem confused, ask
a check-in question. Never be robotic or use jargon without explanation.
"""

_SELF_TEACH_SYSTEM = """\
You are a Socratic coaching assistant powered by Grok on the Salareen platform.
Your role is to help a self-teaching student reason through problems and deepen
understanding — not to give direct answers. Ask clarifying questions, offer hints,
and celebrate effort. Speak naturally and concisely as if talking face-to-face.
Keep responses under 4 sentences unless working through a multi-step problem.
"""


class TeacherVoiceAgent:
    """Theodore as a Grok-powered voice agent for live teaching sessions.

    This is the production surface consumed by the webcam service and the
    orchestrator when XAI_API_KEY is configured.
    """

    def __init__(
        self,
        client: XAIVoiceClient,
        extra_context: str = "",
    ) -> None:
        system = _THEODORE_SYSTEM
        if extra_context:
            system = f"{system}\n\nLesson context:\n{extra_context}"
        self._session = VoiceAgentSession(client, system_prompt=system)
        self._client = client

    def speak(
        self,
        text: str,
        *,
        audio: bool = True,
        temperature: float = 0.65,
    ) -> VoiceAgentResponse:
        """Generate Theodore's response to ``text`` (student utterance or event)."""
        return self._session.reply(text, audio=audio, temperature=temperature)

    def stream_speak(
        self, text: str, *, temperature: float = 0.65
    ) -> Iterator[str]:
        return self._session.stream_reply(text, temperature=temperature)

    def on_student_absent(self, away_s: float) -> VoiceAgentResponse:
        """Generate a natural 'pause + wait' message when the student steps away."""
        prompt = (
            f"The student stepped away from their webcam {int(away_s)} seconds ago. "
            "Generate a brief, warm message to let them know I noticed and that "
            "I'll be here when they return. Keep it under 2 sentences."
        )
        return self._session.reply(prompt, audio=True, temperature=0.5)

    def on_student_returned(self, away_s: float) -> VoiceAgentResponse:
        """Generate a welcoming re-engagement message when the student returns."""
        prompt = (
            f"The student was away for about {int(away_s)} seconds and just returned "
            "to the webcam. Generate a brief, warm welcome-back message that smoothly "
            "resumes where we left off. Keep it under 2 sentences."
        )
        return self._session.reply(prompt, audio=True, temperature=0.6)

    def on_low_engagement(self, attention: float, slide_title: str = "") -> VoiceAgentResponse:
        """Generate a re-engagement nudge when attention drops."""
        ctx = f" on slide '{slide_title}'" if slide_title else ""
        prompt = (
            f"The student's engagement score dropped to {attention:.0%}{ctx}. "
            "Generate a short, encouraging check-in question or comment to re-engage them. "
            "Sound natural and conversational."
        )
        return self._session.reply(prompt, audio=True, temperature=0.7)

    def reset(self) -> None:
        self._session.clear()


class SelfTeachVoiceAgent:
    """Socratic self-teaching coach powered by Grok.

    Activated when a student is in solo self-teaching mode (no live teacher).
    """

    def __init__(
        self,
        client: XAIVoiceClient,
        topic: str = "",
    ) -> None:
        system = _SELF_TEACH_SYSTEM
        if topic:
            system = f"{system}\n\nCurrent topic: {topic}"
        self._session = VoiceAgentSession(client, system_prompt=system)

    def ask(
        self, user_text: str, *, audio: bool = True
    ) -> VoiceAgentResponse:
        return self._session.reply(user_text, audio=audio)

    def stream_ask(self, user_text: str) -> Iterator[str]:
        return self._session.stream_reply(user_text)

    def on_stuck(self, duration_s: float) -> VoiceAgentResponse:
        """Offer a hint when the student appears stuck (no interaction for a while)."""
        prompt = (
            f"The student hasn't interacted for {int(duration_s)} seconds and "
            "may be stuck. Offer a gentle Socratic hint to nudge them forward "
            "without giving the answer away."
        )
        return self._session.reply(prompt, audio=True, temperature=0.7)

    def reset(self) -> None:
        self._session.clear()


# --------------------------------------------------------------------------- #
# Factory helper
# --------------------------------------------------------------------------- #

def make_client_from_config(config) -> XAIVoiceClient:  # type: ignore[return]
    """Construct an ``XAIVoiceClient`` from an ``AppConfig`` instance."""
    return XAIVoiceClient(
        api_key=getattr(config, "xai_api_key", ""),
        base_url=getattr(config, "xai_base_url", ""),
        model=getattr(config, "xai_model", ""),
        audio_model=getattr(config, "xai_audio_model", ""),
        max_tokens=int(getattr(config, "xai_max_tokens", 0) or 0),
    )
