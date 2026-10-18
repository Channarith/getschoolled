"""Planner tests for the small-model RAG eval. No weights and no GPU."""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "subrepos" / "theodore_rag_lab" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

rag_eval = importlib.import_module("rag_small_evals")


def _row(name, rank, f1, ground, reference=False):
    block = {
        "n": 16,
        "answer_f1": f1,
        "groundedness": ground,
        "rag_quality": 0.5,
        "recall_at_k": 1.0,
        "latency_ms_avg": 10.0,
    }
    return {
        "name": name,
        "params": name,
        "size_rank": rank,
        "reference": reference,
        "ok": True,
        "original": dict(block),
        "extended": dict(block),
    }


def test_parse_host_port_and_backend():
    specs = rag_eval.parse_model_list(
        "qwen2.5-0.5b@10.0.0.8:18001, custom-7b@18042, qwen3.6-35b-a3b",
        host="127.0.0.1",
        port=8342,
        backend="auto",
        reference="qwen3.6-35b-a3b",
    )
    assert [spec.name for spec in specs] == ["qwen2.5-0.5b", "custom-7b", "qwen3.6-35b-a3b"]
    assert specs[0].kind == "hf"
    assert (specs[0].host, specs[0].port) == ("10.0.0.8", 18001)
    assert specs[1].kind == "http"
    assert (specs[1].host, specs[1].port) == ("127.0.0.1", 18042)
    assert specs[2].reference is True
    assert specs[2].port == 8342

    forced = rag_eval.parse_model_list(
        "qwen2.5-1.5b",
        host="127.0.0.1",
        port=18100,
        backend="http",
        reference="none",
    )
    assert forced[0].kind == "http"
    assert forced[0].port == 18100
    assert forced[0].size_rank == 2


def test_recommend_smallest_within_margin():
    rows = [
        _row("qwen2.5-0.5b", 1, 0.40, 0.40),
        _row("qwen2.5-1.5b", 2, 0.70, 0.72),
        _row("qwen2.5-3b", 3, 0.74, 0.74),
        _row("qwen3.6-35b-a3b", 5, 0.75, 0.75, reference=True),
    ]
    advice = rag_eval.recommend(rows, 0.05)
    assert advice["model"] == "qwen2.5-1.5b"
    assert advice["within_margin"] is True
    assert advice["reference"] == "qwen3.6-35b-a3b"


def test_high_f1_cannot_hide_ungrounded_answers():
    rows = [
        _row("qwen2.5-1.5b", 2, 0.70, 0.50),
        _row("qwen2.5-3b", 3, 0.50, 0.78),
        _row("qwen3.6-35b-a3b", 5, 0.50, 0.80, reference=True),
    ]
    advice = rag_eval.recommend(rows, 0.05)
    assert advice["model"] == "qwen2.5-3b"
    assert advice["within_margin"] is True
    assert advice["gap"] <= 0.05
    weak = rows[0]
    ref = rows[2]
    assert rag_eval.quality_gap(weak, ref) > 0.05


def test_recommend_when_nothing_is_close():
    rows = [
        _row("qwen2.5-0.5b", 1, 0.10, 0.10),
        _row("qwen2.5-3b", 3, 0.20, 0.20),
        _row("qwen3.6-35b-a3b", 5, 0.80, 0.80, reference=True),
    ]
    advice = rag_eval.recommend(rows, 0.05)
    assert advice["model"] == "qwen2.5-3b"
    assert advice["within_margin"] is False


def test_strip_thinking_and_messages_stay_local():
    text = rag_eval.strip_thinking("<think>hidden chain</think>Plants use sunlight.")
    assert text == "Plants use sunlight."
    messages = rag_eval.build_messages("what is gravity", ["Gravity pulls objects."])
    blob = " ".join(item["content"] for item in messages)
    assert "Gravity pulls objects." in blob
    assert "what is gravity" in blob
    assert "API_KEY" not in blob
    assert "sk-" not in blob


def test_dry_run_reports_original_and_extended(tmp_path):
    code = rag_eval.main(
        [
            "--models",
            "qwen2.5-0.5b,qwen3.6-35b-a3b",
            "--dry-run",
            "--out",
            str(tmp_path),
            "--skip-fetch",
        ]
    )
    assert code == 0
    summary = list(tmp_path.glob("*/summary.json"))
    assert len(summary) == 1
    payload = __import__("json").loads(summary[0].read_text(encoding="utf-8"))
    by_name = {row["name"]: row for row in payload["models"]}
    small = by_name["qwen2.5-0.5b"]
    assert small["original"]["n"] == 16
    assert small["extended"]["n"] == 22
    assert small["original"]["answer_f1"] == 1.0
    assert small["extended"]["answer_f1"] == 1.0
    assert payload["recommendation"]["model"] == "qwen2.5-0.5b"
