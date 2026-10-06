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
import re
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

# Spoken when a question or comment is not about the course being taught.
OFF_COURSE_MESSAGE = (
    "I would like to help, and that topic is outside this course. "
    "I can only talk about the training material. "
    "Ask me about a rule, a sign, or the page you are studying."
)

_TOKEN = re.compile(r"[a-z0-9']+")
_STOP = frozenset(
    """
    a an the and or but if so to of in on for from with at by as is are was were
    be been being it its this that these those i you we they me my your our do
    does did doing not no yes please can could would should will just about into
    over than then there here when where who what which why how tell say talk
    ask question comment
    """.split()
)
# Words a student uses to talk about the page or the training as a whole,
# without naming a specific course term.
_PAGE_TALK = frozenset(
    """
    explain mean means meaning again repeat example examples confused confusing
    understand understood help helpful hard harder difficult easy easier clear
    unclear good great like love nice tough useful interesting boring long short
    wrong right page slide lesson course sign rule training study studying
    material materials topic topics content contents subject subjects overview
    summary purpose idea ideas thing things info information details detail
    module modules section sections chapter chapters whole entire general overall
    basics basic simple cover covers covering learn learning teach teaches teaching
    """.split()
)


def _course_sentence(message: str, lesson_context: str) -> str:
    """Pick the course line that best answers the question.

    A page whose title is the word they asked about (Stop, Yield) wins over
    a later rule that merely mentions that word.
    """
    content = [
        w
        for w in _tokens(message)
        if len(w) >= 4 and w not in _STOP and w not in _PAGE_TALK
    ]
    lines = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+|\n+", lesson_context)
        if part.strip()
    ]
    best = ""
    best_score = 0
    if not content:
        course_line = next(
            (line for line in lines if line.lower().startswith("course:")), ""
        )
        page_line = next(
            (line for line in lines if line.lower().startswith("current page:")), ""
        )
        if course_line and page_line:
            return f"{course_line}. {page_line}"
        return page_line or course_line or (lines[0] if lines else "Look at the page in front of you.")
    for index, sentence in enumerate(lines):
        if sentence.lower().startswith("course:") or sentence.lower().startswith("pages in"):
            continue
        words = _tokens(sentence)
        wordset = set(words)
        score = sum(3 for word in content if word in wordset)
        title_hit = sentence.lower() in content or (
            len(words) <= 3 and any(word in content for word in words) and len(sentence) < 48
        )
        if title_hit and index + 1 < len(lines):
            definition = lines[index + 1]
            score = 8 + sum(3 for word in content if word in set(_tokens(definition)))
            sentence = definition
        if score > best_score:
            best, best_score = sentence, score
    snippet = best or (lines[0] if lines else "Look at the page in front of you.")
    if len(snippet) > 320:
        snippet = snippet[:317].rstrip() + "…"
    return snippet


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def relates_to_course(message: str, lesson_context: str) -> bool:
    """True when the learner is asking or commenting about this course.

    General questions about the training stay in scope, including wording the
    slides never use ("what is this material about?"). A question that names a
    different subject — a city, a sport, another class — is still off-topic.
    """
    ctx = {w for w in _tokens(lesson_context) if len(w) >= 4 and w not in _STOP}
    words = _tokens(message)
    if not words:
        return False
    outside = [
        w
        for w in words
        if len(w) >= 4 and w not in _STOP and w not in _PAGE_TALK and w not in ctx
    ]
    mentions_training = bool(set(words) & _PAGE_TALK)
    mentions_course = any(w in ctx for w in words)
    if mentions_training:
        return True
    # A course word plus an unrelated subject ("weather in Tokyo") stays refused.
    if mentions_course and not outside:
        return True
    if outside:
        return False
    # "why?", "what is this about?" — about the page in front of them.
    return bool(set(words) & frozenset("why how what when where".split()))


def course_context_for(course_title: str, slides: list[tuple[str, str]], current_title: str, current_body: str) -> str:
    """Titles for the whole course, plus the page the student is on."""
    titles = "\n".join(title for title, _body in slides if title)
    text = (
        f"Course: {course_title}\n"
        f"Current page: {current_title}\n"
        f"{current_body}\n\n"
        f"Pages in this course:\n{titles}"
    )
    return text[:8000]


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
        from aoep_shared.supergrok import SUPERGROK_MODEL, subscription_configured

        supergrok = subscription_configured()
        if supergrok:
            provider = "supergrok"
            model = SUPERGROK_MODEL
        elif self.available:
            provider = "xai"
            model = self._model
        else:
            provider = "local-fallback"
            model = ""
        return {
            "xai_available": self.available or supergrok,
            "supergrok": supergrok,
            "provider": provider,
            "model": model,
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
        scope_to_course: bool = False,
    ) -> VoiceTurn:
        lang = normalize_language(language_code)
        lname = language_name(lang)
        started = time.time()
        cleaned = (learner_message or "").strip() or "Continue the lesson with one clear point."
        # Learner questions (Talk) stay on the course. Slide narration does not
        # set this flag, so a present prompt is never treated as off-topic.
        if (
            scope_to_course
            and lesson_context.strip()
            and not relates_to_course(learner_message or "", lesson_context)
        ):
            return VoiceTurn(
                provider="local-fallback",
                message=OFF_COURSE_MESSAGE,
                language_code="en",
                language_name="English",
                fallback_used=True,
                latency_ms=int((time.time() - started) * 1000),
                model="",
            )

        model_context = lesson_context
        if scope_to_course and lesson_context.strip():
            focus = _course_sentence(cleaned, lesson_context)
            model_context = f"Most relevant training:\n{focus}\n\n{lesson_context}"
        shared_context = model_context
        if scope_to_course and lesson_context.strip():
            shared_context = (
                "Answer questions about this course, including what the training "
                "covers and how the current page fits it. Only when the question "
                "is clearly about a different subject, reply exactly: "
                f"{OFF_COURSE_MESSAGE}\n\n{model_context}"
            )
        supergrok = self._try_supergrok(
            session_id=session_id,
            learner_message=cleaned,
            language_code=lang,
            lesson_context=model_context,
        )
        if supergrok is not None:
            supergrok.latency_ms = int((time.time() - started) * 1000)
            supergrok.language_name = lname
            return supergrok

        # Prefer shared TeacherVoiceAgent when package + key are available.
        shared = self._try_shared_agent(
            session_id=session_id,
            text=cleaned,
            language_code=lang,
            lesson_context=shared_context,
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
                    lesson_context=model_context,
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
            lesson_context=lesson_context if scope_to_course else "",
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

    def _try_supergrok(
        self,
        *,
        session_id: str,
        learner_message: str,
        language_code: str,
        lesson_context: str,
    ) -> VoiceTurn | None:
        try:
            from aoep_shared.supergrok import (  # type: ignore
                SUPERGROK_MODEL,
                SuperGrokUnavailable,
                subscription_configured,
                subscription_reply,
            )
        except Exception:  # noqa: BLE001
            return None
        if not subscription_configured():
            return None
        try:
            text = subscription_reply(
                self._messages(
                    session_id=session_id,
                    learner_message=learner_message,
                    language_code=language_code,
                    lesson_context=lesson_context,
                ),
                temperature=0.65,
                max_tokens=280,
                timeout_s=self._timeout_s,
            )
        except SuperGrokUnavailable:
            return None
        self._remember(session_id, learner_message, text)
        return VoiceTurn(
            provider="supergrok",
            message=text,
            language_code=language_code,
            language_name=language_name(language_code),
            fallback_used=False,
            model=SUPERGROK_MODEL,
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

    def _messages(
        self,
        *,
        session_id: str,
        learner_message: str,
        language_code: str,
        lesson_context: str,
    ) -> list[dict[str, str]]:
        system = (
            "You are Theodore, an AI teacher on the Salareen / AOEP platform. "
            "Speak warmly and concisely for voice delivery (under 3 sentences). "
            f"{language_instruction(language_code)}"
        )
        if lesson_context.strip():
            system += (
                "\n\nAnswer questions about this course's training material, "
                "including general questions about what it covers. "
                "Only if the learner asks about a clearly different subject, "
                "reply with exactly this and nothing more: "
                f"{OFF_COURSE_MESSAGE}\n\n"
                f"Lesson context:\n{lesson_context.strip()[:2000]}"
            )
        history = self._history.setdefault(session_id, [])
        return [{"role": "system", "content": system}, *history, {"role": "user", "content": learner_message}]

    def _remember(self, session_id: str, learner_message: str, text: str) -> None:
        history = self._history.setdefault(session_id, [])
        history.append({"role": "user", "content": learner_message})
        history.append({"role": "assistant", "content": text})
        if len(history) > 24:
            del history[:-24]

    def _chat_xai(
        self,
        *,
        session_id: str,
        learner_message: str,
        language_code: str,
        lesson_context: str,
    ) -> str:
        messages = self._messages(
            session_id=session_id,
            learner_message=learner_message,
            language_code=language_code,
            lesson_context=lesson_context,
        )
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
        self._remember(session_id, learner_message, text)
        return text

    @staticmethod
    def _fallback(
        *,
        learner_message: str,
        language_code: str,
        language_name: str,
        latency_ms: int,
        lesson_context: str = "",
    ) -> VoiceTurn:
        cleaned = (learner_message or "").strip()
        if lesson_context.strip():
            message = (
                f"[{language_name}] Let's stay with this course. "
                f"{_course_sentence(cleaned, lesson_context)}"
            )
        else:
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
