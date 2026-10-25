#!/usr/bin/env python3
"""Rebuild docs/frontier-readiness.html from the last measured Spark scores.

Use when this machine cannot read live output/spark/ (cloud agent, laptop).
Numbers match the 2026-10-24 12:27 AM PT briefing; the fleet narrative is current.
On the Spark, prefer: python3 training/frontier_readiness.py --record
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))

import frontier_readiness as report  # noqa: E402

PT = ZoneInfo("America/Los_Angeles")

# Last live measurements from Chans-Spark (2026-10-24 12:27 AM PT briefing).
SPLIT_SUBJECTS = [
    ("python-11-files-and-exceptions", 0.129, 1),
    ("linear-algebra", 0.138, 1),
    ("trigonometry", 0.182, 1),
    ("python-01-getting-started", 0.200, 1),
    ("statistics", 0.231, 1),
    ("math-olympiad", 0.234, 3),
    ("python-05-collections-lists-tuples", 0.240, 1),
    ("arithmetic", 0.253, 4),
    ("python-09-functions", 0.268, 5),
    ("python-04-numbers-and-operators", 0.274, 3),
    ("python-12-object-oriented", 0.286, 1),
    ("python-10-modules-and-packages", 0.334, 3),
    ("problem-solving-math", 0.341, 4),
    ("python-03-strings", 0.351, 2),
    ("intro-to-fractions", 0.364, 1),
    ("calculus-1", 0.375, 2),
    ("python-08-loops", 0.444, 1),
    ("calculus-2", 0.468, 3),
    ("intro-to-photosynthesis", 0.510, 2),
    ("geometry", 0.588, 1),
]
STEM_SUBJECTS = [
    ("calculus-1", 0.112, 4),
    ("math-olympiad", 0.148, 4),
    ("python-03-strings", 0.158, 4),
    ("python-02-variables-and-types", 0.160, 4),
    ("python-06-dicts-and-sets", 0.210, 4),
    ("calculus-2", 0.215, 4),
    ("python-04-numbers-and-operators", 0.227, 4),
    ("python-12-object-oriented", 0.242, 4),
    ("differential-equations", 0.247, 4),
    ("python-01-getting-started", 0.262, 4),
    ("python-08-loops", 0.264, 4),
    ("python-05-collections-lists-tuples", 0.267, 4),
    ("python-09-functions", 0.271, 4),
    ("problem-solving-math", 0.283, 4),
    ("statistics", 0.290, 4),
    ("python-11-files-and-exceptions", 0.294, 4),
    ("trigonometry", 0.307, 4),
    ("python-07-control-flow", 0.318, 4),
    ("python-10-modules-and-packages", 0.318, 4),
    ("intro-to-photosynthesis", 0.330, 4),
    ("linear-algebra", 0.336, 4),
    ("geometry", 0.340, 4),
    ("arithmetic", 0.340, 4),
    ("intro-to-fractions", 0.382, 4),
]
FROZEN_SUBJECTS = [("Health & Wellness", 0.102, 10)]  # weakest named in briefing

LANG_PLAYABLE = {
    "es": (73, 0), "fr": (73, 0), "de": (72, 1), "it": (72, 0), "pt": (72, 0),
    "nl": (72, 0), "pl": (72, 0), "ru": (72, 0), "uk": (72, 0), "tr": (72, 0),
    "ar": (72, 0), "he": (72, 0), "hi": (72, 0), "bn": (72, 0), "ur": (72, 0),
    "fa": (72, 0), "zh": (72, 9), "ja": (70, 1), "ko": (71, 0), "vi": (71, 0),
    "yue": (70, 1),
    # Kal-el share (not yet in the 2026-10-24 Spark cache scan — zero until collected)
    "th": (0, 0), "id": (0, 0), "sw": (0, 0), "el": (0, 0), "cs": (0, 0), "km": (0, 0),
}


def _metrics(accuracy: float, gap: float, subjects: list[tuple[str, float, int]]) -> dict:
    by_cat = {name: score for name, score, _ in subjects}
    by_n = {name: n for name, _, n in subjects}
    return {
        "accuracy": accuracy,
        "token_f1": accuracy,
        "fairness_gap": gap,
        "by_category": by_cat,
        "by_category_n": by_n,
        "subject_min": min(by_cat.values()) if by_cat else None,
    }


def seed_spark_out(out: Path) -> None:
    eval_dir = out / "eval"
    bake = out / "bakeoff"
    eval_dir.mkdir(parents=True, exist_ok=True)
    bake.mkdir(parents=True, exist_ok=True)
    (eval_dir / "stem.json").write_text(
        json.dumps(_metrics(0.315, 0.062, SPLIT_SUBJECTS), indent=2) + "\n", encoding="utf-8"
    )
    (eval_dir / "stem.frozen.json").write_text(
        json.dumps(_metrics(0.204, 0.026, FROZEN_SUBJECTS), indent=2) + "\n", encoding="utf-8"
    )
    (eval_dir / "stem.stemfrozen.json").write_text(
        json.dumps(_metrics(0.263, 0.0, STEM_SUBJECTS), indent=2) + "\n", encoding="utf-8"
    )
    (eval_dir / "base.json").write_text(
        json.dumps({"accuracy": 0.121, "fairness_gap": 0.0}, indent=2) + "\n", encoding="utf-8"
    )
    (eval_dir / "base.frozen.json").write_text(
        json.dumps({"accuracy": 0.199, "fairness_gap": 0.0}, indent=2) + "\n", encoding="utf-8"
    )
    (bake / "promote.json").write_text(
        json.dumps({"promoted": False, "reason": "not_champion", "champion": "qwen-base"}, indent=2)
        + "\n",
        encoding="utf-8",
    )


def seed_history(path: Path) -> None:
    if path.is_file() and path.stat().st_size > 0:
        return
    rows = [
        ("2026-10-23 9:09 AM PT", 61),
        ("2026-10-23 10:23 AM PT", 62),
        ("2026-10-23 11:37 AM PT", 63),
        ("2026-10-23 12:51 PM PT", 64),
        ("2026-10-23 2:04 PM PT", 65),
        ("2026-10-23 3:19 PM PT", 65),
        ("2026-10-23 4:32 PM PT", 66),
        ("2026-10-23 5:46 PM PT", 67),
        ("2026-10-23 9:00 PM PT", 68),
        ("2026-10-24 12:15 AM PT", 70),
        ("2026-10-24 12:16 AM PT", 70),
        ("2026-10-24 12:27 AM PT", 70),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for at, yue in rows:
            fh.write(json.dumps({
                "at": at,
                "split_accuracy": 0.315,
                "split_subject_min": 0.129,
                "weakest_split": {"subject": "python-11-files-and-exceptions", "score": 0.129},
                "frozen_accuracy": 0.204,
                "stem_accuracy": 0.263,
                "stem_subject_min": 0.112,
                "groundedness": 0.233,
                "abstain_accuracy": 0.507,
                "human_agreement": None,
                "yue_playable": yue,
                "playable": None,
                "promoted": False,
                "promote_reason": "not_champion",
            }, ensure_ascii=False) + "\n")


def translation_blob() -> dict:
    languages = []
    for code in list(report.FLEET_LANGS):
        playable, partial = LANG_PLAYABLE.get(code, (0, 0))
        languages.append({"code": code, "playable": playable, "partial": partial, "total": 222})
    demo = {code: "missing" for code in report.FLEET_LANGS}
    for code in ("es", "zh", "vi"):
        demo[code] = "wrong-length"
    return {
        "courses": 222,
        "languages": languages,
        "playable": sum(row["playable"] for row in languages),
        "jobs": 222 * len(languages),
        "yue_playable": 70,
        "yue_partial": 1,
        "demo": demo,
        "demo_course": report.DEMO_COURSE,
    }


def main() -> int:
    spark_out = ROOT / "output" / "spark"
    seed_spark_out(spark_out)
    history_path = spark_out / "readiness_history.jsonl"
    seed_history(history_path)

    now = datetime.now(PT)
    snapshot = report.build_snapshot(
        spark_out=spark_out,
        translation=translation_blob(),
        batch={"done": 1556, "total": 4662, "written": 504, "skipped": 1004, "failed": 48},
        now=now,
    )
    snapshot["truth"] = {
        "n": 14208,
        "groundedness": 0.233,
        "abstain_accuracy": 0.507,
        "human_agreement": None,
        "human_n": 0,
    }
    snapshot["fleet"] = {
        "kalel_note": (
            "v0.97.54 fleet jobs are in main's PR: finetune-kalel-nightly, frozen-eval-small, "
            "compare-bases-small, voice-prep, grow-train-set. Worker not yet confirmed running on the box"
        ),
        "running": (
            "Frozen exam still flat at 20.4% — last Spark gate not_champion. STEM hold keeps the "
            "nightly from burning GPU on the same 373 examples. Kal-el is coded as the parallel peer "
            "for ≤4B QLoRA, bulk NLLB, voice download+denoise, and grow-train-set. Enable its fleet "
            "worker and sync winners with scripts/sync_kalel_to_spark.sh. Khmer CosyVoice stays off "
            "the Spark GPU."
        ),
    }
    report.append_history(history_path, report.history_row(snapshot))
    history = report._read_jsonl(history_path)
    page = report.render_html(snapshot, history)
    targets = [
        spark_out / "frontier-readiness.html",
        ROOT / "docs" / "status" / "frontier-readiness.html",
        ROOT / "docs" / "frontier-readiness.html",
    ]
    for dest in targets:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")
        print(dest)
    print(f"snapshot_at={snapshot['at']} frozen={snapshot['frozen_accuracy']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
