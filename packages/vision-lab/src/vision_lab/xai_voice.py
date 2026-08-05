"""xAI/Grok OpenAI-compatible client for voice-agent lab responses."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Iterable, Iterator, Sequence
import urllib.error
import urllib.request

from .presence import PresenceDecision
from .speech_chunks import SpeechChunker


class XAIVoiceError(RuntimeError):
    """Raised when the xAI voice-agent chat request fails."""


@dataclass(frozen=True)
class XAIConfig:
    api_key: str = ""
    model: str = "grok-4-latest"
    base_url: str = "https://api.x.ai/v1"
    timeout_seconds: float = 45.0

    @classmethod
    def from_env(cls) -> "XAIConfig":
        return cls(
            api_key=os.environ.get("XAI_API_KEY", "").strip(),
            model=os.environ.get("XAI_MODEL", "grok-4-latest").strip()
            or "grok-4-latest",
            base_url=os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1").strip()
            or "https://api.x.ai/v1",
            timeout_seconds=float(os.environ.get("XAI_TIMEOUT_SECONDS", "45") or 45),
        )


class XAIVoiceAgent:
    """Small OpenAI-compatible xAI chat client with streaming chunk output."""

    def __init__(self, config: XAIConfig | None = None) -> None:
        self.config = config or XAIConfig.from_env()

    @property
    def configured(self) -> bool:
        return bool(self.config.api_key.strip())

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.35,
        max_tokens: int = 256,
    ) -> str:
        payload = self._payload(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        raw = self._transport(payload, stream=False)
        return _extract_message(raw)

    def stream(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.35,
        max_tokens: int = 256,
    ) -> Iterable[str]:
        payload = self._payload(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for line in self._transport(payload, stream=True):
            delta = _extract_delta(line)
            if delta:
                yield delta

    def stream_speakable_chunks(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.35,
        max_tokens: int = 256,
        chunker: SpeechChunker | None = None,
    ) -> Iterable[str]:
        chunks = chunker or SpeechChunker()
        for delta in self.stream(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield from chunks.feed(delta)
        rest = chunks.flush()
        if rest:
            yield rest

    def _payload(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> dict:
        if not self.config.api_key.strip():
            raise XAIVoiceError("XAI_API_KEY is not configured")
        return {
            "model": self.config.model,
            "messages": [
                {
                    "role": (msg.get("role") or "user").strip(),
                    "content": msg.get("content", ""),
                }
                for msg in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    def _transport(self, payload: dict, *, stream: bool):
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key.strip()}",
            },
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=self.config.timeout_seconds)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            raise XAIVoiceError(f"xAI HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise XAIVoiceError(f"xAI unreachable: {exc.reason}") from exc
        if not stream:
            return json.loads(resp.read().decode("utf-8"))
        return _iter_sse(resp)


def build_presence_voice_messages(
    decision: PresenceDecision,
    *,
    lesson_context: str = "",
    learner_name: str = "learner",
) -> list[dict[str, str]]:
    """Create a Theodore prompt for natural re-engagement based on webcam state."""

    if decision.reason == "silhouette_without_face":
        instruction = (
            "The learner's body silhouette is visible, but their face is not. "
            "Ask them warmly to adjust camera angle or lighting."
        )
    elif decision.liveness_state == "absent":
        instruction = (
            "The learner appears absent. Pause teaching and ask whether they are "
            "still with Theodore."
        )
    elif decision.reason == "too_many_faces":
        instruction = (
            "More faces than allowed are visible. Ask the learner to confirm who "
            "is participating before continuing."
        )
    elif not decision.verified_live:
        instruction = (
            "The learner may be distracted or liveness is uncertain. Re-engage "
            "without sounding accusatory."
        )
    else:
        instruction = "The learner is present. Continue with a concise helpful line."

    context = lesson_context.strip() or "Continue the current lesson."
    return [
        {
            "role": "system",
            "content": (
                "You are Theodore, an AI teacher. Speak naturally, briefly, and "
                "with clear disclosure that you are an AI teacher when helpful."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Learner: {learner_name}. Presence reason: {decision.reason}. "
                f"Liveness: {decision.liveness_state}. Context: {context}. "
                f"Instruction: {instruction}"
            ),
        },
    ]


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
