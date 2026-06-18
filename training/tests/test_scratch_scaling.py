"""Track A.3 scaling-law fit + orchestration plan tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scratch" / "pretrain"))

from scaling import fit_power_law, predict_loss  # noqa: E402


def test_recovers_known_power_law():
    # loss = 3.0 * compute^-0.1
    pts = [(c, 3.0 * c ** -0.1) for c in (1e3, 1e4, 1e5, 1e6)]
    fit = fit_power_law(pts)
    assert abs(fit["b"] - 0.1) < 1e-6
    assert abs(fit["a"] - 3.0) < 1e-6


def test_predict_extrapolates():
    pts = [(c, 3.0 * c ** -0.1) for c in (1e3, 1e4, 1e5)]
    fit = fit_power_law(pts)
    assert abs(predict_loss(fit, 1e7) - 3.0 * (1e7) ** -0.1) < 1e-3


def test_orchestrate_plan_with_scaling():
    from orchestrate import build_plan

    ladder = Path(__file__).resolve().parents[1] / "scratch" / "config" / "model_ladder.yaml"
    plan = build_plan(str(ladder), 8, 8, 1,
                      proxy_points=[(1e3, 2.0), (1e4, 1.6), (1e5, 1.3)])
    assert any(s["stage"] == "proxy-1b" for s in plan["stages"])
    assert "scaling_fit" in plan
    assert "predicted_target_loss" in plan
