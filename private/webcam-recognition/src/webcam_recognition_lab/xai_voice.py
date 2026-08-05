"""xAI-compatible Theodore response adapter for webcam presence events."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Sequence

from .signals import PresenceDecision

Transport = Callable[[str, dict, dict, float], dict]


@dataclass(frozen=True)
class VoiceAgentEvent:
    learner_name: str
    mode_label: str
    decision: PresenceDecision
    recent_context: Sequence[str] = ()

    def prompt(self) -> str:
        context = " ".join(s.strip() for s in self.recent_context if s.strip())
        if not context:
            context = "Continue the current lesson."
        return (
            f"Learner: {self.learner_name or 'learner'}\n"
            f"Mode: {self.mode_label}\n"
            f"Presence reason: {self.decision.reason}\n"
            f"Teacher action: {self.decision.teacher_action}\n"
            f"Lesson context: {context}\n"
            "Respond as Theodore, the AI teacher. Be natural, supportive, and brief. "
            "Do not mention surveillance or biometrics. If the learner is absent, "
            "pause warmly and invite them back. If only a silhouette is visible, "
            "ask for a small camera adjustment."
        )


@dataclass(frozen=True)
class VoiceAgentResponse:
    text: str
    model: str
    used_network: bool


def _default_transport(url: str, headers: dict, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"xAI HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"xAI unreachable: {exc.reason}") from exc
    return json.loads(body)


class XaiVoiceAgent:
    """Small OpenAI-compatible client for xAI-backed Theodore voice responses."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 20.0,
        transport: Transport = _default_transport,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.getenv("XAI_API_KEY", "")).strip()
        self.base_url = (base_url or os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")).rstrip("/")
        self.model = (model or os.getenv("XAI_VOICE_MODEL", "grok-4")).strip()
        self.timeout = timeout
        self.transport = transport

    def respond(self, event: VoiceAgentEvent) -> VoiceAgentResponse:
        if not self.api_key:
            return VoiceAgentResponse(
                text=_fallback_text(event),
                model="offline-theodore",
                used_network=False,
            )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Theodore, Salareen's calm AI teacher. "
                        "Answer in one or two spoken sentences."
                    ),
                },
                {"role": "user", "content": event.prompt()},
            ],
            "temperature": 0.4,
            "max_tokens": 120,
        }
        raw = self.transport(
            f"{self.base_url}/chat/completions",
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            payload,
            self.timeout,
        )
        text = _extract_text(raw)
        return VoiceAgentResponse(
            text=text or _fallback_text(event),
            model=self.model,
            used_network=True,
        )


def _extract_text(raw: dict) -> str:
    try:
        return str(raw["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError):
        return ""


def _fallback_text(event: VoiceAgentEvent) -> str:
    reason = event.decision.reason
    name = event.learner_name or "there"
    if reason == "absent":
        return f"I'll pause here, {name}. Come back when you're ready and we'll continue."
    if reason == "silhouette_only":
        return f"I can tell you're nearby, {name}. Please face the camera so I can keep pace with you."
    if reason == "too_many_faces":
        return "I see more than one person in this learning seat, so I'll pause until it is just you."
    if reason == "low_attention":
        return f"Let's reset for a moment, {name}. Here is the key idea again in simpler words."
    return f"Great, {name}. Let's keep going."
