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


def test_breakdown_matches_published_pcs_example():
    # Same recipe as the composition unit test: PCS raw R' = 649.
    c = CourseComposition(subject="chemistry")
    c.add_node("introduction", "Welcome").add_node("example", "Example 1").add_node("example", "Example 2")
    b = score_breakdown(c)
    f = b["pcs_formula"]
    assert f["raw_before_modulus"] == 649
    assert b["composition_score"] == 649
    assert f["total_nodes_N"] == 3
    assert f["breadth_K"] == 2


def test_config_normalized_weights_sum_to_one():
    cfg = ScoringConfig(quality_weights={"coverage": 2, "balance": 1, "interactivity": 1, "depth": 0})
    w = cfg.normalized_weights()
    assert abs(sum(w.values()) - 1.0) < 1e-6
    assert w["coverage"] == 0.5


def test_override_delete_persists(tmp_path):
    path = tmp_path / "overrides.json"
    store = OverrideStore(path)
    store.set(ManualOverride(course_id="x", score=128))
    assert store.get("x") is not None
    assert store.delete("x") is True
    # Reload from disk: deletion persisted.
    assert OverrideStore(path).get("x") is None
    assert store.delete("missing") is False


def test_recommend_negative_correlation_reduces_weight(tmp_path):
    store = TelemetryStore(tmp_path / "telemetry.jsonl")
    # Happiness FALLS as depth rises -> depth weight should drop below default.
    data = [
        (0.9, {"coverage": 0.5, "balance": 0.5, "interactivity": 0.5, "depth": 0.1}),
        (0.6, {"coverage": 0.5, "balance": 0.5, "interactivity": 0.5, "depth": 0.4}),
        (0.4, {"coverage": 0.5, "balance": 0.5, "interactivity": 0.5, "depth": 0.7}),
        (0.1, {"coverage": 0.5, "balance": 0.5, "interactivity": 0.5, "depth": 0.95}),
    ]
    for i, (h, metrics) in enumerate(data):
        store.record(TelemetrySample(course_id=f"c{i}", composition_score=100 + i,
                                     quality_index=50, happiness=h, metrics=metrics))
    rec = store.recommend_weight_adjustments(ScoringConfig())
    assert rec["status"] == "ok"
    assert rec["correlations"]["depth"] < 0
    assert rec["suggested_weights"]["depth"] < ScoringConfig().normalized_weights()["depth"]


def test_leaderboard_subject_filter_and_min_samples(tmp_path):
    store = TelemetryStore(tmp_path / "telemetry.jsonl")
    store.record(TelemetrySample(course_id="m1", composition_score=1, quality_index=70,
                                 happiness=0.8, subject="math"))
    store.record(TelemetrySample(course_id="s1", composition_score=2, quality_index=60,
                                 happiness=0.9, subject="science"))
    math_board = store.leaderboard(subject="math")
    assert [r["course_id"] for r in math_board] == ["m1"]
    # min_samples filters out single-sample courses.
    assert store.leaderboard(subject="math", min_samples=2) == []


def test_breakdown_modulus_zero_returns_raw():
    c = CourseComposition().add_node("introduction", "x").add_node("example", "y")
    # composition_score(modulus=0) is the uncompressed raw R'.
    assert c.composition_score(modulus=0) == score_breakdown(c)["pcs_formula"]["raw_before_modulus"]


def test_override_and_telemetry_integration(tmp_path):
    """End-to-end: compute, override, record telemetry, and tune together."""
    comp = _sample_course("flagship")
    cfg = ScoringConfig()
    b = score_breakdown(comp, cfg)

    overrides = OverrideStore(tmp_path / "ov.json")
    overrides.set(ManualOverride(course_id="flagship", label="flagship-128", score=128))
    eff = overrides.effective("flagship", computed_score=b["composition_score"],
                              computed_quality=b["quality_index"], computed_label=b["quality_label"])
    assert eff["score"] == 128 and eff["computed"]["score"] == b["composition_score"]

    tel = TelemetryStore(tmp_path / "tel.jsonl")
    tel.record(TelemetrySample(course_id="flagship", composition_score=128,
                               quality_index=b["quality_index"], happiness=0.95,
                               metrics=comp.quality_metrics(), config_version=cfg.version()))
    assert tel.course_summary("flagship")["avg_happiness"] == 0.95
