from __future__ import annotations

import contextlib
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .types import (
    AudioAnswerAssessment,
    ClassMode,
    SupportedLanguage,
    VoiceQuestion,
    VoiceResponse,
)

SUPPORTED_LANGUAGES: list[SupportedLanguage] = [
    SupportedLanguage(code="en", name="English"),
    SupportedLanguage(code="es", name="Spanish"),
    SupportedLanguage(code="fr", name="French"),
    SupportedLanguage(code="de", name="German"),
    SupportedLanguage(code="it", name="Italian"),
    SupportedLanguage(code="pt", name="Portuguese"),
    SupportedLanguage(code="nl", name="Dutch"),
    SupportedLanguage(code="sv", name="Swedish"),
    SupportedLanguage(code="no", name="Norwegian"),
    SupportedLanguage(code="da", name="Danish"),
    SupportedLanguage(code="fi", name="Finnish"),
    SupportedLanguage(code="pl", name="Polish"),
    SupportedLanguage(code="cs", name="Czech"),
    SupportedLanguage(code="sk", name="Slovak"),
    SupportedLanguage(code="ro", name="Romanian"),
    SupportedLanguage(code="hu", name="Hungarian"),
    SupportedLanguage(code="el", name="Greek"),
    SupportedLanguage(code="tr", name="Turkish"),
    SupportedLanguage(code="ru", name="Russian"),
    SupportedLanguage(code="uk", name="Ukrainian"),
    SupportedLanguage(code="ar", name="Arabic"),
    SupportedLanguage(code="he", name="Hebrew"),
    SupportedLanguage(code="hi", name="Hindi"),
    SupportedLanguage(code="id", name="Indonesian"),
    SupportedLanguage(code="vi", name="Vietnamese"),
    SupportedLanguage(code="th", name="Thai"),
]
_LANG_BY_CODE = {item.code: item for item in SUPPORTED_LANGUAGES}


class XaiVoiceAgentError(RuntimeError):
    """Raised when the xAI voice-agent endpoint call fails."""


@dataclass
class _CachedResponse:
    provider: str
    message: str
    fallback_used: bool
    communication_style: str
    created_ms: int


class XaiVoiceAgent:
    """xAI-backed Theodore conversational responder with local fallback."""

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "https://api.x.ai/v1",
        model: str = "grok-4",
        fast_model: str = "grok-4",
        timeout_s: float = 25.0,
        fast_timeout_s: float = 6.0,
        cache_ttl_s: float = 20.0,
        max_history_turns: int = 4,
        max_cache_entries: int = 512,
        max_tracked_sessions: int = 512,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._fast_model = fast_model or model
        self._timeout_s = timeout_s
        self._fast_timeout_s = fast_timeout_s
        self._cache_ttl_ms = int(max(1.0, cache_ttl_s) * 1000)
        self._max_history_turns = max(1, max_history_turns)
        self._max_cache_entries = max(1, max_cache_entries)
        self._max_tracked_sessions = max(1, max_tracked_sessions)
        self._response_cache: dict[str, _CachedResponse] = {}
        self._session_history: dict[str, list[dict[str, str]]] = {}

    @classmethod
    def from_env(cls) -> XaiVoiceAgent:
        return cls(
            api_key=os.environ.get("XAI_API_KEY", ""),
            base_url=os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1"),
            model=os.environ.get("XAI_MODEL", "grok-4"),
            fast_model=os.environ.get("XAI_FAST_MODEL", os.environ.get("XAI_MODEL", "grok-4")),
            timeout_s=float(os.environ.get("XAI_TIMEOUT_S", "25")),
            fast_timeout_s=float(os.environ.get("XAI_FAST_TIMEOUT_S", "6")),
            cache_ttl_s=float(os.environ.get("XAI_CACHE_TTL_S", "20")),
            max_history_turns=int(os.environ.get("XAI_MAX_HISTORY_TURNS", "4")),
            max_cache_entries=int(os.environ.get("XAI_MAX_CACHE_ENTRIES", "512")),
            max_tracked_sessions=int(os.environ.get("XAI_MAX_TRACKED_SESSIONS", "512")),
        )

    @staticmethod
    def supported_languages() -> list[SupportedLanguage]:
        return list(SUPPORTED_LANGUAGES)

    def respond(
        self,
        *,
        learner_message: str,
        class_mode: ClassMode,
        language_code: str = "en",
        context: str = "",
        session_id: str = "",
        fast_mode: bool = True,
    ) -> VoiceResponse:
        started_ms = self._now_ms()
        language = self._resolve_language(language_code)
        learner_text = self._normalize_text(learner_message)
        context_text = self._normalize_text(context)
        session_key = self._normalize_text(session_id)
        history = self._history_for_session(session_key)
        cache_key = self._build_cache_key(
            session_id=session_key,
            learner_text=learner_text,
            class_mode=class_mode,
            language=language.code,
            context=context_text,
            fast_mode=fast_mode,
            history=history,
        )
        cached = self._get_cached(cache_key, now_ms=started_ms)
        if cached is not None:
            # A cached reply is still a real conversational turn: record it so the
            # session keeps a faithful history instead of silently skipping a turn.
            self._remember_turn(session_key, learner_text, cached.message)
            return VoiceResponse(
                provider=cached.provider,
                message=cached.message,
                communication_style=cached.communication_style,
                fallback_used=cached.fallback_used,
                latency_ms=self._elapsed_ms(started_ms),
                cache_hit=True,
                tts_voice_style="warm_clear",
                tts_engine_chain=["elevenlabs", "edge-tts", "device"],
                should_stream_audio=True,
            )
        prompt = self._build_prompt(
            learner_message=learner_text,
            class_mode=class_mode,
            language=language,
            context=context_text,
            history=history,
        )
        if not self._api_key:
            response = self._fallback_response(
                learner_message=learner_text,
                language_name=language.name,
                latency_ms=self._elapsed_ms(started_ms),
            )
            self._set_cached(cache_key, response, now_ms=started_ms)
            self._remember_turn(session_key, learner_text, response.message)
            return response

        payload = {
            "model": self._fast_model if fast_mode else self._model,
            "messages": prompt,
            "temperature": 0.45 if fast_mode else 0.55,
            "max_tokens": 140 if fast_mode else 240,
            "stream": False,
        }
        try:
            timeout_s = self._fast_timeout_s if fast_mode else self._timeout_s
            body = self._transport(payload, timeout_s=timeout_s)
            message = self._extract_message(body)
        except XaiVoiceAgentError:
            message = ""
        if not message:
            response = self._fallback_response(
                learner_message=learner_text,
                language_name=language.name,
                latency_ms=self._elapsed_ms(started_ms),
            )
            self._set_cached(cache_key, response, now_ms=started_ms)
            self._remember_turn(session_key, learner_text, response.message)
            return response

        response = VoiceResponse(
            provider="xai",
            message=message,
            communication_style="natural_conversational_realtime",
            fallback_used=False,
            latency_ms=self._elapsed_ms(started_ms),
            cache_hit=False,
            tts_voice_style="warm_clear",
            tts_engine_chain=["elevenlabs", "edge-tts", "device"],
            should_stream_audio=True,
        )
        self._set_cached(cache_key, response, now_ms=started_ms)
        self._remember_turn(session_key, learner_text, response.message)
        return response

    def ask_question(
        self,
        *,
        class_mode: ClassMode,
        language_code: str,
        topic: str,
        difficulty: str = "medium",
        context: str = "",
    ) -> VoiceQuestion:
        started_ms = self._now_ms()
        language = self._resolve_language(language_code)
        prompt = self._build_question_prompt(
            class_mode=class_mode,
            language=language,
            topic=topic,
            difficulty=difficulty,
            context=context,
        )
        if self._api_key:
            payload = {
                "model": self._model,
                "messages": prompt,
                "temperature": 0.6,
                "max_tokens": 280,
                "stream": False,
                "response_format": {"type": "json_object"},
            }
            try:
                body = self._transport(payload, timeout_s=self._fast_timeout_s)
                parsed = self._extract_json_message(body)
                if parsed:
                    question = (parsed.get("question") or "").strip()
                    hint = (parsed.get("hint") or "").strip()
                    if question:
                        return VoiceQuestion(
                            provider="xai",
                            language_code=language.code,
                            language_name=language.name,
                            question=question,
                            hint=hint or "Think about the key concept and answer briefly.",
                            fallback_used=False,
                            latency_ms=self._elapsed_ms(started_ms),
                        )
            except XaiVoiceAgentError:
                pass
        return self._fallback_question(
            language_code=language.code,
            language_name=language.name,
            topic=topic,
            difficulty=difficulty,
            latency_ms=self._elapsed_ms(started_ms),
        )

    def absorb_audio_answer(
        self,
        *,
        class_mode: ClassMode,
        language_code: str,
        question: str,
        audio_transcript: str,
        expected_answer: str = "",
        context: str = "",
    ) -> AudioAnswerAssessment:
        started_ms = self._now_ms()
        language = self._resolve_language(language_code)
        transcript = (audio_transcript or "").strip()
        if not transcript:
            return AudioAnswerAssessment(
                provider="local-fallback",
                language_code=language.code,
                language_name=language.name,
                absorbed_transcript="",
                understood=False,
                understanding_confidence=0.0,
                correctness_score=0.0,
                feedback_message="I could not hear your answer clearly. Please repeat.",
                follow_up_question=question,
                fallback_used=True,
                latency_ms=self._elapsed_ms(started_ms),
            )

        prompt = self._build_audio_assessment_prompt(
            class_mode=class_mode,
            language=language,
            question=question,
            transcript=transcript,
            expected_answer=expected_answer,
            context=context,
        )
        if self._api_key:
            payload = {
                "model": self._model,
                "messages": prompt,
                "temperature": 0.4,
                "max_tokens": 320,
                "stream": False,
                "response_format": {"type": "json_object"},
            }
            try:
                body = self._transport(payload, timeout_s=self._fast_timeout_s)
                parsed = self._extract_json_message(body)
                if parsed:
                    understood = bool(parsed.get("understood", True))
                    u_conf = self._clamp01(parsed.get("understanding_confidence", 0.7))
                    score = self._clamp01(parsed.get("correctness_score", 0.6))
                    feedback = (
                        str(parsed.get("feedback_message", "")).strip()
                        or "Good effort. Let's refine your answer."
                    )
                    follow_up = (
                        str(parsed.get("follow_up_question", "")).strip()
                        or "Can you add one more key detail?"
                    )
                    return AudioAnswerAssessment(
                        provider="xai",
                        language_code=language.code,
                        language_name=language.name,
                        absorbed_transcript=transcript,
                        understood=understood,
                        understanding_confidence=u_conf,
                        correctness_score=score,
                        feedback_message=feedback,
                        follow_up_question=follow_up,
                        fallback_used=False,
                        latency_ms=self._elapsed_ms(started_ms),
                    )
            except XaiVoiceAgentError:
                pass
        return self._fallback_audio_assessment(
            language_code=language.code,
            language_name=language.name,
            question=question,
            transcript=transcript,
            expected_answer=expected_answer,
            latency_ms=self._elapsed_ms(started_ms),
        )

    @staticmethod
    def _now_ms() -> int:
        return int(time.perf_counter() * 1000)

    def _elapsed_ms(self, started_ms: int) -> int:
        return max(0, self._now_ms() - started_ms)

    @staticmethod
    def _normalize_text(value: str) -> str:
        return (value or "").strip()

    def _history_for_session(self, session_id: str) -> list[dict[str, str]]:
        if not session_id:
            return []
        rows = self._session_history.get(session_id, [])
        if not rows:
            return []
        max_messages = self._max_history_turns * 2
        return list(rows[-max_messages:])

    def _remember_turn(
        self, session_id: str, learner_message: str, assistant_message: str
    ) -> None:
        if not session_id:
            return
        if not learner_message or not assistant_message:
            return
        bucket = self._session_history.setdefault(session_id, [])
        bucket.append({"role": "user", "content": learner_message})
        bucket.append({"role": "assistant", "content": assistant_message})
        max_messages = self._max_history_turns * 2
        if len(bucket) > max_messages:
            bucket = bucket[-max_messages:]
        # Re-insert so this session counts as most-recently used for eviction.
        self._session_history.pop(session_id, None)
        self._session_history[session_id] = bucket
        while len(self._session_history) > self._max_tracked_sessions:
            self._session_history.pop(next(iter(self._session_history)), None)

    @staticmethod
    def _build_cache_key(
        *,
        session_id: str,
        learner_text: str,
        class_mode: ClassMode,
        language: str,
        context: str,
        fast_mode: bool,
        history: list[dict[str, str]],
    ) -> str:
        payload = {
            # Scoped per session so one learner never receives another learner's reply.
            "session_id": session_id,
            "learner_text": learner_text,
            "class_mode": class_mode.value,
            "language": language,
            "context": context,
            "fast_mode": fast_mode,
            "history": history,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest()

    def _get_cached(self, key: str, *, now_ms: int) -> _CachedResponse | None:
        row = self._response_cache.get(key)
        if row is None:
            return None
        if now_ms - row.created_ms > self._cache_ttl_ms:
            self._response_cache.pop(key, None)
            return None
        return row

    def _set_cached(self, key: str, response: VoiceResponse, *, now_ms: int) -> None:
        self._response_cache[key] = _CachedResponse(
            provider=response.provider,
            message=response.message,
            fallback_used=response.fallback_used,
            communication_style=response.communication_style,
            created_ms=now_ms,
        )
        self._prune_cache(now_ms=now_ms)

    def _prune_cache(self, *, now_ms: int) -> None:
        """Drop expired entries eagerly, then cap the cache so it cannot grow forever."""
        expired = [
            key
            for key, row in self._response_cache.items()
            if now_ms - row.created_ms > self._cache_ttl_ms
        ]
        for key in expired:
            self._response_cache.pop(key, None)
        while len(self._response_cache) > self._max_cache_entries:
            self._response_cache.pop(next(iter(self._response_cache)), None)

    def _build_prompt(
        self,
        *,
        learner_message: str,
        class_mode: ClassMode,
        language: SupportedLanguage,
        context: str,
        history: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        system = (
            "You are Theodore, an educational AI teacher. Reply in clear, warm "
            "speech-ready language that sounds natural when spoken aloud. "
            f"Always reply in {language.name} (code: {language.code}). "
            "Keep feedback actionable and concise in 1-2 short sentences unless asked for more."
        )
        mode_text = "group class" if class_mode is ClassMode.GROUP else "solo session"
        user_parts = [
            f"Class mode: {mode_text}.",
            f"Learner says: {learner_message.strip()}",
        ]
        if context.strip():
            user_parts.append(f"Context: {context.strip()}")
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": " ".join(user_parts)})
        return messages

    def _build_question_prompt(
        self,
        *,
        class_mode: ClassMode,
        language: SupportedLanguage,
        topic: str,
        difficulty: str,
        context: str,
    ) -> list[dict[str, str]]:
        mode_text = "group class" if class_mode is ClassMode.GROUP else "solo session"
        system = (
            "You are Theodore, a multilingual teacher. Create one spoken question and "
            "one short hint in the requested language. Return strict JSON with keys "
            "question and hint."
        )
        user = (
            f"Language code: {language.code} ({language.name}). "
            f"Class mode: {mode_text}. Topic: {topic}. Difficulty: {difficulty}. "
            f"Context: {context.strip() or 'none'}."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _build_audio_assessment_prompt(
        self,
        *,
        class_mode: ClassMode,
        language: SupportedLanguage,
        question: str,
        transcript: str,
        expected_answer: str,
        context: str,
    ) -> list[dict[str, str]]:
        mode_text = "group class" if class_mode is ClassMode.GROUP else "solo session"
        system = (
            "You are Theodore, a multilingual assessor. Evaluate the learner transcript. "
            "Return strict JSON with keys: understood (bool), understanding_confidence "
            "(0..1), correctness_score (0..1), feedback_message (string), "
            "follow_up_question (string). Keep feedback concise and supportive."
        )
        user = (
            f"Language code: {language.code} ({language.name}). "
            f"Class mode: {mode_text}. Question: {question}. "
            f"Learner transcript: {transcript}. "
            f"Expected answer: {expected_answer or 'not provided'}. "
            f"Context: {context.strip() or 'none'}."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _transport(self, payload: dict, *, timeout_s: float | None = None) -> dict:
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
            with urllib.request.urlopen(
                req,
                timeout=(timeout_s if timeout_s is not None else self._timeout_s),
            ) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = ""
            with contextlib.suppress(Exception):
                detail = exc.read().decode("utf-8", errors="replace")[:200]
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

    @classmethod
    def _extract_json_message(cls, payload: dict) -> dict[str, Any] | None:
        raw = cls._extract_message(payload)
        if not raw:
            return None
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        return obj

    @staticmethod
    def _clamp01(value: Any) -> float:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return 0.0
        if num < 0.0:
            return 0.0
        if num > 1.0:
            return 1.0
        return num

    def _resolve_language(self, language_code: str) -> SupportedLanguage:
        code = (language_code or "").strip().lower()
        if code not in _LANG_BY_CODE:
            supported = ", ".join(item.code for item in SUPPORTED_LANGUAGES)
            raise ValueError(f"Unsupported language code '{language_code}'. Supported: {supported}")
        return _LANG_BY_CODE[code]

    @staticmethod
    def _fallback_response(
        *,
        learner_message: str,
        language_name: str,
        latency_ms: int = 0,
    ) -> VoiceResponse:
        cleaned = (learner_message or "").strip()
        if not cleaned:
            cleaned = "Let's begin by reviewing one clear learning goal."
        return VoiceResponse(
            provider="local-fallback",
            message=(
                f"[{language_name}] I hear you. We'll break this into one step at a time, "
                f"then I will check understanding after each step. First focus: {cleaned}"
            ),
            communication_style="natural_conversational_realtime",
            fallback_used=True,
            latency_ms=latency_ms,
            cache_hit=False,
            tts_voice_style="warm_clear",
            tts_engine_chain=["elevenlabs", "edge-tts", "device"],
            should_stream_audio=True,
        )

    @staticmethod
    def _fallback_question(
        *,
        language_code: str,
        language_name: str,
        topic: str,
        difficulty: str,
        latency_ms: int = 0,
    ) -> VoiceQuestion:
        q = (
            f"[{language_name}] In one or two sentences, explain: {topic}. "
            f"(difficulty: {difficulty})"
        )
        return VoiceQuestion(
            provider="local-fallback",
            language_code=language_code,
            language_name=language_name,
            question=q,
            hint=f"[{language_name}] Start with the main idea, then add one supporting detail.",
            fallback_used=True,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _fallback_audio_assessment(
        *,
        language_code: str,
        language_name: str,
        question: str,
        transcript: str,
        expected_answer: str,
        latency_ms: int = 0,
    ) -> AudioAnswerAssessment:
        words = [part for part in transcript.split() if part.strip()]
        understood = len(words) >= 3
        confidence = 0.85 if understood else 0.4
        score = 0.45
        if expected_answer.strip():
            expected_tokens = {
                token.strip(".,!?;:").lower()
                for token in expected_answer.split()
                if len(token.strip(".,!?;:")) >= 4
            }
            observed_tokens = {
                token.strip(".,!?;:").lower()
                for token in transcript.split()
                if len(token.strip(".,!?;:")) >= 4
            }
            if expected_tokens:
                overlap = len(expected_tokens & observed_tokens) / len(expected_tokens)
                score = min(1.0, max(0.0, 0.35 + overlap * 0.65))
            else:
                score = 0.6 if understood else 0.35
        elif understood:
            score = 0.65

        feedback = (
            f"[{language_name}] Good try. You answered: \"{transcript}\". "
            "Add one concrete detail to strengthen your response."
        )
        follow_up = (
            f"[{language_name}] Can you answer this again with one key example? "
            f"Question: {question}"
        )
        return AudioAnswerAssessment(
            provider="local-fallback",
            language_code=language_code,
            language_name=language_name,
            absorbed_transcript=transcript,
            understood=understood,
            understanding_confidence=confidence,
            correctness_score=score,
            feedback_message=feedback,
            follow_up_question=follow_up,
            fallback_used=True,
            latency_ms=latency_ms,
        )
