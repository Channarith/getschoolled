"""Curriculum validation endpoints (offline mock engine)."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def test_validate_claim_endpoint():
    r = client.post("/validate/claim", json={"text": "plants release oxygen during photosynthesis"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("supported", "unverified", "contradicted")
    assert body["engines_consulted"] >= 1


def test_validate_deck_endpoint():
    # Author a deck, then validate it.
    deck = client.post(
        "/decks",
        json={"title": "Bio", "slides": [
            {"title": "Photosynthesis", "body": "Plants release oxygen during photosynthesis."}]},
    ).json()
    r = client.post(f"/decks/{deck['deck_id']}/validate")
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["deck_id"] == deck["deck_id"]
    assert rep["total"] >= 1
    assert "verdicts" in rep and "flagged" in rep


def test_validate_unknown_deck_404():
    assert client.post("/decks/nope/validate").status_code == 404
