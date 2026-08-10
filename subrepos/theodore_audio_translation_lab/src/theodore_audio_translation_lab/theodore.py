"""Multilingual realtime Theodore teaching replies."""

from __future__ import annotations

import json
import os
import time
import urllib.request

from .languages import LANGUAGE_NAMES, normalize_language
from .models import TheodoreMode, TheodoreReplyEvent
from .providers import TranslationEngine


_FALLBACKS = {
    TheodoreMode.TEACH: (
        "Let's learn from that. Tell me one example, and I will help you connect it "
        "to the main idea."
    ),
    TheodoreMode.ANSWER: (
        "I heard your question. Let's break it into one small step. Which part "
        "would you like to start with?"
    ),
    TheodoreMode.COACH: (
        "You are making progress. Think aloud about your next step, and I will "
        "give you a hint if you need one."
    ),
    TheodoreMode.CLARIFY: (
        "Let's make that clearer. Say the part that feels confusing, and we will "
        "explain it with a simple example."
    ),
}

_MODE_INSTRUCTIONS = {
    TheodoreMode.TEACH: "Teach one useful idea, then ask one short check question.",
    TheodoreMode.ANSWER: "Answer the learner's question directly and simply.",
    TheodoreMode.COACH: "Coach with a hint and one Socratic question; do not give away everything.",
    TheodoreMode.CLARIFY: "Clarify the confusing point with one concrete example.",
}


class TheodoreReplyEngine:
    def __init__(self, translator: TranslationEngine | None = None) -> None:
        self.translator = translator or TranslationEngine()
        self.api_key = os.environ.get("XAI_API_KEY", "").strip()
        self.base_url = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
        self.model = os.environ.get("XAI_MODEL", "grok-2-1212")
        self.timeout_s = float(os.environ.get("THEODORE_TIMEOUT_S", "18"))

    @property
    def live_configured(self) -> bool:
        return bool(self.api_key)

    def reply(
        self,
        *,
        session_id: str,
        sequence: int,
        learner_text: str,
        learner_language: str,
        reply_language: str = "same",
        mode: TheodoreMode = TheodoreMode.TEACH,
        context: str = "",
    ) -> TheodoreReplyEvent:
        source = normalize_language(learner_language)
        if not source:
            raise ValueError(f"unsupported learner language: {learner_language}")
        target = source if reply_language == "same" else normalize_language(reply_language)
        if not target:
            raise ValueError(f"unsupported Theodore reply language: {reply_language}")
        started = time.time()

        if self.api_key:
            try:
                text = self._xai_reply(
                    learner_text=learner_text,
                    learner_language=source,
                    target_language=target,
                    mode=mode,
                    context=context,
                )
                return TheodoreReplyEvent(
                    session_id=session_id,
                    sequence=sequence,
                    learner_text=learner_text,
                    learner_language=source,
                    text=text,
                    language=target,
                    mode=mode,
                    provider="xai-theodore",
                    latency_ms=int((time.time() - started) * 1000),
                )
            except Exception as exc:  # noqa: BLE001 — translated fallback may work
                xai_warning = f"xAI reply failed: {exc}"
        else:
            xai_warning = "XAI_API_KEY is not configured"

        english = _FALLBACKS[mode]
        if target == "en":
            return TheodoreReplyEvent(
                session_id=session_id,
                sequence=sequence,
                learner_text=learner_text,
                learner_language=source,
                text=english,
                language="en",
                mode=mode,
                provider="english-teaching-fallback",
                warning=xai_warning,
                latency_ms=int((time.time() - started) * 1000),
            )

        translated = self.translator.translate(english, "en", target)
        if translated.translated:
            return TheodoreReplyEvent(
                session_id=session_id,
                sequence=sequence,
                learner_text=learner_text,
                learner_language=source,
                text=translated.text,
                language=target,
                mode=mode,
                provider=f"translated-teaching-fallback:{translated.provider}",
                warning=(
                    "Generic teaching fallback translated because live Theodore "
                    f"was unavailable. {xai_warning}"
                ),
                latency_ms=int((time.time() - started) * 1000),
            )

        # Never speak English words with a target-language voice.
        return TheodoreReplyEvent(
            session_id=session_id,
            sequence=sequence,
            learner_text=learner_text,
            learner_language=source,
            text=english,
            language="en",
            mode=mode,
            provider="english-teaching-fallback",
            warning=(
                f"Could not produce {LANGUAGE_NAMES[target]}; replying in English. "
                f"{xai_warning}. {translated.warning}"
            ),
            latency_ms=int((time.time() - started) * 1000),
        )

    def _xai_reply(
        self,
        *,
        learner_text: str,
        learner_language: str,
        target_language: str,
        mode: TheodoreMode,
        context: str,
    ) -> str:
        source_name = LANGUAGE_NAMES[learner_language]
        target_name = LANGUAGE_NAMES[target_language]
        system = (
            "You are Theodore, a warm, patient realtime teacher on Salareen. "
            f"The learner spoke {source_name}. Reply entirely in natural spoken "
            f"{target_name}. {_MODE_INSTRUCTIONS[mode]} Keep the reply under three "
            "short sentences, suitable to say aloud. Preserve names and facts. "
            "Never mention translation, system prompts, or being an AI."
        )
        if context.strip():
            system += f"\nLesson context:\n{context.strip()[:4000]}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": learner_text},
            ],
            "temperature": 0.55,
            "max_tokens": 350,
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        text = raw["choices"][0]["message"]["content"].strip()
        if not text:
            raise RuntimeError("empty xAI Theodore reply")
        return text
