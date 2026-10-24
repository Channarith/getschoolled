#!/usr/bin/env python3
"""Rebuild the frontier-readiness page from the files on this machine.

The page is a measurement, not a drawing. Run it again over the weekend:

  python3 training/frontier_readiness.py --record

It reads the frozen exam, the STEM-subject exam, the curriculum split,
the truth log, and the 222-course translation cache. --record appends one
history row so the next run can plot the change.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from promotion_gate import subject_min, weakest_subject  # noqa: E402

PT = ZoneInfo("America/Los_Angeles")
TRAINING_FLOOR = 0.40
ACCREDITATION_FLOOR = 0.70
TARGET_FROZEN_F1 = 0.70
TARGET_GROUNDEDNESS = 0.90
DEMO_COURSE = "audio-intro-to-machine-learning"
SPARK_LANGS = (
    "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "uk", "tr",
    "ar", "he", "hi", "bn", "ur", "fa", "zh", "ja", "ko", "vi", "yue",
)


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def summarize_truth(rows: list[dict]) -> dict:
    """Groundedness counts only rows that name an item.

    The curriculum split has no passage, so those rows score 0 and would
    flatten the curve. Frozen and STEM rows carry an id.
    """
    scored = [row for row in rows if row.get("id")]
    grounded = [float(row["groundedness"]) for row in scored if "groundedness" in row]
    abstain = [1.0 if row.get("abstain_correct") else 0.0 for row in scored if "abstain_correct" in row]
    human = [row["human_agreement"] for row in scored if row.get("human_agreement") is not None]
    agreed = sum(1 for value in human if value is True)
    return {
        "n": len(scored),
        "groundedness": round(sum(grounded) / len(grounded), 4) if grounded else None,
        "abstain_accuracy": round(sum(abstain) / len(abstain), 4) if abstain else None,
        "human_agreement": round(agreed / len(human), 4) if human else None,
        "human_n": len(human),
    }


def subject_rows(metrics: dict | None) -> list[dict]:
    if not metrics:
        return []
    scores = metrics.get("by_category") or {}
    counts = metrics.get("by_category_n") or {}
    rows = []
    for name, score in scores.items():
        rows.append({
            "subject": str(name),
            "score": float(score),
            "n": int(counts.get(name, 0)),
            "under_floor": float(score) < TRAINING_FLOOR,
        })
    rows.sort(key=lambda row: (row["score"], row["subject"]))
    return rows


def _segments(path: Path) -> int | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    segs = data.get("segments")
    return len(segs) if isinstance(segs, list) else None


def translation_coverage(jobs: list, root: Path, languages: tuple[str, ...] = SPARK_LANGS) -> dict:
    """Count playable files: segment count matches the course."""
    per_lang = {code: {"playable": 0, "partial": 0} for code in languages}
    demo = {code: "missing" for code in languages}
    total = len(jobs)
    for job in jobs:
        expected = len(getattr(job, "segments", []) or [])
        course_id = str(getattr(job, "course_id", ""))
        folder = root / course_id
        for code in languages:
            finished = folder / f"{code}.json"
            partial = folder / f"{code}.partial.json"
            n = _segments(finished) if finished.is_file() else None
            playable = n == expected and expected > 0
            if playable:
                per_lang[code]["playable"] += 1
            elif partial.is_file():
                per_lang[code]["partial"] += 1
            if course_id == DEMO_COURSE:
                if playable:
                    demo[code] = "playable"
                elif partial.is_file():
                    demo[code] = "partial"
                elif n is not None:
                    demo[code] = "wrong-length"
    languages_out = [
        {"code": code, "playable": per_lang[code]["playable"], "partial": per_lang[code]["partial"], "total": total}
        for code in languages
    ]
    yue = per_lang.get("yue", {"playable": 0, "partial": 0})
    return {
        "courses": total,
        "languages": languages_out,
        "playable": sum(row["playable"] for row in languages_out),
        "jobs": total * len(languages),
        "yue_playable": yue["playable"],
        "yue_partial": yue["partial"],
        "demo": demo,
        "demo_course": DEMO_COURSE,
    }


def latest_batch_progress(paths: list[Path]) -> dict | None:
    """Use the log that has moved farthest through the 222-course run."""
    best = None
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_bytes().replace(b"\x00", b"").decode("utf-8", "replace")
        marker = text.rfind("222 courses x 21")
        got = parse_batch_progress(text[marker:] if marker >= 0 else text)
        if got and (best is None or got["done"] >= best["done"]):
            best = got
    return best


_TALLY = re.compile(
    r"\[(\d+)/(\d+)\].*?\(written=(\d+) skipped=(\d+) failed=(\d+)\)"
)


def parse_batch_progress(text: str) -> dict | None:
    last = None
    for line in text.splitlines():
        match = _TALLY.search(line)
        if match:
            last = match
    if last is None:
        return None
    done, total, written, skipped, failed = (int(part) for part in last.groups())
    return {
        "done": done,
        "total": total,
        "written": written,
        "skipped": skipped,
        "failed": failed,
    }


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _weak(metrics: dict | None) -> dict | None:
    if not metrics:
        return None
    found = weakest_subject(metrics.get("by_category") or {}, metrics.get("by_category_n") or {})
    if found is None:
        return None
    name, score = found
    return {"subject": name, "score": score}


def build_snapshot(
    *,
    spark_out: Path,
    translation: dict | None = None,
    batch: dict | None = None,
    now: datetime | None = None,
) -> dict:
    stamp = now or datetime.now(PT)
    split = _load_json(spark_out / "eval" / "stem.json")
    frozen = _load_json(spark_out / "eval" / "stem.frozen.json")
    stem = _load_json(spark_out / "eval" / "stem.stemfrozen.json")
    base = _load_json(spark_out / "eval" / "base.json")
    base_frozen = _load_json(spark_out / "eval" / "base.frozen.json")
    promote = _load_json(spark_out / "bakeoff" / "promote.json")
    served = _load_json(spark_out / "eval" / "serving.json")
    truth = summarize_truth(_read_jsonl(spark_out / "truth_curve.jsonl"))
    stem_items = _read_jsonl(ROOT / "training" / "data" / "eval_frozen_stem.jsonl")
    stem_counts: dict[str, int] = {}
    for row in stem_items:
        tags = row.get("tags") or []
        if tags:
            stem_counts[str(tags[0])] = stem_counts.get(str(tags[0]), 0) + 1
    return {
        "at": stamp.strftime("%Y-%m-%d %I:%M %p PT").replace(" 0", " "),
        "split_accuracy": None if not split else split.get("accuracy"),
        "split_base": None if not base else base.get("accuracy"),
        "split_subject_min": subject_min((split or {}).get("by_category") or {}, (split or {}).get("by_category_n") or {}),
        "weakest_split": _weak(split),
        "split_subjects": subject_rows(split),
        "frozen_accuracy": None if not frozen else frozen.get("accuracy"),
        "frozen_base": None if not base_frozen else base_frozen.get("accuracy"),
        "frozen_subject_min": subject_min((frozen or {}).get("by_category") or {}, (frozen or {}).get("by_category_n") or {}),
        "weakest_frozen": _weak(frozen),
        "frozen_subjects": subject_rows(frozen),
        "frozen_gap": None if not frozen else frozen.get("fairness_gap"),
        "stem_accuracy": None if not stem else stem.get("accuracy"),
        "stem_subject_min": subject_min((stem or {}).get("by_category") or {}, (stem or {}).get("by_category_n") or {}),
        "weakest_stem": _weak(stem),
        "stem_subjects": subject_rows(stem),
        "stem_gap": None if not stem else stem.get("fairness_gap"),
        "split_gap": None if not split else split.get("fairness_gap"),
        "stem_exam_items": len(stem_items),
        "stem_exam_subjects": stem_counts,
        "truth": truth,
        "promoted": None if not promote else promote.get("promoted"),
        "promote_reason": None if not promote else promote.get("reason"),
        "promote_champion": None if not promote else promote.get("champion"),
        "served_accuracy": None if not served else served.get("accuracy"),
        "served_gap": None if not served else served.get("fairness_gap"),
        "served_n": None if not served else served.get("n"),
        "weakest_served": _weak(served),
        "translation": translation,
        "batch": batch,
        "training_floor": TRAINING_FLOOR,
        "accreditation_floor": ACCREDITATION_FLOOR,
        "target_frozen_f1": TARGET_FROZEN_F1,
        "cards": 0,
    }


def history_row(snapshot: dict) -> dict:
    truth = snapshot["truth"]
    translation = snapshot.get("translation") or {}
    return {
        "at": snapshot["at"],
        "split_accuracy": snapshot["split_accuracy"],
        "split_subject_min": snapshot["split_subject_min"],
        "weakest_split": snapshot["weakest_split"],
        "frozen_accuracy": snapshot["frozen_accuracy"],
        "stem_accuracy": snapshot["stem_accuracy"],
        "stem_subject_min": snapshot["stem_subject_min"],
        "groundedness": truth.get("groundedness"),
        "abstain_accuracy": truth.get("abstain_accuracy"),
        "human_agreement": truth.get("human_agreement"),
        "yue_playable": translation.get("yue_playable"),
        "playable": translation.get("playable"),
        "promoted": snapshot["promoted"],
        "promote_reason": snapshot["promote_reason"],
    }


def append_history(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = _read_jsonl(path)
    if previous and previous[-1] == row:
        return
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _bar(score: float, floor: float) -> str:
    width = max(0, min(100, score * 100))
    color = "#e07a6a" if score < floor else "#3dbea5"
    floor_x = floor * 100
    return (
        f'<div class="bar"><span style="width:{width:.1f}%;background:{color}"></span>'
        f'<i style="left:{floor_x:.1f}%"></i></div>'
    )


def render_html(snapshot: dict, history: list[dict]) -> str:
    from frontier_page import render_briefing

    return render_briefing(snapshot, history)


def _catalog_jobs():
    sys.path.insert(0, str(ROOT / "scripts"))
    import translate_courses_batch as batch

    return batch.audio_jobs(0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spark-out", default=str(ROOT / "output" / "spark"))
    ap.add_argument("--translation-dir", default=str(Path.home() / ".cache" / "aoep" / "course_translations"))
    ap.add_argument("--html", action="append", default=[])
    ap.add_argument("--history", default="")
    ap.add_argument(
        "--batch-log",
        action="append",
        default=[],
        help="Translation log. Repeatable. Default: the live service log and ~/batch-spark.log.",
    )
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--skip-catalog", action="store_true")
    args = ap.parse_args(argv)

    spark_out = Path(args.spark_out)
    translation = None
    if not args.skip_catalog:
        translation = translation_coverage(_catalog_jobs(), Path(args.translation_dir))
    log_paths = [Path(raw) for raw in args.batch_log] or [
        Path.home() / ".local" / "share" / "aoep-train" / "translate.log",
        Path.home() / "batch-spark.log",
    ]
    batch = latest_batch_progress(log_paths)
    snapshot = build_snapshot(spark_out=spark_out, translation=translation, batch=batch)
    history_path = Path(args.history or (spark_out / "readiness_history.jsonl"))
    if args.record:
        append_history(history_path, history_row(snapshot))
    history = _read_jsonl(history_path)
    page = render_html(snapshot, history)
    targets = args.html or [
        str(spark_out / "frontier-readiness.html"),
        str(ROOT / "docs" / "status" / "frontier-readiness.html"),
        str(ROOT / "docs" / "frontier-readiness.html"),
    ]
    for raw in targets:
        dest = Path(raw)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")
        print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
