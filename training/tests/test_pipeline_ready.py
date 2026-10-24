"""Benchmarks, base comparison, behaviour-gated bake-off, requirements and scripts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import bakeoff
import build_eval_behavior as beb
import build_eval_multilingual as bem
import compare_bases as cb
import nightly_candidates as nc
import run_finetune
import scoring

ROOT = Path(__file__).resolve().parents[2]
TRAINING = ROOT / "training"
# The frozen set was regenerated once, on 2026-10-22 (PR #728, build_eval_set.py v2: every item carries its
# passage). Every Spark score on record (20.4% adapter, 19.9% base) was measured on this version, so it is
# the frozen set. The earlier hash was 368c8037...; do not regenerate again.
FROZEN_SHA256 = "d7409c2b87acf3d76b284bc46a381a1c345e858be8b04c5315c25cbf837deb66"


def lines(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


# ---- the frozen benchmark never changes -------------------------------------------------


def test_frozen_benchmark_is_untouched():
    path = TRAINING / "data" / "eval_frozen.jsonl"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == FROZEN_SHA256, (
        "eval_frozen.jsonl changed. It is frozen: add new items in a new file instead.")


def test_builders_refuse_to_overwrite_the_frozen_file():
    with pytest.raises(SystemExit):
        bem.main(["--out", str(TRAINING / "data" / "eval_frozen.jsonl"), "--translations", str(ROOT / "data" / "course_translations")])


# ---- behaviour benchmark ---------------------------------------------------------------


def test_behaviour_benchmark_is_deterministic_and_well_formed():
    items = beb.build_items()
    assert items == beb.build_items()
    assert {"hint", "spoken", "grounded", "refuse"} == {i["scorer"] for i in items}
    for i in items:
        assert i["instruction"].startswith("[Tutor mode:")
        scoring.score_behaviour(i, "x")  # every scorer name is recognised
        if i["scorer"] == "hint":
            assert i["answer"] and i["answer"].lower() not in i["instruction"].lower().split("fill in the blank:")[0]
            assert "____" in i["instruction"]
    assert [i for i in items if i["scorer"] == "refuse"]
    committed = lines(TRAINING / "data" / "eval_behavior_v1.jsonl")
    assert len(committed) == len(items)


def test_refusal_eval_prompts_are_not_in_training_data():
    import tutor_format as tf

    eval_prompts = {i["instruction"].split("\n", 1)[1] for i in beb.build_items() if i["scorer"] == "refuse"}
    assert eval_prompts == set(tf.REFUSE_EVAL_PROMPTS) and not (eval_prompts & set(tf.REFUSE_TRAIN_PROMPTS))


def test_behaviour_benchmark_does_not_use_training_lessons():
    """Training uses sample-curriculum; the benchmark uses the audio lessons only."""
    train_text = " ".join(p.read_text(encoding="utf-8", errors="ignore")
                          for p in (ROOT / "sample-curriculum").glob("**/lesson.txt"))
    clash = 0
    for i in beb.build_items():
        if i["scorer"] == "grounded":
            passage = i["instruction"].split("Passage from the lesson", 1)[1].split("\n", 2)[2][:60]
            clash += passage in train_text
    assert clash == 0


# ---- multilingual benchmark ------------------------------------------------------------


def test_multilingual_benchmark_covers_the_seven_languages_and_marks_machine_references():
    items = lines(TRAINING / "data" / "eval_multilingual_v1.jsonl")
    assert {i["context"]["language"] for i in items} == set(bem.LANGUAGES)
    assert all(i["source"] in ("mt-unreviewed", "staff-reviewed") for i in items)
    for i in items:
        assert i["scorer"] == "language" and i["response"]
        assert scoring.score_language(i["response"], i["context"]["language"]) == 1.0, i["id"]
        assert scoring.token_f1(i["response"], i["response"]) == pytest.approx(1.0)


def test_gold_pairs_take_priority_and_are_marked_reviewed(tmp_path):
    gold = tmp_path / "gold.jsonl"
    gold.write_text(json.dumps({"lang": "km", "source": {"heading": "H", "text": "English passage here."},
                                "target": "សូមស្វាគមន៍។ មេរៀននេះ។"}, ensure_ascii=False) + "\n", encoding="utf-8")
    items = bem.build_items(tmp_path / "none", gold, per_lang=3)
    assert [i["source"] for i in items] == ["staff-reviewed"] and items[0]["context"]["language"] == "km"


def test_unaligned_translations_are_skipped_not_guessed(tmp_path):
    course = tmp_path / "audio-nonexistent-course"
    course.mkdir()
    (course / "km.json").write_text(json.dumps({"segments": [{"heading": "h", "text": "t"}]}), encoding="utf-8")
    assert bem.build_items(tmp_path, None, per_lang=3) == []


# ---- base-model comparison -------------------------------------------------------------


def test_fits_matches_the_documented_budgets():
    assert cb.fits(7.6, "spark") == {"qlora": True, "eval_bf16": True, "eval_4bit": True}
    f = cb.fits(7.6, "ibuypower")
    assert not f["qlora"] and not f["eval_bf16"] and f["eval_4bit"]
    assert cb.fits(4.0, "ibuypower")["qlora"]
    assert not any(cb.fits(27.4, "ibuypower").values())


def test_candidate_config_is_valid():
    cfg = cb.load_candidates(TRAINING / "config" / "base_candidates.yaml")
    names = [c["name"] for c in cfg["candidates"]]
    assert len(names) == len(set(names)) and "qwen2.5-7b-instruct" in names
    assert all(c["params_b"] > 0 and c["repo"] and c["dir"] for c in cfg["candidates"])
    for bench in cfg["benchmarks"]:
        assert (ROOT / bench).is_file(), bench


def test_leaderboard_for_missing_weights_is_reported_not_crashed(tmp_path):
    out = tmp_path / "bases"
    status = cb.main(["--weights", str(tmp_path / "w"), "--out", str(out), "--only", "qwen3-4b"])
    assert status == 1  # nothing scored
    board = json.loads((out / "leaderboard.json").read_text(encoding="utf-8"))
    assert board["rows"][0]["status"] == "missing"


def test_list_mode_downloads_nothing(capsys, tmp_path):
    assert cb.main(["--list", "--machine", "ibuypower", "--weights", str(tmp_path)]) == 0
    assert "qwen3-4b" in capsys.readouterr().out and not list(tmp_path.iterdir())


def fake_python(tmp_path: Path, body: str) -> str:
    script = tmp_path / "fakepy.sh"
    script.write_text("#!/usr/bin/env bash\n" + body + "\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_run_candidate_ok_failed_and_timeout_kills_the_group(tmp_path):
    ok = cb.run_candidate(fake_python(tmp_path, "exit 0"), tmp_path, [], tmp_path / "o", device="cpu",
                          max_new_tokens=8, timeout_s=20)
    assert ok["status"] == "ok"
    bad = cb.run_candidate(fake_python(tmp_path, "echo boom; exit 3"), tmp_path, [], tmp_path / "o", device="cpu",
                           max_new_tokens=8, timeout_s=20)
    assert bad["status"] == "failed" and bad["returncode"] == 3 and "boom" in bad["tail"]
    marker = "sleep 7773"
    slow = cb.run_candidate(fake_python(tmp_path, f"{marker} & {marker}; wait"), tmp_path, [], tmp_path / "o",
                            device="cpu", max_new_tokens=8, timeout_s=1)
    assert slow["status"] == "timeout"
    assert subprocess.run(["pgrep", "-f", marker], capture_output=True).returncode != 0, "timeout left orphans"


def test_summarize_and_render_leaderboard(tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    (d / "eval_frozen.json").write_text(json.dumps({"accuracy": 0.4, "fairness_gap": 0.02,
                                                    "behaviour": {"abstain": 0.9, "grounded": 0.8}}), encoding="utf-8")
    (d / "eval_behavior_v1.json").write_text(json.dumps({"accuracy": 0.7, "behaviour": {"hint": 0.6, "refuse": 0.4}}),
                                             encoding="utf-8")
    (d / "eval_multilingual_v1.json").write_text(json.dumps({"accuracy": 0.3, "by_language": {"km": 0.2},
                                                             "behaviour": {"language": 1.0}}), encoding="utf-8")
    row = cb.summarize("m", d, [])
    row["status"], row["score"] = "ok", cb.score(row)
    assert row["hint"] == 0.6 and row["multilingual_f1"] == 0.3 and row["by_language_f1"] == {"km": 0.2}
    table = cb.render([row], {"refuse": 0.5})
    assert "below refuse floor 0.5" in table and "m" in table


# ---- behaviour-gated bake-off ----------------------------------------------------------


def test_bakeoff_rejects_a_model_that_wins_overlap_by_guessing():
    cands = [bakeoff.Candidate("base", {"accuracy": 0.30, "abstain": 0.7, "refuse": 0.8, "fairness_gap": 0.0}),
             bakeoff.Candidate("guesser", {"accuracy": 0.60, "abstain": 0.1, "refuse": 0.8, "fairness_gap": 0.0}),
             bakeoff.Candidate("careful", {"accuracy": 0.40, "abstain": 0.9, "refuse": 0.9, "fairness_gap": 0.0})]
    out = bakeoff.run_bakeoff(cands, max_fairness_gap=0.1, min_metrics={"abstain": 0.7, "refuse": 0.8})
    assert out["champion"] == "careful"
    assert {r["name"] for r in out["rejected"]} == {"guesser"} and out["rejected"][0]["reason"] == "metric_floor"


def test_unmeasured_metric_does_not_fail_the_gate():
    cands = [bakeoff.Candidate("a", {"accuracy": 0.5})]
    assert bakeoff.run_bakeoff(cands, min_metrics={"abstain": 0.9})["champion"] == "a"


def write_eval(dir_: Path, f1, abstain, refuse, hint):
    dir_.mkdir(parents=True)
    (dir_ / "eval_frozen.json").write_text(json.dumps({"accuracy": f1, "fairness_gap": 0.0,
                                                       "behaviour": {"abstain": abstain, "grounded": 1.0}}), encoding="utf-8")
    (dir_ / "eval_behavior_v1.json").write_text(json.dumps({"accuracy": 0.5, "behaviour": {
        "refuse": refuse, "hint": hint, "spoken": 1.0}}), encoding="utf-8")


def test_nightly_adapter_must_not_regress_on_behaviour(tmp_path):
    write_eval(tmp_path / "eval" / "base", 0.30, 0.8, 0.8, 0.5)
    write_eval(tmp_path / "eval" / "stem", 0.45, 0.4, 0.8, 0.9)  # better F1, worse abstention
    assert nc.main(["--out", str(tmp_path)]) == 0
    result = json.loads((tmp_path / "bakeoff" / "result.json").read_text(encoding="utf-8"))
    assert result["champion"] == "qwen-base"
    assert result["rejected"][0]["name"] == "stem-qlora"
    floors = (tmp_path / "bakeoff" / "floors.args").read_text(encoding="utf-8")
    assert "--min-metric abstain=0.8" in floors and "--min-metric hint=0.5" in floors


def test_nightly_adapter_wins_when_it_improves_without_regressing(tmp_path):
    write_eval(tmp_path / "eval" / "base", 0.30, 0.8, 0.8, 0.5)
    write_eval(tmp_path / "eval" / "stem", 0.45, 0.9, 0.9, 0.9)
    assert nc.main(["--out", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "bakeoff" / "result.json").read_text(encoding="utf-8"))["champion"] == "stem-qlora"
    assert nc.main(["--out", str(tmp_path), "--note-only"]) == 0
    assert json.loads((tmp_path / "candidate.json").read_text(encoding="utf-8"))["promoted"] is False


def test_nightly_fails_loudly_without_eval_results(tmp_path):
    with pytest.raises(SystemExit):
        nc.main(["--out", str(tmp_path)])


# ---- dataset validation ----------------------------------------------------------------


def test_validate_dataset_rejects_protected_attributes_everywhere():
    ok = {"instruction": "q", "response": "a", "context": {"language": "en"}}
    assert run_finetune.validate_dataset([ok]) == []
    assert run_finetune.validate_dataset([{**ok, "context": {"race": "x"}}])
    assert run_finetune.validate_dataset([{**ok, "ethnicity": "x"}])
    assert run_finetune.validate_dataset([{**ok, "tags": ["Race"]}])


# ---- requirements and scripts ----------------------------------------------------------


def test_spark_requirements_never_pin_or_install_torch():
    active = [l.strip().lower() for l in (TRAINING / "requirements-spark.txt").read_text(encoding="utf-8").splitlines()
              if l.strip() and not l.strip().startswith("#")]
    assert active and not any(l.startswith("torch") for l in active)
    assert not any(l.startswith("bitsandbytes") for l in active)  # optional, never blocks the install
    assert "torch==" in (TRAINING / "requirements.txt").read_text(encoding="utf-8")
    assert "DO NOT USE THIS FILE" in (TRAINING / "requirements.txt").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
@pytest.mark.parametrize("script", ["train.sh", "spark_nightly.sh", "lib_limits.sh", "systemd/install-user-timer.sh"])
def test_shell_scripts_parse(script):
    assert subprocess.run(["bash", "-n", str(TRAINING / script)], capture_output=True).returncode == 0


def test_nightly_wraps_every_long_stage_and_holds_the_lock_with_a_wait():
    text = (TRAINING / "spark_nightly.sh").read_text(encoding="utf-8")
    assert "flock -w" in text and "lib_limits.sh" in text and "gs_preflight" in text
    for stage in ('gs_stage "train"', 'gs_stage "eval-base"', 'gs_stage "eval-adapter"'):
        assert stage in text
    assert "training/quality_gate.py" in text and "floors.args" in text


def test_systemd_unit_has_hard_limits_and_kills_the_whole_group():
    unit = (TRAINING / "systemd" / "aoep-spark-train.service").read_text(encoding="utf-8")
    for needle in ("MemoryMax=@MEMMAX@", "CPUQuota=@CPUQUOTA@", "KillMode=control-group", "OOMPolicy=kill",
                   "SuccessExitStatus=75", "MemorySwapMax=0"):
        assert needle in unit


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_check_only_passes_end_to_end_without_a_gpu():
    env = {**os.environ, "CHECK_ONLY": "1", "PYTHON": sys.executable, "PYTHONPATH": str(ROOT / "packages" / "shared" / "src")}
    proc = subprocess.run(["bash", str(TRAINING / "train.sh")], capture_output=True, text=True, env=env,
                          cwd=str(ROOT), timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CHECK_ONLY ok" in proc.stdout and "quality" not in proc.stderr.lower()
