import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "training"))
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

import build_eval_set  # noqa: E402


def test_benchmark_is_balanced_deterministic_and_has_audience_groups():
    first = build_eval_set.build_items(per_kind=20)
    again = build_eval_set.build_items(per_kind=20)
    assert first == again
    kinds = [i["tags"][1] for i in first]
    assert kinds.count("recall") == kinds.count("abstain") == 20
    assert {i["context"]["reading_level"] for i in first} == set(build_eval_set.LEVELS)
    assert all(i["response"] and i["instruction"] and i["source"] == "synthetic-v1" for i in first)


def test_abstain_items_ask_about_a_different_topic_than_the_passage():
    for item in build_eval_set.build_items(per_kind=15):
        if item["tags"][1] != "abstain":
            continue
        title = item["instruction"].split("'")[1]
        asked = item["instruction"].rsplit("about ", 1)[1].rstrip("?")
        assert title != asked


def test_stem_exam_includes_linear_algebra_and_is_deterministic():
    curriculum = ROOT / "sample-curriculum"
    first = build_eval_set.build_stem_items(curriculum, per_course=2)
    again = build_eval_set.build_stem_items(curriculum, per_course=2)
    assert first == again
    ids = [item["id"] for item in first]
    assert len(ids) == len(set(ids))
    algebra = [item for item in first if item["tags"][0] == "linear-algebra"]
    assert len(algebra) >= 3
    assert {item["tags"][1] for item in algebra} == {"recall", "abstain"}
    assert all(item["passage"] and item["source"] == "synthetic-v1" for item in algebra)
    committed = ROOT / "training" / "data" / "eval_frozen_stem.jsonl"
    rows = [json.loads(line) for line in committed.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [row["id"] for row in rows] == ids


def test_committed_frozen_set_is_valid_jsonl():
    path = ROOT / "training" / "data" / "eval_frozen.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= 200 and len({r["id"] for r in rows}) == len(rows)
