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
from .languages import (
    AUTO_LANGUAGE,
    LANGUAGE_NAMES,
    normalize_input_language,
    normalize_language,
    resolve_detected_language,
)
from .models import AudioTranscription, ProviderStatus, TranslationResult


class ProviderUnavailable(RuntimeError):
    pass


# xAI retired the grok-2 family from the API (grok-2-1212 was removed in January
# 2026), so calling it with a perfectly valid key returns a bare HTTP 400. Point
# at a current canonical model instead. grok-4.3 rather than the newer grok-4.5
# because 4.5 is not offered to EU API Console accounts, and a default has to
# work everywhere; override with XAI_MODEL to pick something else.
XAI_DEFAULT_MODEL = "grok-4.3"


def xai_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout_s: float,
) -> str:
    """POST an xAI chat completion and return the reply text.

    Raises ``ProviderUnavailable`` carrying xAI's own explanation. urllib's
    HTTPError stringifies as just "HTTP Error 400: Bad Request" and drops the
    response body, which is where xAI says things like "model X does not exist" —
    so a retired model default looked like an unexplained failure.
    """
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()[:400]
        except Exception:  # noqa: BLE001 - the status code is still worth reporting
            pass
        hint = ""
        if exc.code in {400, 404} and "model" in detail.lower():
            hint = (
                f" The configured model is '{model}'; set XAI_MODEL to a current "
                f"one (default is {XAI_DEFAULT_MODEL})."
            )
        raise ProviderUnavailable(
            f"xAI HTTP {exc.code} for model '{model}': {detail or exc.reason}{hint}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ProviderUnavailable(f"xAI unreachable: {exc.reason}") from exc

    try:
        return (raw["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderUnavailable(f"unexpected xAI response shape: {raw}") from exc


class TranslationEngine:
    def __init__(self) -> None:
        self.gateway_url = (
            os.environ.get("TRANSLATION_BASE_URL")
            or os.environ.get("SPEECH_BASE_URL")
            or ""
        ).rstrip("/")
        self.xai_key = os.environ.get("XAI_API_KEY", "").strip()
        self.xai_url = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
        self.xai_model = os.environ.get("XAI_MODEL", "").strip() or XAI_DEFAULT_MODEL
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
        messages = [
            {
                "role": "system",
                "content": (
                    f"Translate spoken {source_name} into natural {target_name}. "
                    "Preserve meaning, names, tone, and questions. Return only the "
                    "translation, with no explanation."
                ),
            },
            {"role": "user", "content": text},
        ]
        translated = xai_chat(
            base_url=self.xai_url,
            api_key=self.xai_key,
            model=self.xai_model,
            messages=messages,
            temperature=0.1,
            max_tokens=800,
            timeout_s=self.timeout_s,
        )
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
        language = normalize_input_language(language)
        if not language:
            raise ValueError("unsupported ASR language")
        auto_detect = language == AUTO_LANGUAGE
        fields = {
            "model": self.model,
            # verbose_json asks compatible Whisper servers to return detected language.
            "response_format": "verbose_json" if auto_detect else "json",
        }
        if not auto_detect:
            fields["language"] = language

        boundary = f"----aoep-{uuid.uuid4().hex}"
        body = _multipart(
            boundary,
            fields=fields,
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
        detected_default = "" if auto_detect else language
        detected = resolve_detected_language(
            str(raw.get("language") or ""), default=detected_default
        )
        if not detected:
            raise ProviderUnavailable(
                "Whisper auto-detect did not return a supported language; "
                "use verbose_json or choose an input language manually."
            )
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

    # Imported here: tts imports this module for ProviderUnavailable.
    from .tts import engine_chain

    chain = engine_chain()
    if chain:
        notes.append(f"Theodore speaks server-side via {' → '.join(chain)}.")
    else:
        notes.append(
            "No server TTS; Theodore uses the device voice. Set TTS_BASE_URL/"
            "SPEECH_BASE_URL, ELEVENLABS_API_KEY, or install edge-tts for neural audio."
        )
    return ProviderStatus(
        remote_asr_configured=asr.configured,
        remote_asr_url=asr.base_url,
        translation_gateway_configured=bool(mt.gateway_url),
        translation_gateway_url=mt.gateway_url,
        xai_translation_configured=bool(mt.xai_key),
        xai_model=mt.xai_model if mt.xai_key else "",
        server_tts_configured=bool(chain),
        server_tts_engine=chain[0] if chain else "",
        notes=notes,
    )


# Curated common classroom phrases across en/es/fr/zh/km. Each row is one
# concept with display-cased text per language; the flat lookup table below is
# generated for every directed language pair so short spoken phrases translate
# instantly even with no MT provider configured.
_PHRASE_TABLE: list[dict[str, str]] = [
    {"en": "Hello", "es": "Hola", "fr": "Bonjour", "zh": "你好", "km": "សួស្តី"},
    {"en": "Goodbye", "es": "Adiós", "fr": "Au revoir", "zh": "再见", "km": "លាហើយ"},
    {"en": "Yes", "es": "Sí", "fr": "Oui", "zh": "是的", "km": "បាទ"},
    {"en": "No", "es": "No", "fr": "Non", "zh": "不是", "km": "ទេ"},
    {"en": "Thank you", "es": "Gracias", "fr": "Merci", "zh": "谢谢", "km": "អរគុណ"},
    {"en": "Please", "es": "Por favor", "fr": "S'il vous plaît", "zh": "请", "km": "សូម"},
    {
        "en": "Good morning",
        "es": "Buenos días",
        "fr": "Bonjour",
        "zh": "早上好",
        "km": "អរុណសួស្តី",
    },
    {
        "en": "I need help",
        "es": "Necesito ayuda",
        "fr": "J'ai besoin d'aide",
        "zh": "我需要帮助",
        "km": "ខ្ញុំត្រូវការជំនួយ",
    },
    {
        "en": "I don't understand",
        "es": "No entiendo",
        "fr": "Je ne comprends pas",
        "zh": "我不明白",
        "km": "ខ្ញុំមិនយល់ទេ",
    },
    {
        "en": "Can you repeat that",
        "es": "¿Puede repetir?",
        "fr": "Pouvez-vous répéter",
        "zh": "你能再说一遍吗",
        "km": "សូមនិយាយម្តងទៀត",
    },
    {
        "en": "I have a question",
        "es": "Tengo una pregunta",
        "fr": "J'ai une question",
        "zh": "我有一个问题",
        "km": "ខ្ញុំមានសំណួរ",
    },
    {
        "en": "Please wait",
        "es": "Por favor espere",
        "fr": "Veuillez patienter",
        "zh": "请稍等",
        "km": "សូមរង់ចាំ",
    },
    {
        "en": "Well done",
        "es": "Bien hecho",
        "fr": "Bien joué",
        "zh": "做得好",
        "km": "ល្អណាស់",
    },
]


def _phrase_key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).casefold().rstrip(".!?")


def _build_phrasebook() -> dict[tuple[str, str, str], str]:
    book: dict[tuple[str, str, str], str] = {}
    for row in _PHRASE_TABLE:
        for source, source_text in row.items():
            for target, target_text in row.items():
                if source == target:
                    continue
                book[(source, target, _phrase_key(source_text))] = target_text
    return book


_PHRASEBOOK: dict[tuple[str, str, str], str] = _build_phrasebook()
