from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .types import ClassMode, VoiceResponse


class XaiVoiceAgentError(RuntimeError):
    """Raised when the xAI voice-agent endpoint call fails."""


class XaiVoiceAgent:
    """xAI-backed Theodore conversational responder with local fallback."""

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "https://api.x.ai/v1",
        model: str = "grok-4",
        timeout_s: float = 25.0,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s

    @classmethod
    def from_env(cls) -> "XaiVoiceAgent":
        return cls(
            api_key=os.environ.get("XAI_API_KEY", ""),
            base_url=os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1"),
            model=os.environ.get("XAI_MODEL", "grok-4"),
            timeout_s=float(os.environ.get("XAI_TIMEOUT_S", "25")),
        )

    def respond(
        self,
        *,
        learner_message: str,
        class_mode: ClassMode,
        context: str = "",
    ) -> VoiceResponse:
        prompt = self._build_prompt(
            learner_message=learner_message,
            class_mode=class_mode,
            context=context,
        )
        if not self._api_key:
            return self._fallback_response(learner_message)

        payload = {
            "model": self._model,
            "messages": prompt,
            "temperature": 0.5,
            "max_tokens": 240,
            "stream": False,
        }
        try:
            body = self._transport(payload)
            message = self._extract_message(body)
        except XaiVoiceAgentError:
            message = ""
        if not message:
            return self._fallback_response(learner_message)

        return VoiceResponse(
            provider="xai",
            message=message,
            communication_style="natural_conversational",
            fallback_used=False,
        )

    def _build_prompt(
        self, *, learner_message: str, class_mode: ClassMode, context: str
    ) -> list[dict[str, str]]:
        system = (
            "You are Theodore, an educational AI teacher. Reply in clear, warm "
            "speech-ready language that sounds natural when spoken aloud. "
            "Always keep feedback actionable and concise."
        )
        mode_text = "group class" if class_mode is ClassMode.GROUP else "solo session"
        user_parts = [
            f"Class mode: {mode_text}.",
            f"Learner says: {learner_message.strip()}",
        ]
        if context.strip():
            user_parts.append(f"Context: {context.strip()}")
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": " ".join(user_parts)},
        ]

    def _transport(self, payload: dict) -> dict:
        if not self._base_url:
            raise XaiVoiceAgentError("XAI_BASE_URL is empty")
        url = f"{self._base_url}/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            raise XaiVoiceAgentError(f"xAI HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise XaiVoiceAgentError(f"xAI unreachable: {exc.reason}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise XaiVoiceAgentError("xAI response is not valid JSON") from exc

    @staticmethod
    def _extract_message(payload: dict) -> str:
        try:
            return (payload["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError):
            return ""

    @staticmethod
    def _fallback_response(learner_message: str) -> VoiceResponse:
        cleaned = (learner_message or "").strip()
        if not cleaned:
            cleaned = "Let's begin by reviewing one clear learning goal."
        return VoiceResponse(
            provider="local-fallback",
            message=(
                "I hear you. We'll break this into one step at a time, then I will "
                f"check understanding after each step. First focus: {cleaned}"
            ),
            communication_style="natural_conversational",
            fallback_used=True,
        )
