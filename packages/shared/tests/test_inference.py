"""Variational ability/IRT model tests."""

from aoep_shared.inference import VariationalAbilityModel, logit


def _responses():
    # high-ability student gets everything right; low-ability gets everything
    # wrong; an easy item is mostly correct, a hard item mostly wrong.
    rows = []
    for item, hard in [("easy", False), ("mid", False), ("hard", True)]:
        rows.append(("high", item, True))
        rows.append(("low", item, False))
    # Mid student: easy right, hard wrong.
    rows += [("mid", "easy", True), ("mid", "mid", True), ("mid", "hard", False)]
    return rows


def test_ability_ordering_recovered():
    m = VariationalAbilityModel().fit(_responses())
    assert m.ability("high") > m.ability("mid") > m.ability("low")


def test_difficulty_ordering_recovered():
    m = VariationalAbilityModel().fit(_responses())
    assert m.difficulty("hard") > m.difficulty("easy")


def test_p_correct_monotonic():
    m = VariationalAbilityModel().fit(_responses())
    assert m.p_correct("high", "easy") > m.p_correct("low", "easy")


def test_select_difficulty_targets_success():
    m = VariationalAbilityModel().fit(_responses())
    b = m.select_difficulty("high", target_p=0.7)
    # With this difficulty, predicted success ~ 0.7.
    import math
    from aoep_shared.inference import _sigmoid

    assert abs(_sigmoid(m.ability("high") - b) - 0.7) < 1e-6


def test_posterior_std_present():
    m = VariationalAbilityModel().fit(_responses())
    assert all(std > 0 for std in m.ability_std.values())


def test_logit_inverse_of_sigmoid():
    from aoep_shared.inference import _sigmoid

    assert abs(_sigmoid(logit(0.7)) - 0.7) < 1e-6
