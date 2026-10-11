"""API tests for /learn/read-aloud/* dictionary pronunciation trainer."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from speech_gw.main import app

FIXTURES = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "shared"
    / "tests"
    / "fixtures"
    / "dictionary"
)

client = TestClient(app)


@pytest.fixture()
def seeded_dictionary(tmp_path, monkeypatch):
    root = tmp_path / "dictionary"
    monkeypatch.setenv("AOEP_DICTIONARY_DIR", str(root))
    from aoep_shared.dictionary_corpus import (
        ensure_layout,
        ingest_from_baseline_dir,
        merge_entries,
        route_entries,
        save_staging,
    )
    from aoep_shared.dictionary_curriculum import build_curriculum, save_sentences

    ensure_layout(root)
    b = root / "baselines"
    b.mkdir(parents=True, exist_ok=True)
    for p in FIXTURES.iterdir():
        if p.is_file():
            (b / p.name).write_bytes(p.read_bytes())
    entries = merge_entries(ingest_from_baseline_dir(b))
    auto, queued = route_entries(entries)
    all_rows = []
    for e in auto + queued:
        if e.language == "en":
            e.review_status = "approved"
            all_rows.append(e)
    save_staging(all_rows, root, "en")
    sentences = build_curriculum(all_rows, language="en", per_difficulty=5, seed=3)
    save_sentences(sentences, root, "en")
    return root


def test_read_aloud_next_and_score(seeded_dictionary):
    nxt = client.post(
        "/learn/read-aloud/next",
        json={"language": "en", "learner_id": "api-tester", "seed": 7},
    )
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert body["sentence"]
    forms = [t["form"] for t in body["targets"]]

    scored = client.post(
        "/learn/read-aloud/score",
        json={
            "language": "en",
            "learner_id": "api-tester",
            "sentence": body["sentence"],
            "heard": body["sentence"],
            "target_forms": forms,
        },
    )
    assert scored.status_code == 200
    data = scored.json()
    assert data["score"] >= 50
    assert "feedback" in data


def test_read_aloud_unsupported_language():
    r = client.post("/learn/read-aloud/next", json={"language": "zz"})
    assert r.status_code == 404
