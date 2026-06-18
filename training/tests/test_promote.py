"""Phase 19 - Track A vs B promotion + serving wiring + fairness gate."""

from champion import ChampionRegistry
from promote import run_promotion


def test_promotes_higher_accuracy_track_and_records_track(tmp_path):
    path = tmp_path / "champion.json"
    res = run_promotion(
        [
            {"name": "trackA-aligned", "track": "A", "metrics": {"accuracy": 0.83, "fairness_gap": 0.04}},
            {"name": "trackB-routed", "track": "B", "metrics": {"accuracy": 0.80, "fairness_gap": 0.03}},
        ],
        champion_path=str(path),
    )
    assert res["champion"] == "trackA-aligned"
    assert res["track"] == "A"
    assert res["serving"] == {"LLM_MODEL": "trackA-aligned"}
    assert ChampionRegistry(path).current() == "trackA-aligned"


def test_track_b_winner_emits_routes():
    res = run_promotion([
        {"name": "trackA", "track": "A", "metrics": {"accuracy": 0.70, "fairness_gap": 0.02}},
        {"name": "trackB", "track": "B", "metrics": {"accuracy": 0.88, "fairness_gap": 0.02}},
    ])
    assert res["champion"] == "trackB"
    assert "LLM_ROUTES" in res["serving"]


def test_fairness_gate_excludes_unfair_winner():
    res = run_promotion([
        {"name": "unfair", "track": "A", "metrics": {"accuracy": 0.99, "fairness_gap": 0.40}},
        {"name": "fair", "track": "B", "metrics": {"accuracy": 0.80, "fairness_gap": 0.02}},
    ], max_fairness_gap=0.1)
    assert res["champion"] == "fair"
