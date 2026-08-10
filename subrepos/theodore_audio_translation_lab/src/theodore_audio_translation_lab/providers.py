"""Real provider adapters with honest offline degradation.

ASR supports an OpenAI-compatible Whisper endpoint (for vLLM/faster-whisper,
OpenAI, Groq, etc.). Translation prefers the AOEP speech gateway's NLLB endpoint,
then xAI text translation, then a tiny offline phrasebook. It never fabricates a
transcript or claims an untranslated sentence was translated.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from collections import OrderedDict
from .languages import LANGUAGE_NAMES, normalize_language
from .models import AudioTranscription, ProviderStatus, TranslationResult


class ProviderUnavailable(RuntimeError):
    pass


class TranslationEngine:
    def __init__(self) -> None:
        self.gateway_url = (
            os.environ.get("TRANSLATION_BASE_URL")
            or os.environ.get("SPEECH_BASE_URL")
            or ""
        ).rstrip("/")
        self.xai_key = os.environ.get("XAI_API_KEY", "").strip()
        self.xai_url = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
        self.xai_model = os.environ.get("XAI_MODEL", "grok-2-1212")
        self.timeout_s = float(os.environ.get("TRANSLATION_TIMEOUT_S", "15"))
        self._cache: OrderedDict[tuple[str, str, str], TranslationResult] = OrderedDict()
        self._cache_max = 1000

    def translate(self, text: str, source: str, target: str) -> TranslationResult:
        source = normalize_language(source)
        target = normalize_language(target)
        if not source or not target:
            raise ValueError(f"unsupported language pair: {source}->{target}")
        clean = re.sub(r"\s+", " ", (text or "").strip())
        if not clean:
            raise ValueError("translation text is empty")
        if source == target:
            return TranslationResult(
                text=clean,
                source_language=source,
                target_language=target,
                provider="identity",
                translated=False,
            )

        key = (source, target, clean)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached.model_copy(update={"provider": f"{cached.provider}:cache", "latency_ms": 0})

        started = time.time()
        errors: list[str] = []
        result: TranslationResult | None = None

        if self.gateway_url:
            try:
                result = self._gateway_translate(clean, source, target)
            except Exception as exc:  # noqa: BLE001 — next provider may work
                errors.append(f"gateway: {exc}")

        if result is None and self.xai_key:
            try:
                result = self._xai_translate(clean, source, target)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"xai: {exc}")

        if result is None:
            phrase = _PHRASEBOOK.get((source, target, clean.casefold().rstrip(".!?")))
            if phrase is not None:
                result = TranslationResult(
                    text=phrase,
                    source_language=source,
                    target_language=target,
                    provider="offline-phrasebook",
                    translated=True,
                    warning="Limited offline phrasebook; configure NLLB or xAI for open speech.",
                )

        if result is None:
            result = TranslationResult(
                text=clean,
                source_language=source,
                target_language=target,
                provider="source-fallback",
                translated=False,
                warning=(
                    "Translation unavailable; showing source text. Configure "
                    "TRANSLATION_BASE_URL/SPEECH_BASE_URL (NLLB) or XAI_API_KEY."
                    + (f" Provider errors: {'; '.join(errors)}" if errors else "")
                ),
            )

        result.latency_ms = int((time.time() - started) * 1000)
        self._remember(key, result)
        return result

    def _remember(self, key: tuple[str, str, str], result: TranslationResult) -> None:
        self._cache[key] = result
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

    def _gateway_translate(self, text: str, source: str, target: str) -> TranslationResult:
        payload = json.dumps({"text": text, "source": source, "target": target}).encode()
        req = urllib.request.Request(
            f"{self.gateway_url}/translate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        translated = str(raw.get("text") or "").strip()
        if not translated:
            raise ProviderUnavailable("empty NLLB translation")
        return TranslationResult(
            text=translated,
            source_language=source,
            target_language=target,
            provider="speech-gateway-nllb",
            translated=True,
        )

    def _xai_translate(self, text: str, source: str, target: str) -> TranslationResult:
        source_name = LANGUAGE_NAMES[source]
        target_name = LANGUAGE_NAMES[target]
        body = {
            "model": self.xai_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"Translate spoken {source_name} into natural {target_name}. "
                        "Preserve meaning, names, tone, and questions. Return only the "
                        "translation, with no explanation."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
            "max_tokens": 800,
        }
        req = urllib.request.Request(
            f"{self.xai_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.xai_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        translated = raw["choices"][0]["message"]["content"].strip()
        if not translated:
            raise ProviderUnavailable("empty xAI translation")
        return TranslationResult(
            text=translated,
            source_language=source,
            target_language=target,
            provider="xai",
            translated=True,
        )


class ASREngine:
    """OpenAI-compatible Whisper client. Audio is kept in memory and never stored."""

    def __init__(self) -> None:
        self.base_url = os.environ.get("ASR_BASE_URL", "").rstrip("/")
        self.endpoint = os.environ.get("ASR_PATH", "/v1/audio/transcriptions")
        self.api_key = os.environ.get("ASR_API_KEY", "").strip()
        self.model = os.environ.get("ASR_MODEL", "whisper-large-v3")
        self.timeout_s = float(os.environ.get("ASR_TIMEOUT_S", "45"))
        self.max_bytes = int(os.environ.get("ASR_MAX_AUDIO_BYTES", str(8 * 1024 * 1024)))

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def transcribe(
        self,
        audio: bytes,
        *,
        filename: str,
        content_type: str,
        language: str,
    ) -> AudioTranscription:
        if not self.configured:
            raise ProviderUnavailable(
                "Remote ASR is not configured. Set ASR_BASE_URL to an "
                "OpenAI-compatible Whisper endpoint, or use browser recognition."
            )
        if not audio:
            raise ValueError("audio chunk is empty")
        if len(audio) > self.max_bytes:
            raise ValueError(f"audio chunk exceeds {self.max_bytes} bytes")
        language = normalize_language(language)
        if not language:
            raise ValueError("unsupported ASR language")

        boundary = f"----aoep-{uuid.uuid4().hex}"
        body = _multipart(
            boundary,
            fields={"model": self.model, "language": language, "response_format": "json"},
            file_field="file",
            filename=filename or "audio.webm",
            content_type=content_type or "audio/webm",
            payload=audio,
        )
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.base_url}{self.endpoint}", data=body, headers=headers, method="POST"
        )
        started = time.time()
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        text = str(raw.get("text") or "").strip()
        if not text:
            raise ProviderUnavailable("Whisper returned no transcript")
        detected = normalize_language(str(raw.get("language") or language), default=language)
        return AudioTranscription(
            text=text,
            language=detected,
            confidence=float(raw.get("confidence") or 0.0),
            provider=f"openai-compatible:{self.model}",
            duration_ms=int((time.time() - started) * 1000),
            raw={k: v for k, v in raw.items() if k not in {"text"}},
        )


def _multipart(
    boundary: str,
    *,
    fields: dict[str, str],
    file_field: str,
    filename: str,
    content_type: str,
    payload: bytes,
) -> bytes:
    crlf = b"\r\n"
    out: list[bytes] = []
    for name, value in fields.items():
        out.extend(
            [
                f"--{boundary}".encode(),
                f'Content-Disposition: form-data; name="{name}"'.encode(),
                b"",
                value.encode(),
            ]
        )
    out.extend(
        [
            f"--{boundary}".encode(),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{filename}"'
            ).encode(),
            f"Content-Type: {content_type}".encode(),
            b"",
            payload,
            f"--{boundary}--".encode(),
            b"",
        ]
    )
    return crlf.join(out)


def provider_status() -> ProviderStatus:
    asr = ASREngine()
    mt = TranslationEngine()
    notes = [
        "Browser ASR uses the device/browser recognizer and sends transcript text only.",
        "Audio chunks are ephemeral; the lab does not persist raw microphone audio.",
    ]
    if not asr.configured:
        notes.append("Set ASR_BASE_URL for server-side Whisper audio transcription.")
    if not mt.gateway_url and not mt.xai_key:
        notes.append("Set TRANSLATION_BASE_URL/SPEECH_BASE_URL (NLLB) or XAI_API_KEY.")
    return ProviderStatus(
        remote_asr_configured=asr.configured,
        remote_asr_url=asr.base_url,
        translation_gateway_configured=bool(mt.gateway_url),
        translation_gateway_url=mt.gateway_url,
        xai_translation_configured=bool(mt.xai_key),
        notes=notes,
    )


_PHRASEBOOK: dict[tuple[str, str, str], str] = {
    ("en", "es", "hello"): "Hola",
    ("en", "es", "yes"): "Sí",
    ("en", "es", "no"): "No",
    ("en", "es", "i need help"): "Necesito ayuda",
    ("es", "en", "hola"): "Hello",
    ("es", "en", "sí"): "Yes",
    ("es", "en", "necesito ayuda"): "I need help",
    ("en", "zh", "hello"): "你好",
    ("en", "zh", "i need help"): "我需要帮助",
    ("zh", "en", "你好"): "Hello",
    ("zh", "en", "我需要帮助"): "I need help",
    ("en", "km", "hello"): "សួស្តី",
    ("en", "km", "i need help"): "ខ្ញុំត្រូវការជំនួយ",
    ("km", "en", "សួស្តី"): "Hello",
    ("km", "en", "ខ្ញុំត្រូវការជំនួយ"): "I need help",
}
