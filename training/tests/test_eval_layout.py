import json
import os
import time

import eval_layout
import nightly_candidates


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def frozen(acc, subject_min, abstain):
    return {"accuracy": acc, "token_f1": acc, "fairness_gap": 0.02, "subject_min": subject_min,
            "by_category": {"calculus-1": subject_min}, "by_category_n": {"calculus-1": 4},
            "behaviour": {"abstain": abstain}}


def lay_out(out, base_acc=0.199, stem_acc=0.25, stem_min=0.45, stem_abstain=0.6):
    for who, acc, smin, ab in (("base", base_acc, 0.45, 0.5), ("stem", stem_acc, stem_min, stem_abstain)):
        write(out / "eval" / who / "eval_frozen.json", frozen(acc, smin, ab))
        write(out / "eval" / who / "eval_frozen_stem.json", frozen(acc, smin, ab))
        write(out / "eval" / who / "eval.json", frozen(acc, smin, ab))
        write(out / "eval" / who / "eval_behavior_v1.json", {"accuracy": 0.7, "behaviour": {"abstain": ab, "refuse": 0.8, "hint": 0.7}})


def test_per_benchmark_files_are_copied_to_the_flat_names_the_gate_and_briefing_read(tmp_path):
    lay_out(tmp_path)
    written = eval_layout.link_legacy(tmp_path)
    names = {os.path.basename(p) for p in written}
    assert names == {"base.json", "base.frozen.json", "base.stemfrozen.json",
                     "stem.json", "stem.frozen.json", "stem.stemfrozen.json"}
    assert json.loads((tmp_path / "eval" / "stem.frozen.json").read_text())["accuracy"] == 0.25


def test_a_newer_flat_file_is_never_overwritten_by_an_older_one(tmp_path):
    lay_out(tmp_path)
    flat = tmp_path / "eval" / "stem.frozen.json"
    flat.write_text(json.dumps({"accuracy": 0.99}), encoding="utf-8")
    future = time.time() + 60
    os.utime(flat, (future, future))
    eval_layout.link_legacy(tmp_path)
    assert json.loads(flat.read_text())["accuracy"] == 0.99


def run(tmp_path, **kw):
    lay_out(tmp_path, **kw)
    assert nightly_candidates.main(["--out", str(tmp_path), "--max-fairness-gap", "0.1", "--min-subject-score", "0.4"]) == 0
    return json.loads((tmp_path / "bakeoff" / "result.json").read_text())


def test_nightly_wires_the_subject_floor_and_behaviour_floors_into_one_bakeoff(tmp_path):
    result = run(tmp_path)
    assert result["champion"] == "stem-qlora"
    args = (tmp_path / "bakeoff" / "floors.args").read_text()
    assert "--min-metric abstain=" in args and "--min-subject-score 0.4" in args
    assert (tmp_path / "eval" / "stem.frozen.json").is_file()


def test_nightly_rejects_a_weak_subject_even_with_a_higher_score(tmp_path):
    result = run(tmp_path, stem_min=0.12)
    assert result["champion"] == "qwen-base"
    assert result["rejected"][0]["reason"] == "subject_floor"


def test_nightly_rejects_an_abstain_regression_even_with_a_higher_score(tmp_path):
    result = run(tmp_path, stem_abstain=0.2)
    assert result["champion"] == "qwen-base"
    assert result["rejected"][0]["reason"] == "metric_floor"
