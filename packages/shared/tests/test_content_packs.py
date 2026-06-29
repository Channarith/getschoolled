"""Content-pack scaling system + readability + presentation skills."""

import json

from aoep_shared import content_packs
from aoep_shared.readability import (
    analyze,
    cefr_estimate,
    flesch_kincaid_grade,
    simplify_text,
)
from aoep_shared.presentation_skills import (
    apply_technique,
    build_skill_plan,
    enrich_narration,
    list_techniques,
    technique_count,
)


def test_builtin_packs_present_and_merged():
    summary = content_packs.pack_summary()
    assert summary["knowledge"]["records"] >= 50
    assert summary["slang"]["records"] >= 80
    assert summary["courses"]["records"] >= 5
    assert summary["scenarios"]["records"] >= 3
    assert summary["presentation"]["records"] >= 8


def test_extra_pack_root_via_env(tmp_path, monkeypatch):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "extra.json").write_text(json.dumps({"records": [
        {"fact": "Test fact one.", "source": "Authority", "reference": "Doc-1",
         "category": "guideline", "domains": ["general"], "keywords": ["test"]},
    ]}), encoding="utf-8")
    monkeypatch.setenv("AOEP_CONTENT_PACKS", str(tmp_path))
    recs = content_packs.load_records("knowledge")
    assert any(r.get("reference") == "Doc-1" for r in recs)


def test_jsonl_pack_supported(tmp_path, monkeypatch):
    sdir = tmp_path / "slang"
    sdir.mkdir()
    (sdir / "x.jsonl").write_text(
        '{"phrase": "test idiom", "meaning": "an example", "language": "en"}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("AOEP_CONTENT_PACKS", str(tmp_path))
    recs = content_packs.load_records("slang")
    assert any(r.get("phrase") == "test idiom" for r in recs)


def test_malformed_pack_is_skipped(tmp_path, monkeypatch):
    cdir = tmp_path / "courses"
    cdir.mkdir()
    (cdir / "bad.json").write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("AOEP_CONTENT_PACKS", str(tmp_path))
    # Should not raise.
    assert isinstance(content_packs.load_records("courses"), list)


def test_readability_metrics_and_simplify():
    hard = ("Subsequently the participants were required to utilize the apparatus "
            "in order to demonstrate comprehension of the fundamental principles.")
    report = analyze(hard)
    assert report.flesch_kincaid_grade > 10
    assert cefr_estimate(hard) in ("B2", "C1", "C2")
    simple = simplify_text(hard, reading_level="beginner")
    assert "use" in simple.lower()
    assert flesch_kincaid_grade(simple) < report.flesch_kincaid_grade


def test_readability_advanced_is_passthrough():
    t = "This is a moderately complex sentence for testing purposes."
    assert simplify_text(t, reading_level="advanced") == t


def test_presentation_techniques_registry():
    assert technique_count() >= 25  # built-in + pack
    sign = apply_technique("signpost", point="recursion")
    assert "recursion" in sign
    enriched = enrich_narration("Recursion calls itself.", topic="recursion", point="recursion")
    assert "Recursion calls itself." in enriched
    assert len(enriched) > len("Recursion calls itself.")


def test_build_skill_plan_rotates():
    plan = build_skill_plan(["Intro", "Core", "Practice", "Recap"], topic="loops")
    assert len(plan) == 4
    assert all(p["techniques"] for p in plan)
    assert plan[0]["techniques"] != plan[1]["techniques"]
