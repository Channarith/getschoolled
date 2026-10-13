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
    import torch

    raw = (os.environ.get("NLLB_DEVICE") or "").strip()
    if raw:
        return torch.device(raw)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


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
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            device = _torch_device()
            tok = AutoTokenizer.from_pretrained(model_id)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
            model.to(device)
            model.eval()
            _tokenizer = tok
            _model = model
        except Exception as exc:  # noqa: BLE001
            _load_error = f"NLLB load failed ({model_id}): {exc}"
            raise RuntimeError(_load_error) from exc
        return _tokenizer, _model


def translate_text(text: str, *, source: str, target: str) -> str:
    """Translate ``text`` from ``source`` to ``target`` (platform ISO codes)."""
    import torch

    clean = " ".join((text or "").split())
    if not clean:
        return ""
    src = flores_code(source)
    tgt = flores_code(target)
    if src == tgt:
        return clean
    tokenizer, model = _get_model()
    max_len = int(os.environ.get("NLLB_MAX_LENGTH") or "512")
    # NLLB tokenizers expose forced_bos via lang code conversion.
    if hasattr(tokenizer, "src_lang"):
        tokenizer.src_lang = src
    encoded = tokenizer(clean, return_tensors="pt", truncation=True, max_length=max_len)
    device = next(model.parameters()).device
    encoded = {k: v.to(device) for k, v in encoded.items()}
    bos = tokenizer.convert_tokens_to_ids(tgt)
    with torch.inference_mode():
        generated = model.generate(
            **encoded,
            forced_bos_token_id=bos,
            max_length=max_len,
        )
    return tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()
