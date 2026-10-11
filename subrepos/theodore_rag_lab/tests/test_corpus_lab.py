"""Dictionary corpus + read-aloud APIs in the Theodore RAG lab."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "shared"
    / "tests"
    / "fixtures"
    / "dictionary"
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_DICTIONARY_DIR", str(tmp_path / "dictionary"))
    # Reset feedback singleton if any
    import aoep_shared.dictionary_feedback as df

    df._STORE = None
    from theodore_rag_lab.main import app

    return TestClient(app)


def test_health_lists_corpus_features(client):
    r = client.get("/health")
    assert r.status_code == 200
    feats = r.json()["features"]
    assert "dictionary_corpus" in feats
    assert "read_aloud" in feats
    assert "corpus" in r.json()


def test_corpus_train_update_and_read_aloud(client, tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_DICTIONARY_DIR", str(tmp_path / "dictionary"))
    upd = client.post("/api/corpus/train-update", json={"force": True, "language": "en"})
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["ingest"]["en"] > 0
    stats = client.get("/api/corpus/stats").json()
    assert stats["languages"]["en"]["total"] > 0

    nxt = client.post(
        "/api/read-aloud/next",
        json={"language": "en", "learner_id": "lab-test", "seed": 3},
    )
    assert nxt.status_code == 200, nxt.text
    prompt = nxt.json()
    assert prompt["sentence"]
    forms = [t["form"] for t in prompt["targets"]]
    scored = client.post(
        "/api/read-aloud/score",
        json={
            "sentence": prompt["sentence"],
            "heard": prompt["sentence"],
            "target_forms": forms,
            "language": "en",
            "learner_id": "lab-test",
        },
    )
    assert scored.status_code == 200
    assert scored.json()["score"] >= 50

    llm = client.post("/api/corpus/export-llm")
    assert llm.status_code == 200
    assert llm.json()["examples"] >= 1
    assert Path(llm.json()["path"]).is_file()


def test_corpus_review_list(client, tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_DICTIONARY_DIR", str(tmp_path / "d2"))
    client.post("/api/corpus/train-update", json={"force": True})
    rev = client.get("/api/corpus/review?limit=10")
    assert rev.status_code == 200
    assert "entries" in rev.json()
