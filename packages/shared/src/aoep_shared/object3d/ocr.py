"""Read text off a sign crop. Optional: uses Tesseract when it is installed."""

from __future__ import annotations

import numpy as np


def read_sign_text(rgb: np.ndarray) -> str:
    """Return OCR text, or an empty string when no OCR engine is installed."""
    image = np.asarray(rgb)
    if image.size == 0:
        return ""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    try:
        text = pytesseract.image_to_string(Image.fromarray(image[:, :, :3]))
    except Exception:
        return ""
    return " ".join(text.split())
