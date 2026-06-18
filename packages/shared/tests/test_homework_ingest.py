"""OCR provider + homework ingest tests (Phase 7)."""

from aoep_shared.config import AppConfig, DeployMode
from aoep_shared.factory import ProviderFactory
from aoep_shared.homework import ocr_to_submission, segment_answers
from aoep_shared.providers.ocr import MockOcrProvider


def test_mock_ocr_typed_vs_handwritten():
    ocr = MockOcrProvider()
    typed = ocr.read(b"Photosynthesis makes glucose.")
    assert typed.text == "Photosynthesis makes glucose."
    assert typed.handwritten is False and typed.confidence == 1.0

    hand = ocr.read(b"messy handwriting", hint="handwritten")
    assert hand.handwritten is True and hand.confidence < 1.0


def test_segment_numbered_answers():
    text = "1. Plants make glucose.\n2. Cells use oxygen.\n3) Chlorophyll is green."
    segs = segment_answers(text)
    assert len(segs) == 3
    assert "glucose" in segs[0]


def test_segment_blank_line_fallback():
    text = "First answer here.\n\nSecond answer here."
    segs = segment_answers(text)
    assert len(segs) == 2


def test_ocr_to_submission():
    res = MockOcrProvider().read(b"1. a\n2. b", hint="handwritten")
    sub = ocr_to_submission(res)
    assert sub.handwritten is True
    assert len(sub.segments) == 2


def test_factory_ocr_local_defaults_to_mock_without_tesseract():
    # No tesseract binary in CI -> local OCR falls back to the offline mock.
    fac = ProviderFactory(AppConfig(deploy_mode=DeployMode.LOCAL))
    ocr = fac.ocr()
    assert ocr.info().capability == "ocr"
    # MockOcrProvider decodes bytes; confirm it reads.
    assert ocr.read(b"hello").text == "hello"
