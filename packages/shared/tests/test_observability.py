"""Phase 10 - latency budget + recorder tests."""

from aoep_shared.observability import (
    TOTAL_BUDGET_MS,
    LatencyBudget,
    LatencyRecorder,
)


def test_total_budget():
    assert TOTAL_BUDGET_MS == 1100.0
    assert LatencyBudget().total_ms == 1100.0


def test_within_budget_and_overages():
    budget = LatencyBudget()
    ok = {"asr": 200, "think": 400, "tts": 250}
    assert budget.within_budget(ok) is True
    assert budget.overages(ok) == {}

    bad = {"asr": 350, "think": 700, "tts": 250}
    assert budget.within_budget(bad) is False
    over = budget.overages(bad)
    assert over["asr"] == 50 and over["think"] == 200
    assert "tts" not in over


def test_recorder_aggregates():
    rec = LatencyRecorder()
    for v in (100, 200, 300, 400, 500):
        rec.record("think", v)
    assert rec.mean("think") == 300
    assert rec.p95("think") == 500
    summary = rec.summary()
    assert "think" in summary and summary["think"]["mean"] == 300
