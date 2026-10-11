"""Local ASR for utterance transcripts (faster-whisper) with offline degrade."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_MODEL = "base"


@dataclass
class TranscriptResult:
    text: str
    language: str
    engine: str
    ok: bool
    reason: str = ""


def asr_model_name() -> str:
    return (
        os.environ.get("AOEP_ASR_MODEL")
        or os.environ.get("WHISPER_MODEL")
        or os.environ.get("FASTER_WHISPER_MODEL")
        or DEFAULT_MODEL
    )


def asr_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def transcribe_wav(
    path: Path | str,
    *,
    language: str = "en",
    model: Optional[str] = None,
    compute_type: Optional[str] = None,
) -> TranscriptResult:
    """Transcribe a WAV with faster-whisper when installed.

    Offline / missing-dep degradation: returns empty text with ``ok=False`` and
    an honest ``reason`` (never invents captions).
    """
    wav = Path(path)
    if not wav.is_file():
        return TranscriptResult("", language, "none", False, "missing_wav")

    if not asr_available():
        return TranscriptResult(
            "",
            language,
            "none",
            False,
            "faster_whisper_unavailable; pip install -e 'packages/shared[cosyvoice-ingest]'",
        )

    model_name = model or asr_model_name()
    ctype = compute_type or os.environ.get("AOEP_ASR_COMPUTE_TYPE", "int8")
    device = os.environ.get("AOEP_ASR_DEVICE", "cpu")
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # pragma: no cover
        return TranscriptResult("", language, "none", False, f"import_failed:{exc}")

    try:
        engine = WhisperModel(model_name, device=device, compute_type=ctype)
        segments, info = engine.transcribe(
            str(wav),
            language=language or None,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        parts = []
        for seg in segments:
            t = (seg.text or "").strip()
            if t:
                parts.append(t)
        text = " ".join(parts).strip()
        detected = getattr(info, "language", None) or language
        if not text:
            return TranscriptResult("", str(detected), f"faster-whisper:{model_name}", False, "empty_transcript")
        return TranscriptResult(text, str(detected), f"faster-whisper:{model_name}", True, "ok")
    except Exception as exc:
        return TranscriptResult("", language, f"faster-whisper:{model_name}", False, f"asr_error:{exc}")
