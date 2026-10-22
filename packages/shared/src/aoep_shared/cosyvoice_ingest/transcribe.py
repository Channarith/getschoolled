"""Local ASR for utterance transcripts (faster-whisper) with offline degrade."""

from __future__ import annotations

import gc
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .guard import available_mb, env_int, is_memory_error


DEFAULT_MODEL = "base"

# One model per (engine, name, device, compute) for the process. Loading
# large-v3 once per utterance makes a channel unusable.
_MODEL_CACHE: Dict[Tuple[str, str, str, str], Any] = {}
_MODEL_LOCK = threading.Lock()
_FASTER_WHISPER_CUDA_BROKEN = False


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
        return True
    except Exception:
        pass
    try:
        import whisper  # noqa: F401
        return True
    except Exception:
        return False


def release_asr_models() -> None:
    """Drop cached ASR weights so a memory error does not stick until the next kill."""
    with _MODEL_LOCK:
        _MODEL_CACHE.clear()
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        return


def _memory_blocked(floor_name: str, default: int) -> bool:
    floor = env_int(floor_name, default)
    if floor <= 0:
        return False
    free = available_mb()
    return free is not None and free < floor


def _oom_result(language: str, engine: str) -> TranscriptResult:
    release_asr_models()
    return TranscriptResult("", language, engine, False, "oom")


def _cache_get(key: Tuple[str, str, str, str], factory):
    with _MODEL_LOCK:
        engine = _MODEL_CACHE.get(key)
        if engine is None:
            engine = factory()
            _MODEL_CACHE[key] = engine
        return engine


def _openai_engine(model_name: str, device: str):
    def factory():
        import whisper

        return whisper.load_model(model_name, device=device)

    return _cache_get(("openai-whisper", model_name, device, "fp16" if device == "cuda" else "fp32"), factory)


def _faster_engine(model_name: str, device: str, compute_type: str):
    def factory():
        from faster_whisper import WhisperModel

        threads = int(os.environ.get("AOEP_ASR_CPU_THREADS", "0") or 0)
        return WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=threads,
        )

    return _cache_get(("faster-whisper", model_name, device, compute_type), factory)


def _detect_language_whisper(wav: Path, model_name: str) -> Optional[str]:
    """Top Whisper language for a clip, or None when detection is unavailable."""
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        import whisper

        engine = _openai_engine(model_name, "cuda")
        audio = whisper.load_audio(str(wav))
        mel = whisper.log_mel_spectrogram(
            whisper.pad_or_trim(audio), n_mels=engine.dims.n_mels
        ).to(engine.device)
        _, probs = engine.detect_language(mel)
        return max(probs, key=probs.get) if probs else None
    except Exception:  # noqa: BLE001
        return None


def _transcribe_mms_khmer(wav: Path) -> Optional[TranscriptResult]:
    """Meta MMS (facebook/mms-1b-all, khm adapter) for Khmer speech.

    Whisper invents Khmer-looking text over real Khmer speech. MMS was trained
    for Khmer. Returns None when the weights are unavailable so callers fall back.
    Opt in with AOEP_ASR_KM_ENGINE=mms.
    """
    try:
        import torch
        from transformers import AutoProcessor, Wav2Vec2ForCTC

        def factory():
            processor = AutoProcessor.from_pretrained("facebook/mms-1b-all")
            model = Wav2Vec2ForCTC.from_pretrained("facebook/mms-1b-all", torch_dtype=torch.float32)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = model.to(device)
            processor.tokenizer.set_target_lang("khm")
            model.load_adapter("khm")
            return (processor, model, device)

        processor, model, device = _cache_get(("mms", "facebook/mms-1b-all", "khm", "fp32"), factory)
        import whisper

        audio = whisper.load_audio(str(wav))
        if len(audio) < 1600:
            return TranscriptResult("", "km", "mms-1b-all:khm", False, "too_short")
        inputs = processor(audio, sampling_rate=16000, return_tensors="pt")
        inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}
        with torch.no_grad():
            logits = model(**inputs).logits
        text = processor.batch_decode(torch.argmax(logits, dim=-1))[0].strip()
        if not text:
            return TranscriptResult("", "km", "mms-1b-all:khm", False, "empty_transcript")
        return TranscriptResult(text, "km", "mms-1b-all:khm", True, "ok")
    except MemoryError:
        return _oom_result("km", "mms-1b-all:khm")
    except Exception as exc:  # noqa: BLE001 — fall back to Whisper on any MMS failure
        if is_memory_error(str(exc)):
            return _oom_result("km", "mms-1b-all:khm")
        return None


def _transcribe_openai(wav: Path, *, language: str, model_name: str, device: str) -> TranscriptResult:
    if device == "cuda":
        try:
            import torch

            if not torch.cuda.is_available():
                return TranscriptResult("", language, "openai-whisper", False, "cuda_unavailable")
        except Exception as exc:
            return TranscriptResult("", language, "openai-whisper", False, f"import_failed:{exc}")
    try:
        engine = _openai_engine(model_name, device)
        result = engine.transcribe(
            str(wav),
            language=language or None,
            fp16=device == "cuda",
            condition_on_previous_text=False,
        )
    except MemoryError:
        return _oom_result(language, f"openai-whisper:{model_name}")
    except Exception as exc:
        if is_memory_error(str(exc)):
            return _oom_result(language, f"openai-whisper:{model_name}")
        return TranscriptResult("", language, f"openai-whisper:{model_name}", False, f"asr_error:{exc}")
    text = str((result or {}).get("text") or "").strip()
    detected = str((result or {}).get("language") or language)
    if not text:
        return TranscriptResult("", detected, f"openai-whisper:{model_name}", False, "empty_transcript")
    return TranscriptResult(text, detected, f"openai-whisper:{model_name}", True, "ok")


def _transcribe_faster(
    wav: Path, *, language: str, model_name: str, device: str, compute_type: str
) -> Optional[TranscriptResult]:
    """Return None when CUDA faster-whisper cannot run, so the caller can fall back."""
    global _FASTER_WHISPER_CUDA_BROKEN
    if device == "cuda" and _FASTER_WHISPER_CUDA_BROKEN:
        return None
    try:
        engine = _faster_engine(model_name, device, compute_type)
        segments, info = engine.transcribe(
            str(wav),
            language=language or None,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        parts = []
        for seg in segments:
            piece = (seg.text or "").strip()
            if piece:
                parts.append(piece)
        text = " ".join(parts).strip()
        detected = getattr(info, "language", None) or language
        if not text:
            return TranscriptResult("", str(detected), f"faster-whisper:{model_name}", False, "empty_transcript")
        return TranscriptResult(text, str(detected), f"faster-whisper:{model_name}", True, "ok")
    except MemoryError:
        return _oom_result(language, f"faster-whisper:{model_name}")
    except Exception as exc:
        message = str(exc)
        if is_memory_error(message):
            return _oom_result(language, f"faster-whisper:{model_name}")
        if device == "cuda" and "cuda" in message.lower():
            _FASTER_WHISPER_CUDA_BROKEN = True
            return None
        return TranscriptResult("", language, f"faster-whisper:{model_name}", False, f"asr_error:{exc}")


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

    if _memory_blocked("AOEP_ASR_MIN_FREE_MB", 0):
        return TranscriptResult("", language, "none", False, "low_memory")

    if not asr_available():
        return TranscriptResult(
            "",
            language,
            "none",
            False,
            "faster_whisper_unavailable; pip install -e 'packages/shared[cosyvoice-ingest]'",
        )

    model_name = model or asr_model_name()
    # Khmer-native speech: MMS transcribes it; Whisper invents it. English
    # lessons inside the Khmer pool stay on Whisper after language detection.
    if (language or "").lower() in {"km", "khm"} and os.environ.get("AOEP_ASR_KM_ENGINE", "").strip().lower() == "mms":
        # Whisper plus MMS is two large models. Under the single-model floor,
        # trust the pool language and load only MMS.
        if _memory_blocked("AOEP_ASR_SINGLE_MODEL_MB", 0):
            detected: Optional[str] = "km"
        else:
            detected = _detect_language_whisper(wav, model_name)
        if detected in (None, "km", "khm"):
            mms_result = _transcribe_mms_khmer(wav)
            if mms_result is not None and (mms_result.ok or mms_result.reason == "oom"):
                return mms_result
    if os.environ.get("AOEP_ASR_DETECT_LANGUAGE", "").strip().lower() in {"1", "true", "yes"}:
        language = ""

    ctype = compute_type or os.environ.get("AOEP_ASR_COMPUTE_TYPE", "int8")
    device = os.environ.get("AOEP_ASR_DEVICE", "cpu").strip().lower() or "cpu"
    engine_name = os.environ.get("AOEP_ASR_ENGINE", "faster-whisper").strip().lower()
    if engine_name in {"openai", "openai-whisper", "whisper", "gpu"}:
        openai_device = "cuda" if device == "cuda" else device
        return _transcribe_openai(wav, language=language, model_name=model_name, device=openai_device)

    faster = _transcribe_faster(
        wav, language=language, model_name=model_name, device=device, compute_type=ctype
    )
    if faster is not None:
        return faster
    # This machine's CTranslate2 build has no CUDA. Use torch Whisper instead of
    # failing every segment.
    return _transcribe_openai(wav, language=language, model_name=model_name, device=device)
