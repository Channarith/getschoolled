"""Offline export + run_finetune --check tests (no ML libs required)."""

import json
from pathlib import Path

import export
import run_finetune
from evaluate import token_f1

DATA = Path(__file__).resolve().parents[1] / "data" / "sample_sessions.json"
CONFIG = Path(__file__).resolve().parents[1] / "config" / "finetune.yaml"


def test_export_produces_clean_jsonl(tmp_path):
    out = tmp_path / "train.jsonl"
    rc = export.main(["--in", str(DATA), "--out", str(out)])
    assert rc == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(rows) >= 3
    for r in rows:
        assert r["instruction"] and r["response"]
        # Fairness guardrail: no protected attributes leak into context.
        assert "race" not in r["context"] and "ethnicity" not in r["context"]


def test_export_eval_split(tmp_path):
    train = tmp_path / "t.jsonl"
    ev = tmp_path / "e.jsonl"
    export.main(["--in", str(DATA), "--out", str(train), "--eval-out", str(ev),
                 "--eval-split", "0.5"])
    assert ev.exists() and train.exists()


def test_export_merges_corrections(tmp_path):
    out = tmp_path / "train.jsonl"
    corr = tmp_path / "corrections.jsonl"
    corr.write_text(json.dumps({
        "instruction": "what gas do plants release?",
        "context": {"language": "en"},
        "response": "oxygen", "reward": 1.0, "tags": ["correction", "model"],
    }) + "\n")
    rc = export.main(["--in", str(DATA), "--out", str(out), "--corrections", str(corr)])
    assert rc == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    # Includes the gold correction row (reward 1.0) alongside session examples.
    assert any(r.get("reward") == 1.0 and r["response"] == "oxygen" for r in rows)


def test_run_finetune_check_is_torch_free(tmp_path):
    # Build a dataset, then validate with --check (must NOT import torch).
    out = tmp_path / "train.jsonl"
    export.main(["--in", str(DATA), "--out", str(out)])
    rc = run_finetune.main(["--check", "--config", str(CONFIG), "--train", str(out)])
    assert rc == 0


def test_run_finetune_check_rejects_protected_attr(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({
        "instruction": "q", "response": "a",
        "context": {"language": "en", "race": "X"},
    }) + "\n")
    rc = run_finetune.main(["--check", "--config", str(CONFIG), "--train", str(bad)])
    assert rc == 2  # guardrail violation -> non-zero


def test_token_f1_scoring():
    assert token_f1("oxygen is released", "plants release oxygen") > 0.0
    assert token_f1("", "anything") == 0.0
    assert token_f1("exact match", "exact match") == 1.0
