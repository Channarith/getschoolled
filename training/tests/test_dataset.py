"""Training data pipeline + fairness guardrail tests."""

import json

import pytest

from pipeline.dataset import (
    CONDITIONING_FEATURES,
    PROTECTED_ATTRIBUTES,
    AudienceContext,
    assert_no_protected,
    build_example,
    class_session_to_examples,
    redact_protected,
    to_jsonl,
)
from pipeline.feedback import Feedback, aggregate, reward_from_feedback


def test_conditioning_dict_only_allowlisted_features():
    ctx = AudienceContext(language="es", race="X", ethnicity="Y")
    cond = ctx.conditioning_dict()
    assert set(cond) == set(CONDITIONING_FEATURES)
    for p in PROTECTED_ATTRIBUTES:
        assert p not in cond


def test_protected_attributes_never_in_example():
    ctx = AudienceContext(race="X", ethnicity="Y", language="fr")
    ex = build_example("What is 2+2?", "It's 4.", ctx)
    d = ex.to_dict()
    assert "race" not in d["context"] and "ethnicity" not in d["context"]
    assert d["context"]["language"] == "fr"


def test_assert_no_protected_raises_on_leak():
    with pytest.raises(ValueError):
        assert_no_protected({"language": "en", "race": "X"})
    assert redact_protected({"language": "en", "race": "X"}) == {"language": "en"}


def test_class_session_to_examples_pairs_turns():
    turns = [
        {"role": "student", "text": "what is gravity?"},
        {"role": "teacher", "text": "a force pulling objects together"},
        {"role": "student", "text": "why do we fall?"},
        {"role": "teacher", "text": "earth's gravity pulls us down"},
    ]
    ctx = AudienceContext(age_band="teen", reading_level="beginner")
    exs = class_session_to_examples(turns, ctx, rewards=[1.0, 0.5])
    assert len(exs) == 2
    assert exs[0].reward == 1.0
    assert exs[0].context["age_band"] == "teen"


def test_to_jsonl_is_valid_and_clean():
    ctx = AudienceContext(race="X")
    jsonl = to_jsonl([build_example("q", "a", ctx)])
    row = json.loads(jsonl.splitlines()[0])
    assert "race" not in row["context"]
    assert row["instruction"] == "q" and row["response"] == "a"


def test_reward_mapping_and_aggregate():
    assert reward_from_feedback(Feedback(rating=5)) == 1.0
    assert reward_from_feedback(Feedback(rating=3)) == 0.0
    assert reward_from_feedback(Feedback(rating=1)) == -1.0
    assert reward_from_feedback(Feedback(rating=5, helpful=False)) == 0.5
    # An explicit correction caps reward negative.
    assert reward_from_feedback(Feedback(rating=5, correction="real answer")) <= -0.5

    agg = aggregate([Feedback(rating=5), Feedback(rating=3, helpful=False)])
    assert agg["count"] == 2
    assert agg["mean_rating"] == 4.0
    assert agg["helpful_rate"] == 0.5
