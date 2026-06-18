"""Bake-off / champion-challenger harness tests."""

from bakeoff import Candidate, promote_champion, run_bakeoff
from champion import ChampionRegistry
from evaluate import aggregate_scores


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


def test_fairness_gate_rejects_unfair_candidate():
    res = run_bakeoff([
        Candidate("accurate-but-unfair", {"accuracy": 0.95, "fairness_gap": 0.30}),
        Candidate("fair", {"accuracy": 0.80, "fairness_gap": 0.05}),
    ], max_fairness_gap=0.10)
    assert res["champion"] == "fair"
    assert any(r["name"] == "accurate-but-unfair" for r in res["rejected"])


def test_champion_registry_promote_and_revert(tmp_path):
    path = tmp_path / "champion.json"
    res = run_bakeoff([
        Candidate("trackB", {"accuracy": 0.78}),
        Candidate("trackA", {"accuracy": 0.84}),
    ])
    promote_champion(res, str(path))
    reg = ChampionRegistry(path)
    assert reg.current() == "trackA"
    # Promote a newer one, then revert to the previous champion.
    reg.promote("trackA-v2", {"accuracy": 0.90})
    assert reg.current() == "trackA-v2"
    reg.revert()
    assert reg.current() == "trackA"


def test_aggregate_scores_category_and_fairness_gap():
    agg = aggregate_scores([
        {"score": 0.9, "category": "math", "group": "A"},
        {"score": 0.5, "category": "math", "group": "B"},
        {"score": 0.8, "category": "history", "group": "A"},
    ])
    assert agg["by_category"]["math"] == 0.7
    assert agg["fairness_gap"] > 0  # group A mean > group B mean
    assert agg["n"] == 3
