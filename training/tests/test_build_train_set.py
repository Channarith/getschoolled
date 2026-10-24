import json
from pathlib import Path

import build_train_set as b

AUD = {"age_band": "adult", "language": "en", "reading_level": "intermediate", "learning_style": "reading",
       "professionalism": "neutral", "prior_mastery": 0.5}


def session(q, a, subject, source="authored:test", consent="authored", **extra):
    return {"audience": dict(AUD), "turns": [{"role": "student", "text": q}, {"role": "teacher", "text": a}],
            "rewards": [1.0], "tags": [subject, "stem"], "source": source, "consent": consent, **extra}


def pair(key, lang, heading, text, target):
    return {"key": key, "lang": lang, "source": {"heading": heading, "text": text}, "target": target,
            "verdict": "accept", "reviewer": "r1"}


def run(authored=(), gold=(), classes=(), scores=None, floor=0.4):
    return b.build(authored=list(authored), gold_pairs=list(gold), class_sessions=list(classes),
                   scores=scores or {}, floor=floor)


def test_three_sources_merge_and_are_counted_per_subject_language_source():
    authored = [session("Explain: limits", "A limit is the value a function approaches.", "calculus-1")]
    gold = [pair("k1", "km", "Fractions", "A fraction is part of a whole.", "ប្រភាគគឺជាផ្នែកនៃទាំងមូល។")]
    classes = [session("what is a vector?", "A vector has size and direction.", "linear-algebra",
                       source="class:2026-10-20", consent="opt-in")]
    clean, manifest = run(authored, gold, classes)
    assert manifest["kept"] == 3
    assert manifest["by_language"] == {"en": 2, "km": 1}
    assert set(manifest["by_source"]) == {"authored", "review-lab", "class"}
    assert manifest["by_consent"] == {"authored": 1, "staff-reviewed": 1, "opt-in": 1}
    assert manifest["by_subject"]["calculus-1"] == 1


def test_class_sessions_without_explicit_consent_are_dropped_and_counted():
    classes = [
        session("q1 about derivatives", "Derivatives measure change.", "calculus-1", source="class:a", consent="opt-in"),
        session("q2 about integrals", "Integrals add up area.", "calculus-1", source="class:b", consent=""),
        session("q3 about matrices", "A matrix is a grid of numbers.", "linear-algebra", source="class:c", consent="authored"),
        session("q4 about vectors", "A vector has direction.", "linear-algebra", source="", consent="opt-in"),
    ]
    clean, manifest = run(classes=classes)
    assert manifest["inputs"]["class_sessions_with_consent"] == 1
    assert manifest["class_sessions_dropped"] == {"no_explicit_consent": 2, "no_source": 1}
    assert manifest["kept"] == 1


def test_child_sessions_need_guardian_consent():
    child = session("what is a number?", "A number counts things.", "arithmetic", source="class:k", consent="opt-in")
    child["audience"]["age_band"] = "child"
    clean, manifest = run(classes=[child])
    assert manifest["kept"] == 0
    assert manifest["gate"]["dropped"].get("child_without_guardian_consent") == 1


def test_pii_is_scrubbed_or_dropped_and_duplicates_removed():
    authored = [
        session("Explain: email", "Contact me at someone@example.com for the answer to this.", "writing"),
        session("Explain: dup", "Same answer text that is definitely long enough to count as a duplicate answer here.", "a"),
        session("Explain: dup", "A different answer that is also long enough to be kept as a separate record.", "a"),
    ]
    clean, manifest = run(authored)
    assert all("example.com" not in t["text"] for s in clean for t in s["turns"])
    assert manifest["gate"]["dropped"].get("duplicate_question") == 1


def test_protected_attribute_is_a_hard_failure():
    bad = session("q about fractions", "Fractions are parts of a whole number.", "math", ethnicity="x")
    clean, manifest = run([bad])
    assert manifest["hard_failures"] and manifest["kept"] == 0


def test_gold_pairs_without_a_reviewed_target_are_ignored():
    gold = [pair("k1", "es", "Cells", "Cells are the unit of life.", ""),
            pair("k2", "es", "Atoms", "Atoms are small.", "Los átomos son pequeños.")]
    clean, manifest = run(gold=gold)
    assert manifest["inputs"]["gold_pairs"] == 1 and manifest["kept"] == 1


def test_needs_data_lists_subjects_under_the_floor_with_training_counts():
    authored = [session(f"Explain: topic {i}", f"Linear algebra statement number {i} about vectors.", "linear-algebra")
                for i in range(3)]
    scores = {
        "Health & Wellness": {"score": 0.102, "eval_n": 10, "exam": "stem.frozen.json"},
        "calculus-1": {"score": 0.112, "eval_n": 4, "exam": "stem.stemfrozen.json"},
        "linear-algebra": {"score": 0.336, "eval_n": 4, "exam": "stem.stemfrozen.json"},
        "history": {"score": 0.61, "eval_n": 8, "exam": "stem.frozen.json"},
    }
    clean, manifest = run(authored, scores=scores)
    rows = {r["subject"]: r for r in manifest["needs_data"]}
    assert set(rows) == {"Health & Wellness", "calculus-1", "linear-algebra"}
    assert rows["Health & Wellness"]["note"] == "no training examples at all"
    assert rows["linear-algebra"]["train_examples"] == 3
    assert rows["linear-algebra"]["suggested_new_examples"] == 27
    assert [r["subject"] for r in manifest["needs_data"]][0] == "Health & Wellness"  # weakest first


def test_a_subject_with_plenty_of_data_but_a_low_score_is_not_told_to_add_volume():
    authored = [session(f"Explain: calc {i}", f"Calculus statement number {i} about limits and rates.", "calculus-1")
                for i in range(40)]
    scores = {"calculus-1": {"score": 0.112, "eval_n": 4, "exam": "stem.stemfrozen.json"}}
    clean, manifest = run(authored, scores=scores)
    row = manifest["needs_data"][0]
    assert row["train_examples"] == 40 and row["suggested_new_examples"] == 0
    assert "not volume" in row["note"]


def test_briefing_scores_are_used_only_when_no_metrics_exist_and_are_labelled():
    clean, manifest = run([session("Explain: python", "Python reads files with open.", "python-11-files-and-exceptions")])
    assert manifest["scores_from_briefing"] is True
    names = {r["subject"] for r in manifest["needs_data"]}
    assert {"Health & Wellness", "calculus-1", "python-11-files-and-exceptions", "linear-algebra"} <= names
    assert all("briefing" in r["note"] or "briefing" in r["exam"] for r in manifest["needs_data"])


def test_load_subject_scores_takes_the_lowest_score_across_exams(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"by_category": {"x": 0.5}, "by_category_n": {"x": 4}}))
    (tmp_path / "b.json").write_text(json.dumps({"by_category": {"x": 0.2}, "by_category_n": {"x": 2}}))
    scores = b.load_subject_scores([tmp_path / "a.json", tmp_path / "b.json", tmp_path / "missing.json"])
    assert scores["x"]["score"] == 0.2 and scores["x"]["exam"] == "b.json"


def test_cli_report_only_writes_nothing_and_full_run_writes_manifest(tmp_path, capsys):
    sessions = tmp_path / "s.json"
    sessions.write_text(json.dumps([session("Explain: limits", "A limit is the value a function approaches.", "calculus-1")]))
    out = tmp_path / "grown.json"
    assert b.main(["--sessions", str(sessions), "--eval-metrics", "--out", str(out), "--report-only"]) == 0
    assert not out.exists()
    assert b.main(["--sessions", str(sessions), "--eval-metrics", "--out", str(out)]) == 0
    assert json.loads(out.read_text())[0]["tags"][0] == "calculus-1"
    assert (tmp_path / "grown.manifest.json").is_file() and (tmp_path / "needs_data.json").is_file()
    assert "floor" in capsys.readouterr().out
