"""Correction apply / back-propagation tests."""

import json

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def _approved(payload: dict) -> str:
    cid = client.post("/corrections", json=payload).json()["id"]
    client.post(f"/corrections/{cid}/approve")
    return cid


def test_apply_requires_approval():
    cid = client.post("/corrections", json={"corrected": "x"}).json()["id"]
    assert client.post(f"/corrections/{cid}/apply").status_code == 409


def test_apply_patches_deck_slide():
    deck = client.post("/decks", json={
        "title": "Bio", "slides": [{"title": "S1", "body": "wrong fact"}]}).json()
    cid = _approved({"target_kind": "deck", "target_id": deck["deck_id"],
                     "locator": "0", "corrected": "Plants release oxygen."})
    r = client.post(f"/corrections/{cid}/apply")
    assert r.status_code == 200, r.text
    assert r.json()["patched"] == "deck"
    # Deck content now reflects the correction.
    updated = client.get(f"/decks/{deck['deck_id']}").json()
    assert updated["slides"][0]["body"] == "Plants release oxygen."
    assert client.get(f"/corrections/{cid}").json()["status"] == "applied"


def test_apply_model_emits_gold_example(tmp_path, monkeypatch):
    out = tmp_path / "corrections.jsonl"
    monkeypatch.setenv("CORRECTIONS_JSONL", str(out))
    cid = _approved({"target_kind": "model", "locator": "what gas do plants release?",
                     "corrected": "Plants release oxygen.",
                     "audience": {"language": "en", "race": "X"}})
    r = client.post(f"/corrections/{cid}/apply")
    assert r.status_code == 200, r.text
    assert r.json()["emitted"] == "training_example"
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert rows[-1]["reward"] == 1.0
    assert rows[-1]["response"] == "Plants release oxygen."
    assert "race" not in rows[-1]["context"]  # fairness guardrail


def test_apply_bad_slide_index_422():
    deck = client.post("/decks", json={"title": "D", "slides": [{"title": "s", "body": "b"}]}).json()
    cid = _approved({"target_kind": "deck", "target_id": deck["deck_id"],
                     "locator": "9", "corrected": "x"})
    assert client.post(f"/corrections/{cid}/apply").status_code == 422
