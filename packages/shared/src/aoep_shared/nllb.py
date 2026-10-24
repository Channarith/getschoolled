"""Local NLLB-200 translation (free, self-hosted).

Lazy-loads ``facebook/nllb-200-distilled-600M`` (override with ``NLLB_MODEL``).
Used by the speech gateway ``SpeechProvider.translate`` so batch course
translation does not need xAI.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

# ISO 639-1 (platform) → FLORES-200 codes used by NLLB-200.
_FLORES: dict[str, str] = {
    "en": "eng_Latn",
    "es": "spa_Latn",
    "fr": "fra_Latn",
    "de": "deu_Latn",
    "it": "ita_Latn",
    "pt": "por_Latn",
    "nl": "nld_Latn",
    "pl": "pol_Latn",
    "ru": "rus_Cyrl",
    "uk": "ukr_Cyrl",
    "tr": "tur_Latn",
    "ar": "arb_Arab",
    "he": "heb_Hebr",
    "hi": "hin_Deva",
    "bn": "ben_Beng",
    "ur": "urd_Arab",
    "fa": "pes_Arab",
    "zh": "zho_Hans",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
    "vi": "vie_Latn",
    "th": "tha_Thai",
    "id": "ind_Latn",
    "sw": "swh_Latn",
    "el": "ell_Grek",
    "cs": "ces_Latn",
    "km": "khm_Khmr",
}

_lock = threading.Lock()
_model = None
_tokenizer = None
_load_error: Optional[str] = None


def flores_code(language: str) -> str:
    code = (language or "").strip().lower()
    if code not in _FLORES:
        raise ValueError(f"no NLLB FLORES mapping for language {language!r}")
    return _FLORES[code]


def nllb_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        import sentencepiece  # noqa: F401
    except ImportError:
        return False
    return True


def _torch_device():
    """Device under the host policy (aoep_shared.devices): CUDA on the Spark, never a silent CPU there."""
    import torch

    from .devices import pick_device

    return torch.device(pick_device("nllb", os.environ.get("NLLB_DEVICE")))


def _model_dtype(device):
    """bf16 on CUDA by default (NLLB_DTYPE=fp16|bf16|fp32 overrides); fp32 elsewhere."""
    import torch

    if getattr(device, "type", str(device)) != "cuda":
        return torch.float32
    raw = (os.environ.get("NLLB_DTYPE") or "bf16").strip().lower()
    return {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}.get(raw, torch.bfloat16)


def _get_model():
    """Lazy-load tokenizer + seq2seq model (transformers v5 has no translation pipeline)."""
    global _model, _tokenizer, _load_error
    with _lock:
        if _model is not None and _tokenizer is not None:
            return _tokenizer, _model
        if _load_error:
            raise RuntimeError(_load_error)
        if not nllb_available():
            _load_error = (
                "NLLB deps missing; pip install transformers sentencepiece torch"
            )
            raise RuntimeError(_load_error)
        model_id = (
            os.environ.get("NLLB_MODEL") or "facebook/nllb-200-distilled-600M"
        ).strip()
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            device = _torch_device()
            tok = AutoTokenizer.from_pretrained(model_id)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_id, torch_dtype=_model_dtype(device))
            model.to(device)
            model.eval()
            _tokenizer = tok
            _model = model
        except Exception as exc:  # noqa: BLE001
            from .devices import DevicePolicyError

            if isinstance(exc, DevicePolicyError):
                raise  # not cached: fixing the install and retrying must work
            _load_error = f"NLLB load failed ({model_id}): {exc}"
            raise RuntimeError(_load_error) from exc
        return _tokenizer, _model


def _inference_ctx():
    try:
        import torch

        return torch.inference_mode()
    except ImportError:  # tests with fake models run without torch
        import contextlib

        return contextlib.nullcontext()


def nllb_status() -> dict:
    """Device actually in use and whether the CUDA policy is met (for /health). Does not load the model."""
    from .devices import device_status

    device = None
    if _model is not None:
        device = next(_model.parameters()).device.type
    status = device_status(device or "not-loaded")
    status["model_loaded"] = _model is not None
    status["load_error"] = _load_error
    return status


def translate_batch(
    texts: list[str],
    *,
    source: str,
    target: str,
    batch_size: Optional[int] = None,
    num_beams: Optional[int] = None,
) -> list[str]:
    """Translate many segments per generate() call, longest-first so padding stays small.

    The GPU only pays off when it is fed batches; one segment per call leaves it idle.
    Order of the result matches ``texts``. Empty segments stay empty.
    """
    src = flores_code(source)
    tgt = flores_code(target)
    cleaned = [" ".join((x or "").split()) for x in texts]
    if src == tgt:
        return cleaned
    tokenizer, model = _get_model()
    max_len = int(os.environ.get("NLLB_MAX_LENGTH") or "512")
    batch = int(batch_size or os.environ.get("NLLB_BATCH_SIZE") or "16")
    beams = int(num_beams or os.environ.get("NLLB_NUM_BEAMS") or "4")
    if hasattr(tokenizer, "src_lang"):
        tokenizer.src_lang = src
    bos = tokenizer.convert_tokens_to_ids(tgt)
    device = next(model.parameters()).device
    order = sorted((i for i, c in enumerate(cleaned) if c), key=lambda i: -len(cleaned[i]))
    out = [""] * len(cleaned)
    for start in range(0, len(order), max(1, batch)):
        idx = order[start : start + max(1, batch)]
        encoded = tokenizer(
            [cleaned[i] for i in idx], return_tensors="pt", truncation=True, max_length=max_len, padding=True
        )
        encoded = {k: v.to(device) for k, v in encoded.items()}
        with _inference_ctx():
            generated = model.generate(**encoded, forced_bos_token_id=bos, max_length=max_len, num_beams=beams)
        for i, text in zip(idx, tokenizer.batch_decode(generated, skip_special_tokens=True)):
            out[i] = text.strip()
    return out


def translate_text(text: str, *, source: str, target: str) -> str:
    """Translate ``text`` from ``source`` to ``target`` (platform ISO codes)."""
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    return translate_batch([clean], source=source, target=target)[0]
