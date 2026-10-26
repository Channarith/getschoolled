"""Speech provider implementations.

local  -> Whisper large-v3 (ASR), NLLB-200 (translation), XTTS-v2 (TTS).
cloud  -> the same models on GPU pods, plus a cloud-TTS fallback for languages
          open voices do not cover.

The 26-language support and the TTS fallback policy live here so callers get a
single, mode-agnostic SpeechProvider.
"""

from __future__ import annotations

from ..config import AppConfig
from ..languages import SUPPORTED_LANGUAGES, tts_needs_fallback
from .base import Audio, ProviderInfo, SpeechProvider, Transcript


class _BaseSpeechProvider(SpeechProvider):
    impl = "speech"

    def __init__(self, config: AppConfig, *, mode: str) -> None:
        self._config = config
        self._mode = mode
        self._base_url = config.speech_base_url

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability,
            mode=self._mode,
            impl=self.impl,
            endpoint=self._base_url,
        )

    def transcribe(self, audio_object_key: str) -> Transcript:
        raise NotImplementedError(
            "ASR model not loaded in this environment; configure the speech "
            "gateway (Whisper) via SPEECH_BASE_URL."
        )

    def translate(self, text: str, *, source: str, target: str) -> str:
        for lang in (source, target):
            # yue is Cantonese (yue_Hant), not a 27-language platform code
            # and not an alias of Mandarin.
            if lang not in SUPPORTED_LANGUAGES and lang != "yue":
                raise ValueError(f"Unsupported language: {lang}")
        # Prefer in-process NLLB when transformers weights are available
        # (local Spark / GPU). Falls through to NotImplementedError so the
        # speech gateway can try phrasebook then honest passthrough.
        from ..devices import DevicePolicyError

        try:
            from ..nllb import translate_text

            return translate_text(text, source=source, target=target)
        except DevicePolicyError:
            raise  # CUDA is required here: surface it, never degrade to a phrasebook or passthrough
        except Exception as exc:  # noqa: BLE001
            raise NotImplementedError(
                f"Translation model (NLLB-200) not loaded: {exc}"
            ) from exc

    def synthesize(self, text: str, *, language: str, voice: str) -> Audio:
        if language not in SUPPORTED_LANGUAGES and language != "yue":
            raise ValueError(f"Unsupported language: {language}")
        # Policy decision (synchronous, no model needed) so it is testable:
        # which engine should render this language?
        self.tts_engine(language)
        raise NotImplementedError(
            "TTS engine not loaded in this environment; configure XTTS (local) "
            "or the cloud-TTS fallback."
        )

    def tts_engine(self, language: str) -> str:
        """Return the TTS engine that should render ``language``.

        Open voices (XTTS) do not cover every one of the 26 languages, so some
        fall back to a cloud TTS engine regardless of deploy mode.
        """
        if language == "yue":
            return "cloud-tts-fallback"
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")
        return "cloud-tts-fallback" if tts_needs_fallback(language) else "xtts"


class LocalSpeechProvider(_BaseSpeechProvider):
    impl = "whisper-nllb-xtts-local"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="local")


class CloudSpeechProvider(_BaseSpeechProvider):
    impl = "whisper-nllb-xtts-cloud"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="cloud")
