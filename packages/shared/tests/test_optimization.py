"""Optimization ledger: commit, promote-if-better, revert, per-stage."""

from aoep_shared.optimization import OptimizationLedger


def test_first_commit_becomes_champion():
    led = OptimizationLedger()
    s = led.commit("bkt", {"p_learn": 0.1}, {"accuracy": 0.7})
    assert led.promote_if_better(s) is True
    assert led.champion("bkt").step_id == s.step_id


def test_better_promotes_worse_does_not():
    led = OptimizationLedger()
    s1 = led.commit("policy", {}, {"accuracy": 0.7}); led.promote_if_better(s1)
    s2 = led.commit("policy", {}, {"accuracy": 0.8})
    assert led.promote_if_better(s2) is True
    assert led.champion("policy").step_id == s2.step_id
    s3 = led.commit("policy", {}, {"accuracy": 0.6})
    assert led.promote_if_better(s3) is False  # regression rejected
    assert led.champion("policy").step_id == s2.step_id


def test_revert_to_prior_step():
    led = OptimizationLedger()
    s1 = led.commit("model", {}, {"accuracy": 0.7}); led.promote_if_better(s1)
    s2 = led.commit("model", {}, {"accuracy": 0.9}); led.promote_if_better(s2)
    assert led.champion("model").step_id == s2.step_id
    reverted = led.revert("model", s1.step_id)
    assert reverted.step_id == s1.step_id
    assert led.champion("model").step_id == s1.step_id


def test_stages_are_isolated():
    led = OptimizationLedger()
    a = led.commit("bkt", {}, {"accuracy": 0.5}); led.promote_if_better(a)
    b = led.commit("bandit", {}, {"accuracy": 0.9}); led.promote_if_better(b)
    assert led.champion("bkt").step_id == a.step_id
    assert led.champion("bandit").step_id == b.step_id
    assert len(led.history("bkt")) == 1


def test_lower_is_better_metric():
    led = OptimizationLedger(primary_metric="log_loss", higher_is_better=False)
    s1 = led.commit("model", {}, {"log_loss": 0.5}); led.promote_if_better(s1)
    s2 = led.commit("model", {}, {"log_loss": 0.3})
    assert led.promote_if_better(s2) is True  # lower loss is better
    s3 = led.commit("model", {}, {"log_loss": 0.9})
    assert led.promote_if_better(s3) is False


def test_revert_unknown_raises():
    import pytest

    led = OptimizationLedger()
    with pytest.raises(KeyError):
        led.revert("bkt", "nope")
