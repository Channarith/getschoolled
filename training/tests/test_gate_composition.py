"""The two promotion gates (frozen-exam rise + subject floor from PR #728; behaviour floors from PR #774)
must compose: an adapter is kept only when every condition holds, and each condition alone blocks it."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from bakeoff import Candidate, run_bakeoff
from evaluate import _prompt, run_eval
from scoring import token_f1
from promotion_gate import decide_promotion

ROOT = Path(__file__).resolve().parents[2]
TRAINING = ROOT / "training"

BASE = {"accuracy": 0.199, "fairness_gap": 0.02, "subject_min": 0.45, "abstain": 0.5, "refuse": 0.8, "hint": 0.7}
FLOORS = {"abstain": 0.5, "refuse": 0.8, "hint": 0.7}


def bake(adapter_metrics, **kw):
    cands = [Candidate("qwen-base", BASE), Candidate("stem-qlora", adapter_metrics)]
    return run_bakeoff(cands, primary="accuracy", max_fairness_gap=0.1, min_subject_score=0.40,
                       min_metrics=FLOORS, **kw)


def gate(**over):
    args = dict(name="stem-qlora", champion="stem-qlora", frozen_accuracy=0.25, previous_accuracy=0.204,
                frozen_subject_min=0.45, split_subject_min=0.5, subject_floor=0.40, stem_subject_min=0.5,
                stem_required=True)
    args.update(over)
    return decide_promotion(**args)


GOOD = {**BASE, "accuracy": 0.25}


def test_all_conditions_met_promotes():
    assert bake(GOOD)["champion"] == "stem-qlora"
    assert gate()[0] is True


def test_higher_score_but_weak_subject_is_rejected_by_bakeoff():
    result = bake({**GOOD, "subject_min": 0.12})
    assert result["champion"] == "qwen-base"
    assert {r["reason"] for r in result["rejected"]} == {"subject_floor"}


def test_higher_score_but_behaviour_regression_is_rejected_by_bakeoff():
    for metric in ("abstain", "refuse", "hint"):
        result = bake({**GOOD, metric: BASE[metric] - 0.2})
        assert result["champion"] == "qwen-base", metric
        assert {r["reason"] for r in result["rejected"]} == {"metric_floor"}, metric


def test_fairness_gap_is_still_enforced():
    assert bake({**GOOD, "fairness_gap": 0.3})["champion"] == "qwen-base"


def test_unchanged_frozen_score_is_not_promoted_by_the_gate():
    allowed, reason = gate(frozen_accuracy=0.204, previous_accuracy=0.204)
    assert not allowed and reason


def test_lower_frozen_score_is_not_promoted_by_the_gate():
    assert gate(frozen_accuracy=0.19, previous_accuracy=0.204)[0] is False


@pytest.mark.parametrize("field", ["frozen_subject_min", "split_subject_min", "stem_subject_min"])
def test_any_subject_under_the_floor_blocks_the_gate(field):
    assert gate(**{field: 0.11})[0] is False


def test_gate_needs_the_bakeoff_champion():
    assert gate(champion="qwen-base")[0] is False


def test_promote_cli_accepts_the_subject_floor(tmp_path):
    cands = [{"name": "qwen-base", "track": "B", "metrics": BASE},
             {"name": "stem-qlora", "track": "B", "metrics": {**GOOD, "subject_min": 0.1}}]
    path = tmp_path / "c.json"
    path.write_text(json.dumps(cands), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(TRAINING / "promote.py"), "--candidates", str(path), "--min-subject-score", "0.4",
         "--min-metric", "abstain=0.5"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["champion"] == "qwen-base"


# ---- the scorer change must not move any English number -----------------------------------------------

_TOKEN = re.compile(r"[a-z0-9]+")


def original_token_f1(prediction: str, reference: str) -> float:
    """The scorer as it was when the Spark measured 20.4% (adapter) and 19.9% (base)."""
    pred = _TOKEN.findall(prediction.lower())
    ref = _TOKEN.findall(reference.lower())
    if not pred or not ref:
        return 0.0
    common: dict = {}
    ref_counts: dict = {}
    for t in ref:
        ref_counts[t] = ref_counts.get(t, 0) + 1
    overlap = 0
    for t in pred:
        if ref_counts.get(t, 0) - common.get(t, 0) > 0:
            common[t] = common.get(t, 0) + 1
            overlap += 1
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred)
    recall = overlap / len(ref)
    return 2 * precision * recall / (precision + recall)


def frozen_rows(name):
    path = TRAINING / "data" / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _variants(ref):
    words = ref.split()
    return [
        ref,
        " ".join(words[::2]),
        " ".join(reversed(words)),
        " ".join(words[: max(1, len(words) // 3)]),
        "I do not know. " + " ".join(words[1::3]),
        "",
    ]


@pytest.mark.parametrize("name", ["eval_frozen.jsonl", "eval_frozen_stem.jsonl"])
def test_english_scoring_is_identical_on_the_frozen_exams(name):
    """Through the real evaluate path, every English item scores exactly as the original scorer did."""
    rows = frozen_rows(name)
    assert rows
    for variant in range(6):
        answers = {_prompt(r): _variants(r.get("response", ""))[variant] for r in rows}
        summary = run_eval(rows, lambda prompt: answers[prompt])
        expected = sum(original_token_f1(answers[_prompt(r)], r.get("response", "")) for r in rows) / len(rows)
        assert summary["token_f1"] == pytest.approx(round(expected, 4), abs=1e-9), (name, variant)


def test_non_english_rows_use_the_unicode_scorer():
    """Khmer scores 0 under the original tokenizer (it keeps only a-z0-9); the new one must not."""
    khmer = "សូមស្វាគមន៍មកកាន់មេរៀន"
    assert original_token_f1(khmer, khmer) == 0.0
    assert token_f1(khmer, khmer) == 1.0
    rows = [{"instruction": "q", "response": khmer, "context": {"language": "km"}}]
    assert run_eval(rows, lambda prompt: khmer)["token_f1"] == 1.0
