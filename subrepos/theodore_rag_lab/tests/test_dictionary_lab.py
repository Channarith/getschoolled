"""Tests for dictionary / dialect / regurgitation / feedback in the RAG lab."""

from __future__ import annotations

import os
from pathlib import Path

import theodore_rag_lab.bakeoff_loop as bl
from fastapi.testclient import TestClient

from aoep_shared.dialect import DIALECTS, normalize_dialect
from aoep_shared.slang import default_lexicon, lexicon_stats
from theodore_rag_lab.bakeoff_loop import RagBakeoffRunner
from theodore_rag_lab.eval_harness import build_demo_index, load_golden
from theodore_rag_lab.main import app


REQUIRED_DIALECTS = {
    "us_south",
    "us_ny",
    "us_ne",
    "us_ca",
    "en_ca",
    "en_gb",
    "en_au",
    "en_sg",
    "zh_bj",
    "zh_sh",
    "zh_yue_gz",
    "zh_min_fj",
}


def test_world_dialects_registered():
    assert REQUIRED_DIALECTS <= set(DIALECTS)
    assert normalize_dialect("singaporean") == "en_sg"
    assert normalize_dialect("beijing") == "zh_bj"
    assert normalize_dialect("cantonese") == "zh_yue_gz"
    assert normalize_dialect("fujianese") == "zh_min_fj"
    assert normalize_dialect("newyork") == "us_ny"
    assert normalize_dialect("new_england") == "us_ne"


def test_lexicon_is_extensive():
    stats = lexicon_stats()
    assert stats["total"] >= 300
    assert stats["from_packs"] >= 250
    regions = set(stats["regions"])
    for need in ("us-south", "us-ny", "us-ne", "sg", "cn-bj", "cn-sh", "cn-gz", "cn-fj", "ca", "au", "uk"):
        assert need in regions, need


def test_dictionary_and_dialect_apis(tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_FEEDBACK_DIR", str(tmp_path / "fb"))
    # Reset feedback singleton
    import aoep_shared.slang_feedback as sf
    import aoep_shared.slang as slang_mod

    sf._STORE = None
    slang_mod._default = None

    bl._RUNNER = RagBakeoffRunner()
    bl._RUNNER.index = build_demo_index()
    bl._RUNNER.examples = load_golden()[:5]
    bl._RUNNER._seed_champion()

    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200
        body = h.json()
        assert body["ok"] is True
        assert body["lexicon_total"] >= 300
        assert "dictionary" in body["features"]
        assert "regurgitation" in body["features"]
        assert "feedback_learning" in body["features"]

        d = client.get("/api/dictionary", params={"region": "us-south", "limit": 20})
        assert d.status_code == 200
        assert d.json()["count"] >= 5

        cat = client.get("/api/dialects")
        assert cat.status_code == 200
        ids = {row["id"] for row in cat.json()["dialects"]}
        assert REQUIRED_DIALECTS <= ids

        probe = client.post(
            "/api/dialects/probe",
            json={"dialect": "en_sg", "text": "Welcome! We will walk through the lesson."},
        )
        assert probe.status_code == 200
        assert "lah" in probe.json()["humanized"].lower() or "go through" in probe.json()["humanized"].lower()

        bj = client.post("/api/dialects/probe", json={"dialect": "zh_bj", "text": "Welcome"})
        assert bj.status_code == 200
        assert bj.json()["dialect"]["id"] == "zh_bj"

        deck = client.get("/api/regurgitate/deck", params={"dialect": "us_south", "n": 5})
        assert deck.status_code == 200
        cards = deck.json()["cards"]
        assert len(cards) >= 3
        card = cards[0]
        # Look up meaning and grade a strong answer
        entry = default_lexicon().lookup(card["phrase"], language=card["language"], region=card["region"])
        assert entry is not None
        grade = client.post(
            "/api/regurgitate/grade",
            json={
                "phrase": card["phrase"],
                "answer": entry.meaning,
                "language": card["language"],
                "region": card["region"],
                "dialect": "us_south",
                "learn": True,
            },
        )
        assert grade.status_code == 200
        assert grade.json()["ok"] is True
        assert grade.json()["score"] >= 0.45

        fb = client.post(
            "/api/feedback",
            json={
                "phrase": "lab only phrase xyz",
                "meaning": "a test-only idiom meaning",
                "language": "en",
                "region": "global",
                "action": "correct",
            },
        )
        assert fb.status_code == 200
        assert fb.json()["stats"]["learned_entries"] >= 1

        snap = client.get("/api/feedback")
        assert snap.status_code == 200
        assert snap.json()["stats"]["events"] >= 1

        page = client.get("/")
        assert page.status_code == 200
        assert "Dictionary" in page.text
        assert "Regurgitation" in page.text
        assert "Feedback learning" in page.text
        assert "Beijing" in page.text or "zh_bj" in page.text
