"""POST /homework/scan (Phase 7) - offline via MockOcrProvider."""

import io

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def test_scan_typed_submission():
    f = io.BytesIO(b"1. Plants release oxygen.\n2. Cells use glucose.")
    res = client.post(
        "/homework/scan",
        files={"file": ("hw.txt", f, "text/plain")},
    ).json()
    assert "Plants release oxygen" in res["raw_text"]
    assert res["handwritten"] is False
    assert len(res["segments"]) == 2


def test_scan_handwritten_hint():
    f = io.BytesIO(b"handwritten answer about fractions")
    res = client.post(
        "/homework/scan",
        files={"file": ("hw.png", f, "image/png")},
        data={"hint": "handwritten"},
    ).json()
    assert res["handwritten"] is True
    assert res["confidence"] < 1.0
