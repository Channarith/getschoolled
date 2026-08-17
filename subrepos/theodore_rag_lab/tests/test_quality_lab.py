"""Tests for RAG auto-tune lab."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from theodore_rag_lab.bakeoff_loop import RagBakeoffRunner
from theodore_rag_lab.eval_harness import build_demo_index, evaluate_index, load_golden
from theodore_rag_lab.main import app
from theodore_rag_lab.rag_tuning import RagTuning
import theodore_rag_lab.bakeoff_loop as bl


def test_tuning_presets_and_patch():
    t = RagTuning.preset("precision")
    assert t.top_k == 2
    t2 = t.patched({"top_k": 3})
    assert t2.top_k == 3
    with pytest.raises(ValueError):
        t.patched({"nope": 1})


def test_eval_demo_index_quality():
    index = build_demo_index()
    examples = load_golden()
    demo_ids = {"photosynthesis", "gravity", "python", "fractions", "supply_demand"}
    demo_ex = [
        e for e in examples if e.expected_doc_ids and e.expected_doc_ids[0] in demo_ids
    ] or examples[:3]
    report = evaluate_index(index, demo_ex, RagTuning(top_k=3, min_score=0.0))
    assert report.n >= 1
    assert report.recall_at_k > 0.0
    assert 0.0 <= report.rag_quality <= 1.0


def test_bakeoff_blocking_promotes_or_keeps():
    runner = RagBakeoffRunner()
    runner.index = build_demo_index()
    runner.examples = load_golden()[:5]
    runner._seed_champion()
    status = runner.run_blocking(hours=0.01)
    assert status["rounds_done"] >= 1
    assert "champion" in status
    assert status["telemetry"]["bakeoff_rounds"] >= 1
    assert status["telemetry"]["avg_rag_quality"] >= 0.0


def test_api_health_eval_train():
    bl._RUNNER = RagBakeoffRunner()
    bl._RUNNER.index = build_demo_index()
    bl._RUNNER.examples = load_golden()[:5]
    bl._RUNNER._seed_champion()

    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200
        assert h.json()["ok"] is True

        e = client.post("/api/rag/eval")
        assert e.status_code == 200
        assert "report" in e.json()

        p = client.post("/api/rag/tuning/preset/recall")
        assert p.status_code == 200
        assert p.json()["knobs"]["top_k"] == 5

        t = client.post("/api/rag/train/run-blocking", json={"hours": 0.01})
        assert t.status_code == 200
        assert t.json()["rounds_done"] >= 1

        c = client.get("/api/rag/champion")
        assert c.status_code == 200

        tel = client.get("/api/rag/telemetry")
        assert tel.status_code == 200
        assert "bakeoff_rounds" in tel.json()

        page = client.get("/")
        assert page.status_code == 200
        assert "Theodore RAG Lab" in page.text
        assert "/api/rag/eval" in page.text
        assert "Blocking bakeoff" in page.text
        lab = client.get("/lab")
        assert lab.status_code == 200
        assert "Manual qualification" in lab.text


def test_invalid_preset_404():
    bl._RUNNER = RagBakeoffRunner()
    with TestClient(app) as client:
        r = client.post("/api/rag/tuning/preset/not-a-real-preset")
        assert r.status_code == 404
