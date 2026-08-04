from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
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
    ) -> VoiceResponse:
        language = self._resolve_language(language_code)
        prompt = self._build_prompt(
            learner_message=learner_message,
            class_mode=class_mode,
            language=language,
            context=context,
        )
        if not self._api_key:
            return self._fallback_response(
                learner_message=learner_message,
                language_code=language.code,
                language_name=language.name,
            )

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
            return self._fallback_response(
                learner_message=learner_message,
                language_code=language.code,
                language_name=language.name,
            )

        return VoiceResponse(
            provider="xai",
            message=message,
            communication_style="natural_conversational",
            fallback_used=False,
        )

    def ask_question(
        self,
        *,
        class_mode: ClassMode,
        language_code: str,
        topic: str,
        difficulty: str = "medium",
        context: str = "",
    ) -> VoiceQuestion:
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
                body = self._transport(payload)
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
                        )
            except XaiVoiceAgentError:
                pass
        return self._fallback_question(
            language_code=language.code,
            language_name=language.name,
            topic=topic,
            difficulty=difficulty,
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
                body = self._transport(payload)
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
                    )
            except XaiVoiceAgentError:
                pass
        return self._fallback_audio_assessment(
            language_code=language.code,
            language_name=language.name,
            question=question,
            transcript=transcript,
            expected_answer=expected_answer,
        )

    def _build_prompt(
        self,
        *,
        learner_message: str,
        class_mode: ClassMode,
        language: SupportedLanguage,
        context: str,
    ) -> list[dict[str, str]]:
        system = (
            "You are Theodore, an educational AI teacher. Reply in clear, warm "
            "speech-ready language that sounds natural when spoken aloud. "
            f"Always reply in {language.name} (code: {language.code}). "
            "Keep feedback actionable and concise."
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
            f"Learner transcript: {transcript}. Expected answer: {expected_answer or 'not provided'}. "
            f"Context: {context.strip() or 'none'}."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

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
        *, learner_message: str, language_code: str, language_name: str
    ) -> VoiceResponse:
        cleaned = (learner_message or "").strip()
        if not cleaned:
            cleaned = "Let's begin by reviewing one clear learning goal."
        return VoiceResponse(
            provider="local-fallback",
            message=(
                f"[{language_name}] I hear you. We'll break this into one step at a time, then I will "
                f"check understanding after each step. First focus: {cleaned}"
            ),
            communication_style="natural_conversational",
            fallback_used=True,
        )

    @staticmethod
    def _fallback_question(
        *,
        language_code: str,
        language_name: str,
        topic: str,
        difficulty: str,
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
        )

    @staticmethod
    def _fallback_audio_assessment(
        *,
        language_code: str,
        language_name: str,
        question: str,
        transcript: str,
        expected_answer: str,
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
        )
