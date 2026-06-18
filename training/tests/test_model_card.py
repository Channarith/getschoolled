"""Model card generator tests (Trust layer, Phase 5)."""

from model_card import build_model_card


def test_model_card_has_metrics_and_fairness():
    card = build_model_card(
        "trackB-routed",
        {"accuracy": 0.84, "by_category": {"math": 0.9, "history": 0.8}, "fairness_gap": 0.03},
        base_model="qwen-7b",
    )
    assert card["name"] == "trackB-routed"
    assert card["base_model"] == "qwen-7b"
    assert card["metrics"]["accuracy"] == 0.84
    assert card["metrics"]["by_category"]["math"] == 0.9
    assert card["metrics"]["fairness_gap"] == 0.03
    assert card["limitations"]
    assert "race" in card["fairness"]


def test_model_card_defaults_limitations():
    card = build_model_card("m", {"accuracy": 0.5})
    assert isinstance(card["limitations"], list) and len(card["limitations"]) >= 1
