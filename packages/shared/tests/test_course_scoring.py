"""Course scoring admin: review, override, telemetry, tuning."""

from aoep_shared.harvest.composition import CourseComposition
from aoep_shared.course_scoring import (
    ManualOverride,
    OverrideStore,
    ScoringConfig,
    TelemetryStore,
    TelemetrySample,
    quality_index_with_config,
    score_breakdown,
)


def _sample_course(course_id: str = "c1") -> CourseComposition:
    c = CourseComposition(subject="chemistry", course_id=course_id)
    (c.add_node("introduction", "hook")
      .add_node("concept", "atoms")
      .add_node("example", "ex1")
      .add_node("example", "ex2")
      .add_node("quiz", "q1")
      .add_node("summary", "wrap"))
    return c


def test_score_breakdown_explains_pcs_and_quality():
    c = _sample_course()
    b = score_breakdown(c)
    assert b["composition_score"] == c.composition_score()
    f = b["pcs_formula"]
    # raw_before_modulus mod 1000 must equal the published score.
    assert f["raw_before_modulus"] % f["modulus"] == b["composition_score"]
    assert f["total_nodes_N"] == c.total_nodes()
    assert 0 <= b["quality_index"] <= 100
    assert b["quality_label"] in {"excellent", "strong", "adequate", "thin", "needs_work"}


def test_config_reweighting_changes_quality_label_path():
    c = _sample_course()
    interactive_cfg = ScoringConfig(
        quality_weights={"coverage": 0.1, "balance": 0.1, "interactivity": 0.7, "depth": 0.1})
    coverage_cfg = ScoringConfig(
        quality_weights={"coverage": 0.7, "balance": 0.1, "interactivity": 0.1, "depth": 0.1})
    assert quality_index_with_config(c, interactive_cfg) != quality_index_with_config(c, coverage_cfg)


def test_config_save_and_load_roundtrip(tmp_path):
    cfg = ScoringConfig(quality_weights={"coverage": 0.4, "balance": 0.2,
                                         "interactivity": 0.3, "depth": 0.1}, notes="tuned")
    path = tmp_path / "scoring_config.json"
    cfg.save(path)
    loaded = ScoringConfig.load(path)
    assert loaded.notes == "tuned"
    assert loaded.version() == cfg.version()


def test_quality_bands_editable():
    cfg = ScoringConfig(quality_bands=[(90.0, "A"), (0.0, "B")])
    assert cfg.quality_label(95) == "A"
    assert cfg.quality_label(50) == "B"


def test_manual_override_persists_and_takes_effect(tmp_path):
    store = OverrideStore(tmp_path / "overrides.json")
    store.set(ManualOverride(course_id="chem-101", label="flagship-128", score=128,
                             quality_index=88.0, note="hand-tuned", author="admin"))
    # Reload from disk -> persisted.
    store2 = OverrideStore(tmp_path / "overrides.json")
    eff = store2.effective("chem-101", computed_score=569, computed_quality=50.0,
                           computed_label="adequate")
    assert eff["overridden"] is True
    assert eff["score"] == 128
    assert eff["label"] == "flagship-128"
    assert eff["computed"]["score"] == 569

    eff_none = store2.effective("other", computed_score=200, computed_quality=60.0,
                                computed_label="strong")
    assert eff_none["overridden"] is False
    assert eff_none["score"] == 200


def test_telemetry_record_compare_and_leaderboard(tmp_path):
    store = TelemetryStore(tmp_path / "telemetry.jsonl")
    store.record(TelemetrySample(course_id="A", composition_score=128, quality_index=80,
                                 happiness=0.9, completion_rate=0.8, subject="chem"))
    store.record(TelemetrySample(course_id="B", composition_score=247, quality_index=60,
                                 happiness=0.5, completion_rate=0.6, subject="chem"))
    # Persisted across reloads.
    store2 = TelemetryStore(tmp_path / "telemetry.jsonl")
    assert store2.course_summary("A")["avg_happiness"] == 0.9
    cmp = store2.compare_courses("A", "B")
    assert cmp["winner"] == "A"
    board = store2.leaderboard(subject="chem")
    assert board[0]["course_id"] == "A"


def test_recommend_weight_adjustments_uses_correlation(tmp_path):
    store = TelemetryStore(tmp_path / "telemetry.jsonl")
    # Happiness rises with interactivity; should recommend more interactivity weight.
    data = [
        (0.2, {"coverage": 0.5, "balance": 0.5, "interactivity": 0.1, "depth": 0.3}),
        (0.5, {"coverage": 0.5, "balance": 0.5, "interactivity": 0.4, "depth": 0.3}),
        (0.8, {"coverage": 0.5, "balance": 0.5, "interactivity": 0.7, "depth": 0.3}),
        (0.95, {"coverage": 0.5, "balance": 0.5, "interactivity": 0.9, "depth": 0.3}),
    ]
    for i, (h, metrics) in enumerate(data):
        store.record(TelemetrySample(course_id=f"c{i}", composition_score=100 + i,
                                     quality_index=50, happiness=h, metrics=metrics))
    rec = store.recommend_weight_adjustments(ScoringConfig())
    assert rec["status"] == "ok"
    assert rec["correlations"]["interactivity"] > 0.9
    assert rec["suggested_weights"]["interactivity"] > ScoringConfig().normalized_weights()["interactivity"]


def test_recommend_handles_insufficient_data(tmp_path):
    store = TelemetryStore(tmp_path / "telemetry.jsonl")
    rec = store.recommend_weight_adjustments(ScoringConfig())
    assert rec["status"] == "insufficient_data"
