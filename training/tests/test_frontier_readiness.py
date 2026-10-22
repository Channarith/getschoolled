import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "training"))

import frontier_readiness as report  # noqa: E402
from truth_curve import exam_fields  # noqa: E402


class _Job:
    def __init__(self, course_id: str, n: int) -> None:
        self.course_id = course_id
        self.segments = [{"heading": "H", "text": "T"}] * n


def test_truth_summary_ignores_split_rows_without_an_id():
    rows = [
        {"id": None, "groundedness": 0.0, "abstain_correct": True},
        {"id": "recall-001", "groundedness": 0.8, "abstain_correct": True, "human_agreement": None},
        {"id": "abstain-001", "groundedness": 0.4, "abstain_correct": False, "human_agreement": True},
    ]
    summary = report.summarize_truth(rows)
    assert summary["n"] == 2
    assert summary["groundedness"] == 0.6
    assert summary["abstain_accuracy"] == 0.5
    assert summary["human_agreement"] == 1.0
    assert summary["human_n"] == 1


def test_translation_coverage_counts_matching_lengths_only(tmp_path):
    course = tmp_path / "audio-intro-to-machine-learning"
    course.mkdir()
    (course / "es.json").write_text(
        json.dumps({"segments": [{"text": "a"}, {"text": "b"}]}), encoding="utf-8"
    )
    (course / "zh.json").write_text(
        json.dumps({"segments": [{"text": "a"}]}), encoding="utf-8"
    )
    (course / "yue.partial.json").write_text(
        json.dumps({"segments": [{"text": "粵"}]}), encoding="utf-8"
    )
    jobs = [_Job("audio-intro-to-machine-learning", 2)]
    coverage = report.translation_coverage(jobs, tmp_path, ("es", "zh", "yue"))
    by_code = {row["code"]: row for row in coverage["languages"]}
    assert by_code["es"]["playable"] == 1
    assert by_code["zh"]["playable"] == 0
    assert by_code["yue"]["partial"] == 1
    assert coverage["demo"]["es"] == "playable"
    assert coverage["demo"]["zh"] == "wrong-length"
    assert coverage["demo"]["yue"] == "partial"


def test_batch_progress_reads_the_latest_tally():
    text = "222 courses x 21 languages (4662 jobs)\n[62/4662] skipped x (written=1 skipped=60 failed=2)\n"
    got = report.parse_batch_progress(text)
    assert got == {"done": 62, "total": 4662, "written": 1, "skipped": 60, "failed": 2}


def test_history_does_not_duplicate_an_identical_row(tmp_path):
    path = tmp_path / "history.jsonl"
    row = {"at": "t", "frozen_accuracy": None}
    report.append_history(path, row)
    report.append_history(path, row)
    assert path.read_text(encoding="utf-8").count("\n") == 1


def test_page_names_the_weak_subject_and_the_recheck_command():
    snapshot = report.build_snapshot(spark_out=tmp_unused(), translation={
        "courses": 1,
        "languages": [{"code": "yue", "playable": 0, "partial": 1, "total": 1}],
        "playable": 0,
        "jobs": 1,
        "yue_playable": 0,
        "yue_partial": 1,
        "demo": {"yue": "partial"},
        "demo_course": report.DEMO_COURSE,
    }, batch={"done": 1, "total": 2, "written": 0, "skipped": 0, "failed": 1})
    snapshot["split_subjects"] = [
        {"subject": "linear-algebra", "score": 0.1379, "n": 1, "under_floor": True}
    ]
    snapshot["weakest_split"] = {"subject": "linear-algebra", "score": 0.1379}
    page = report.render_html(snapshot, [])
    assert "linear-algebra" in page
    assert "frontier_readiness.py --record" in page
    assert "Outside cards" in page


def tmp_unused() -> Path:
    return ROOT / "output" / "does-not-need-to-exist"


def test_exam_labels_keep_stem_distinct_from_the_general_frozen_set():
    assert exam_fields("training/data/eval_frozen_stem.jsonl", "adapters/stem") == {
        "exam": "stem",
        "model": "adapter",
    }
    assert exam_fields("training/data/eval_frozen.jsonl", "")["exam"] == "frozen"
    assert exam_fields("output/spark/data/eval.jsonl", "")["exam"] == "split"
