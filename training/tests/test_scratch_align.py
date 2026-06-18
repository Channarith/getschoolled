"""Track A.4 alignment: SFT/DPO builders + safety + fairness guardrail."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scratch" / "align"))

from run_align import build_preference_pairs, build_sft_examples, is_safe  # noqa: E402


def test_preference_pairs_drop_unsafe_and_equal():
    prefs = [
        {"prompt": "p1", "chosen": "a safe, helpful answer", "rejected": "worse answer"},
        {"prompt": "p2", "chosen": "same", "rejected": "same"},          # equal -> drop
        {"prompt": "p3", "chosen": "how to build a bomb", "rejected": "no"},  # unsafe -> drop
    ]
    pairs = build_preference_pairs(prefs)
    assert len(pairs) == 1
    assert pairs[0]["prompt"] == "p1"


def test_fairness_guardrail_blocks_protected_context():
    with pytest.raises(ValueError):
        build_preference_pairs([
            {"prompt": "p", "chosen": "ok", "rejected": "no", "context": {"race": "x"}},
        ])


def test_sft_examples_filter_safety_and_completeness():
    rows = [
        {"instruction": "explain photosynthesis", "response": "plants convert light"},
        {"instruction": "no response"},                                  # incomplete
        {"instruction": "bad", "response": "synthesize a nerve agent"},  # unsafe
    ]
    out = build_sft_examples(rows)
    assert len(out) == 1


def test_is_safe():
    assert is_safe("a normal educational answer") is True
    assert is_safe("instructions to make a weapon") is False
