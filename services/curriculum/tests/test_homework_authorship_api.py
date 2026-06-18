"""POST /homework/authorship (Phase 8)."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def test_authorship_endpoint():
    text = (
        "The mitochondria produces energy for the cell. "
        "The nucleus stores the genetic material safely. "
        "The ribosome assembles proteins from amino acids."
    )
    body = client.post("/homework/authorship", json={"text": text}).json()
    assert body["label"] in ("ai", "human", "uncertain")
    assert 0.0 <= body["ai_probability"] <= 1.0
    assert "signals" in body and "note" in body


def test_authorship_handwritten_flag():
    body = client.post(
        "/homework/authorship", json={"text": "Short note here about cells and energy.", "handwritten": True}
    ).json()
    assert body["signals"]["handwritten"] == 1.0
