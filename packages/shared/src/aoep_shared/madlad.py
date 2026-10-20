"""Local MADLAD-400 translation (free, self-hosted).

The default checkpoint is ``google/madlad400-10b-mt``, the largest model in
the MADLAD-400 family. The "400" is the language count, not the parameter
count. Set ``MADLAD_MODEL`` to a smaller cut (``google/madlad400-3b-mt``) when
the 10B weights are not on disk. Downloads stay off unless
``TRANSLATION_ALLOW_DOWNLOAD=1``.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from .nllb import allow_weight_download, nllb_available

# Largest MADLAD-400 machine-translation checkpoint.
MADLAD_MAX_MODEL = "google/madlad400-10b-mt"

# Platform ISO code -> MADLAD target tag. The model expects ``<2xx>`` in front
# of the source text. Codes follow the model's ISO set.
_TAGS: dict[str, str] = {
    "en": "en",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "pt": "pt",
    "nl": "nl",
    "pl": "pl",
    "ru": "ru",
    "uk": "uk",
    "tr": "tr",
    "ar": "ar",
    "he": "he",
    "hi": "hi",
    "bn": "bn",
    "ur": "ur",
    "fa": "fa",
    "zh": "zh",
    "ja": "ja",
    "ko": "ko",
    "vi": "vi",
    "th": "th",
    "id": "id",
    "sw": "sw",
    "el": "el",
    "cs": "cs",
    "km": "km",
    "yue": "yue",
    "tl": "tl",
}

_lock = threading.Lock()
_model = None
_tokenizer = None
_load_error: Optional[str] = None


def model_id() -> str:
    return (os.environ.get("MADLAD_MODEL") or MADLAD_MAX_MODEL).strip()


def target_tag(language: str) -> str:
    code = (language or "").strip().lower()
    if code not in _TAGS:
        raise ValueError(f"no MADLAD tag for language {language!r}")
    return f"<2{_TAGS[code]}>"


def prompt_for(text: str, target: str) -> str:
    return f"{target_tag(target)} {text}"


def _torch_device():
    import torch

    raw = (os.environ.get("MADLAD_DEVICE") or os.environ.get("NLLB_DEVICE") or "").strip()
    if raw:
        return torch.device(raw)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _get_model():
    global _model, _tokenizer, _load_error
    with _lock:
        if _model is not None and _tokenizer is not None:
            return _tokenizer, _model
        if _load_error:
            raise RuntimeError(_load_error)
        if not nllb_available():
            _load_error = "MADLAD deps missing; pip install transformers sentencepiece torch"
            raise RuntimeError(_load_error)
        chosen = model_id()
        try:
            from transformers import T5ForConditionalGeneration, T5Tokenizer

            device = _torch_device()
            local_only = not allow_weight_download()
            tok = T5Tokenizer.from_pretrained(chosen, local_files_only=local_only)
            model = T5ForConditionalGeneration.from_pretrained(
                chosen, local_files_only=local_only
            )
            model.to(device)
            model.eval()
            _tokenizer = tok
            _model = model
        except Exception as exc:  # noqa: BLE001
            _load_error = f"MADLAD load failed ({chosen}): {exc}"
            raise RuntimeError(_load_error) from exc
        return _tokenizer, _model


def translate_text(text: str, *, source: str, target: str) -> str:
    """Translate ``text`` into ``target``. ``source`` is accepted for the shared call shape."""
    import torch

    del source  # MADLAD is many-to-many from the target tag alone.
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    tokenizer, model = _get_model()
    max_len = int(os.environ.get("MADLAD_MAX_LENGTH") or os.environ.get("NLLB_MAX_LENGTH") or "512")
    encoded = tokenizer(
        prompt_for(clean, target),
        return_tensors="pt",
        truncation=True,
        max_length=max_len,
    )
    device = next(model.parameters()).device
    encoded = {key: value.to(device) for key, value in encoded.items()}
    with torch.inference_mode():
        generated = model.generate(**encoded, max_length=max_len)
    return tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()
