"""OCR providers for homework scanning (Phase 7).

- MockOcrProvider: deterministic, offline (decodes UTF-8 bytes as the "scanned"
  text); powers tests and no-OCR runs.
- LocalOcrProvider: Tesseract via lazy pytesseract (typed text; weak on
  handwriting). Used when a tesseract binary is available.
- CloudOcrProvider: cloud handwriting OCR (Azure/Google Vision) behind config;
  raises until configured.

Network/binary use is import-guarded so importing this module is always safe.
"""

from __future__ import annotations

from typing import Optional

from ..config import AppConfig
from .base import OcrProvider, OcrResult, ProviderInfo


class MockOcrProvider(OcrProvider):
    impl = "mock-ocr"

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config

    def info(self) -> ProviderInfo:
        return ProviderInfo(capability=self.capability, mode="local", impl=self.impl,
                            endpoint="mock://ocr")

    def read(self, content: bytes, *, hint: Optional[str] = None) -> OcrResult:
        try:
            text = content.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            text = ""
        handwritten = hint == "handwritten"
        # Simulated handwriting recognition is less confident than typed OCR.
        confidence = 0.7 if handwritten else 1.0
        return OcrResult(text=text.strip(), handwritten=handwritten, confidence=confidence)


class LocalOcrProvider(OcrProvider):
    impl = "tesseract"

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config

    def info(self) -> ProviderInfo:
        return ProviderInfo(capability=self.capability, mode="local", impl=self.impl,
                            endpoint="local://tesseract")

    def read(self, content: bytes, *, hint: Optional[str] = None) -> OcrResult:
        import io

        import pytesseract  # lazy; requires the tesseract binary
        from PIL import Image

        image = Image.open(io.BytesIO(content))
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        words = [w for w in data.get("text", []) if w.strip()]
        confs = [int(c) for c in data.get("conf", []) if str(c).lstrip("-").isdigit() and int(c) >= 0]
        confidence = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        return OcrResult(
            text=" ".join(words), handwritten=(hint == "handwritten"),
            confidence=round(confidence, 3), blocks=words,
        )


class CloudOcrProvider(OcrProvider):
    impl = "cloud-ocr"

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config

    def info(self) -> ProviderInfo:
        return ProviderInfo(capability=self.capability, mode="cloud", impl=self.impl,
                            endpoint=getattr(self._config, "ocr_endpoint", None))

    def ready(self) -> bool:
        return bool(getattr(self._config, "ocr_api_key", "") if self._config else "")

    def read(self, content: bytes, *, hint: Optional[str] = None) -> OcrResult:
        if not self.ready():
            raise NotImplementedError("OCR_API_KEY not configured for CloudOcrProvider")
        raise NotImplementedError("cloud OCR backend not wired in this build")
