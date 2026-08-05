from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from .models import VoiceAgentRequest, VoiceAgentResponse


Transport = Callable[[str, dict, dict, float], dict]


@dataclass
class XaiVoiceConfig:
    api_key: str
    base_url: str = "https://api.x.ai/v1"
    model: str = "grok-2-latest"
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> XaiVoiceConfig:
        return cls(
            api_key=(os.getenv("XAI_API_KEY") or "").strip(),
            base_url=(os.getenv("XAI_BASE_URL") or "https://api.x.ai/v1").strip(),
            model=(os.getenv("XAI_MODEL") or "grok-2-latest").strip(),
        )


class XaiVoiceAgent:
    """Theodore response adapter using xAI's OpenAI-compatible API surface."""

    def __init__(self, config: XaiVoiceConfig, *, transport: Transport | None = None) -> None:
        self._config = config
        self._transport = transport or self._default_transport

    def respond(self, request: VoiceAgentRequest) -> VoiceAgentResponse:
        if not self._config.api_key:
            return VoiceAgentResponse(
                text=self._fallback_text(request),
                engine="fallback",
                used_fallback=True,
            )

        payload = self._payload(request)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._config.api_key}",
        }
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        try:
            raw = self._transport(url, payload, headers, self._config.timeout_seconds)
            text = (
                raw.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if not text:
                raise RuntimeError("empty response")
            return VoiceAgentResponse(text=text, engine="xai", used_fallback=False)
        except Exception:
            return VoiceAgentResponse(
                text=self._fallback_text(request),
                engine="fallback",
                used_fallback=True,
            )

    def _payload(self, request: VoiceAgentRequest) -> dict:
        event_summary = ", ".join(request.recent_event_codes) or "none"
        student_message = (request.student_message or "").strip()
        if not student_message:
            student_message = "Please provide a short, supportive instruction."
        return {
            "model": self._config.model,
            "temperature": 0.35,
            "max_tokens": 120,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Theodore, an empathetic AI teacher. "
                        "Keep responses concise, natural, and motivating. "
                        "If events mention absence or silhouette, ask the learner to "
                        "re-center in camera and confirm they can hear you."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Class mode: {request.class_mode.value}. "
                        f"Recent events: {event_summary}. "
                        f"Student context: {student_message}"
                    ),
                },
            ],
        }

    @staticmethod
    def _default_transport(url: str, payload: dict, headers: dict, timeout: float) -> dict:
        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"xAI HTTP {exc.code}: {detail[:200]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"xAI unreachable: {exc.reason}") from exc

    @staticmethod
    def _fallback_text(request: VoiceAgentRequest) -> str:
        events = set(request.recent_event_codes)
        if "user_absent" in events:
            return (
                "I cannot see you right now. Please step back into frame and say "
                "'ready' when you are back."
            )
        if "silhouette_detected" in events:
            return (
                "I detect movement but not a clear face. Please face the camera so "
                "I can continue the lesson accurately."
            )
        if "group_understaffed" in events:
            return (
                "We are waiting for a few classmates to rejoin. Let's quickly recap "
                "the last concept while they connect."
            )
        return "Great work. Keep your camera centered and we can continue."
