"""Bake-off / champion-challenger harness tests."""

from bakeoff import Candidate, run_bakeoff


def test_champion_is_highest_accuracy():
    res = run_bakeoff([
        Candidate("trackB-base", {"accuracy": 0.72}),
        Candidate("trackA-scratch", {"accuracy": 0.81}),
        Candidate("trackB-mid", {"accuracy": 0.78}),
    ])
    assert res["champion"] == "trackA-scratch"
    assert abs(res["score"] - 0.81) < 1e-9


def test_lower_is_better_metric():
    res = run_bakeoff([
        Candidate("a", {"log_loss": 0.5}),
        Candidate("b", {"log_loss": 0.3}),
    ], primary="log_loss", higher_is_better=False)
    assert res["champion"] == "b"
