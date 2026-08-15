"""xAI Theodore voice agent for course studio, with offline local fallback.

Pattern matches the webcam lab / aoep_shared stack:
  1) Grok (xAI) generates teaching text when XAI_API_KEY is set
  2) Speech gateway / device TTS speaks it (see ``tts_client``)
  3) Without a key or on API failure → deterministic local-fallback text

Fully usable offline for demos and long training loops.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from pydantic import BaseModel, Field

from .studio_languages import language_instruction, language_name, normalize_language

# xAI retired the grok-2 family from the API (grok-2-1212 was removed in January
# 2026), so the old default returned a bare HTTP 400 even with a valid key.
# grok-4.3 rather than the newer grok-4.5 because 4.5 is not offered to EU API
# Console accounts and a default has to work everywhere; override with XAI_MODEL.
XAI_DEFAULT_MODEL = "grok-4.3"


class VoiceTurn(BaseModel):
    provider: str = "local-fallback"  # xai | local-fallback | aoep_shared
    message: str
    language_code: str = "en"
    language_name: str = "English"
    fallback_used: bool = True
    latency_ms: int = 0
    model: str = ""
    tts_engine_chain: list[str] = Field(
        default_factory=lambda: ["elevenlabs", "edge-tts", "device"]
    )
    should_stream_audio: bool = True


class CourseStudioVoiceAgent:
    """Theodore teaching voice for course studio sessions."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float = 25.0,
    ) -> None:
        self._api_key = (api_key if api_key is not None else os.environ.get("XAI_API_KEY", "")).strip()
        self._base_url = (
            base_url
            or os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1")
        ).rstrip("/")
        self._model = model or os.environ.get("XAI_MODEL", "").strip() or XAI_DEFAULT_MODEL
        self._timeout_s = float(os.environ.get("XAI_TIMEOUT_S", timeout_s))
        self._history: dict[str, list[dict[str, str]]] = {}

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def status(self) -> dict[str, Any]:
        return {
            "xai_available": self.available,
            "provider": "xai" if self.available else "local-fallback",
            "model": self._model if self.available else "",
            "tts_engine_chain": ["elevenlabs", "edge-tts", "device"],
            "realtime_hint": "Use aoep_shared.xai_realtime for browser S2S when promoting to main app",
            "offline_ok": True,
        }

    def clear_session(self, session_id: str) -> None:
        self._history.pop(session_id, None)

    def present_slide(
        self,
        *,
        session_id: str,
        title: str,
        body: str,
        language_code: str = "en",
        course_title: str = "",
    ) -> VoiceTurn:
        """Rewrite / enrich a slide narration for spoken delivery."""
        lang = normalize_language(language_code)
        prompt = (
            f"Present this lesson slide aloud as Theodore.\n"
            f"Course: {course_title or 'Studio course'}\n"
            f"Slide title: {title}\n"
            f"Slide content:\n{body}\n"
            "Keep it under 3 spoken sentences. Do not invent facts beyond the slide."
        )
        return self.respond(
            session_id=session_id,
            learner_message=prompt,
            language_code=lang,
            lesson_context=f"{course_title}\n{title}\n{body}",
        )

    def respond(
        self,
        *,
        session_id: str,
        learner_message: str,
        language_code: str = "en",
        lesson_context: str = "",
    ) -> VoiceTurn:
        lang = normalize_language(language_code)
        lname = language_name(lang)
        started = time.time()
        cleaned = (learner_message or "").strip() or "Continue the lesson with one clear point."

        # Prefer shared TeacherVoiceAgent when package + key are available.
        shared = self._try_shared_agent(
            session_id=session_id,
            text=cleaned,
            language_code=lang,
            lesson_context=lesson_context,
        )
        if shared is not None:
            shared.latency_ms = int((time.time() - started) * 1000)
            return shared

        if self.available:
            try:
                text = self._chat_xai(
                    session_id=session_id,
                    learner_message=cleaned,
                    language_code=lang,
                    lesson_context=lesson_context,
                )
                return VoiceTurn(
                    provider="xai",
                    message=text,
                    language_code=lang,
                    language_name=lname,
                    fallback_used=False,
                    latency_ms=int((time.time() - started) * 1000),
                    model=self._model,
                )
            except Exception:  # noqa: BLE001 — always degrade offline-safe
                pass

        return self._fallback(
            learner_message=cleaned,
            language_code=lang,
            language_name=lname,
            latency_ms=int((time.time() - started) * 1000),
        )

    def ask_check_question(
        self,
        *,
        session_id: str,
        topic: str,
        language_code: str = "en",
        difficulty: str = "medium",
    ) -> VoiceTurn:
        lang = normalize_language(language_code)
        prompt = (
            f"Ask one short spoken check question about: {topic}. "
            f"Difficulty: {difficulty}. Do not answer it yourself."
        )
        return self.respond(
            session_id=session_id,
            learner_message=prompt,
            language_code=lang,
            lesson_context=topic,
        )

    def _try_shared_agent(
        self,
        *,
        session_id: str,
        text: str,
        language_code: str,
        lesson_context: str,
    ) -> VoiceTurn | None:
        if not self.available:
            return None
        try:
            from aoep_shared.xai_voice import (  # type: ignore
                TeacherVoiceAgent,
                XAIVoiceClient,
            )
        except Exception:  # noqa: BLE001
            return None
        try:
            client = XAIVoiceClient(api_key=self._api_key, model=self._model)
            if not getattr(client, "available", True):
                return None
            ctx = (
                f"{lesson_context}\n{language_instruction(language_code)}"
                if lesson_context
                else language_instruction(language_code)
            )
            agent = TeacherVoiceAgent(client, extra_context=ctx)
            # audio=False — studio uses speech gateway / device TTS separately
            resp = agent.speak(text, audio=False)
            msg = getattr(resp, "text", "") or str(resp)
            self._history.setdefault(session_id, []).append(
                {"role": "user", "content": text}
            )
            self._history[session_id].append({"role": "assistant", "content": msg})
            return VoiceTurn(
                provider="aoep_shared",
                message=msg,
                language_code=language_code,
                language_name=language_name(language_code),
                fallback_used=False,
                model=getattr(resp, "model", self._model) or self._model,
            )
        except Exception:  # noqa: BLE001
            return None

    def _chat_xai(
        self,
        *,
        session_id: str,
        learner_message: str,
        language_code: str,
        lesson_context: str,
    ) -> str:
        system = (
            "You are Theodore, an AI teacher on the Salareen / AOEP platform. "
            "Speak warmly and concisely for voice delivery (under 3 sentences). "
            f"{language_instruction(language_code)}"
        )
        if lesson_context.strip():
            system += f"\n\nLesson context:\n{lesson_context.strip()[:2000]}"
        history = self._history.setdefault(session_id, [])
        messages = [{"role": "system", "content": system}, *history]
        messages.append({"role": "user", "content": learner_message})
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.65,
            "max_tokens": 280,
        }
        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        text = (
            raw.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not text:
            raise RuntimeError("empty xAI response")
        history.append({"role": "user", "content": learner_message})
        history.append({"role": "assistant", "content": text})
        if len(history) > 24:
            del history[:-24]
        return text

    @staticmethod
    def _fallback(
        *,
        learner_message: str,
        language_code: str,
        language_name: str,
        latency_ms: int,
    ) -> VoiceTurn:
        cleaned = (learner_message or "").strip()
        if len(cleaned) > 220:
            cleaned = cleaned[:217].rstrip() + "…"
        message = (
            f"[{language_name}] Let's take this one clear step at a time. "
            f"Focus on: {cleaned} "
            "I will check your understanding after this point."
        )
        return VoiceTurn(
            provider="local-fallback",
            message=message,
            language_code=language_code,
            language_name=language_name,
            fallback_used=True,
            latency_ms=latency_ms,
        )


_agent: CourseStudioVoiceAgent | None = None


def get_voice_agent() -> CourseStudioVoiceAgent:
    global _agent
    if _agent is None:
        _agent = CourseStudioVoiceAgent()
    return _agent
