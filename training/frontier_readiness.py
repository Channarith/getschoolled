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
import html
import json
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


def parse_batch_progress(text: str) -> dict | None:
    last = None
    for line in text.splitlines():
        if "/4662]" in line or "] " in line and "written=" in line:
            last = line.strip()
    if not last or "written=" not in last:
        return None
    # [62/4662] skipped ... (written=0 skipped=60 failed=2)
    try:
        head, tail = last.split("]", 1)
        done, total = head.strip().lstrip("[").split("/")
        parts = tail[tail.rfind("(") + 1:tail.rfind(")")].split()
        fields = dict(piece.split("=", 1) for piece in parts if "=" in piece)
        return {
            "done": int(done),
            "total": int(total),
            "written": int(fields.get("written", 0)),
            "skipped": int(fields.get("skipped", 0)),
            "failed": int(fields.get("failed", 0)),
        }
    except (ValueError, IndexError):
        return None


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
        "stem_accuracy": None if not stem else stem.get("accuracy"),
        "stem_subject_min": subject_min((stem or {}).get("by_category") or {}, (stem or {}).get("by_category_n") or {}),
        "weakest_stem": _weak(stem),
        "stem_exam_items": len(stem_items),
        "stem_exam_subjects": stem_counts,
        "truth": truth,
        "promoted": None if not promote else promote.get("promoted"),
        "promote_reason": None if not promote else promote.get("reason"),
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
    e = html.escape
    weak = snapshot.get("weakest_split") or {}
    truth = snapshot["truth"]
    translation = snapshot.get("translation") or {}
    batch = snapshot.get("batch")
    subjects = snapshot["split_subjects"]
    subject_html = []
    for row in subjects:
        subject_html.append(
            "<tr><td>" + e(row["subject"]) + "</td><td>" + _pct(row["score"]) +
            "</td><td>" + str(row["n"]) + "</td><td>" + _bar(row["score"], TRAINING_FLOOR) + "</td></tr>"
        )
    lang_html = []
    for row in translation.get("languages") or []:
        lang_html.append(
            "<tr><td>" + e(row["code"]) + "</td><td>" + str(row["playable"]) +
            "/" + str(row["total"]) + "</td><td>" + str(row["partial"]) + "</td></tr>"
        )
    demo = translation.get("demo") or {}
    demo_bits = ", ".join(f"{e(code)} {e(state)}" for code, state in demo.items() if state != "missing") or "none playable yet"
    hist_bits = []
    for row in history[-12:]:
        hist_bits.append(
            "<tr><td>" + e(str(row.get("at"))) + "</td><td>" + _pct(row.get("frozen_accuracy")) +
            "</td><td>" + _pct(row.get("split_subject_min")) + "</td><td>" +
            _pct(row.get("groundedness")) + "</td><td>" + str(row.get("yue_playable")) +
            "</td><td>" + e(str(row.get("promote_reason") or "")) + "</td></tr>"
        )
    batch_line = "The batch log has no progress line yet."
    if batch:
        batch_line = (
            f"Batch {batch['done']}/{batch['total']}: written {batch['written']}, "
            f"skipped {batch['skipped']}, failed {batch['failed']}."
        )
    algebra_n = snapshot["stem_exam_subjects"].get("linear-algebra", 0)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Salareen frontier readiness — {e(snapshot["at"])}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#0e141b; color:#e7ecf1; font:16px/1.45 Palatino, "Palatino Linotype", serif; }}
  header, main, footer {{ max-width:1080px; margin:0 auto; padding:28px 22px 8px; }}
  h1 {{ font-size:32px; letter-spacing:-0.03em; margin:0 0 8px; }}
  h2 {{ font-size:22px; margin:32px 0 8px; }}
  .meta, td, th, .card span {{ font:13px/1.35 ui-sans-serif, system-ui, sans-serif; }}
  .meta {{ color:#8b98a5; }}
  .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }}
  .card {{ background:#161d26; border:1px solid #2a3542; border-radius:14px; padding:14px; }}
  .card b {{ display:block; font:22px/1.1 ui-sans-serif, system-ui, sans-serif; }}
  .card span {{ color:#8b98a5; }}
  table {{ width:100%; border-collapse:collapse; }}
  th, td {{ text-align:left; padding:6px 8px; border-bottom:1px solid #2a3542; }}
  .bar {{ position:relative; height:10px; background:#243140; border-radius:6px; }}
  .bar span {{ display:block; height:10px; border-radius:6px; }}
  .bar i {{ position:absolute; top:-2px; width:2px; height:14px; background:#e6b35a; }}
  code {{ font:12px/1.4 ui-monospace, monospace; }}
  @media (max-width:800px) {{ .grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header>
  <h1>Frontier readiness, measured.</h1>
  <p class="meta">Snapshot {e(snapshot["at"])}. Rebuild with <code>python3 training/frontier_readiness.py --record</code> from the spark-eval-gates tree. The amber tick on each bar is the {TRAINING_FLOOR:.0%} training floor. Accreditation stays at {ACCREDITATION_FLOOR:.0%} and still does not print an outside card.</p>
</header>
<main>
  <section class="grid">
    <div class="card"><b>{_pct(snapshot["split_accuracy"])}</b><span>STEM adapter on the 41-item split. Base is {_pct(snapshot["split_base"])}. Weakest sampled subject: {e(str(weak.get("subject") or "—"))} {_pct(weak.get("score"))}.</span></div>
    <div class="card"><b>{_pct(snapshot["frozen_accuracy"])}</b><span>Adapter on the frozen 200-item exam. Base {_pct(snapshot["frozen_base"])}. Target {_pct(snapshot["target_frozen_f1"])}. A blank means this cycle has not finished that file.</span></div>
    <div class="card"><b>{_pct(snapshot["stem_accuracy"])}</b><span>Adapter on the frozen STEM exam ({snapshot["stem_exam_items"]} items, linear algebra n={algebra_n}). Subject floor {_pct(snapshot["stem_subject_min"])}.</span></div>
    <div class="card"><b>{snapshot["cards"]}</b><span>Outside cards. A person of record and a {ACCREDITATION_FLOOR:.0%} subject floor are required even to ask. Salareen does not print the card.</span></div>
  </section>

  <h2>Subjects on the curriculum split</h2>
  <p>Every sampled subject counts, including a subject with one item. Promotion needs each of them at or above {TRAINING_FLOOR:.0%}, and a higher frozen-exam score than the last kept adapter.</p>
  <table>
    <tr><th>Subject</th><th>Score</th><th>Items</th><th>Against the floor</th></tr>
    {"".join(subject_html) or "<tr><td colspan=4>No split metrics yet.</td></tr>"}
  </table>

  <h2>Truth curve</h2>
  <p>Groundedness {_pct(truth["groundedness"])} on {truth["n"]} frozen-style rows. Abstention {_pct(truth["abstain_accuracy"])}. Human agreement {_pct(truth["human_agreement"])} from {truth["human_n"]} reviews. The target for groundedness is {_pct(TARGET_GROUNDEDNESS)}. Empty human agreement means nobody has reviewed a row yet.</p>

  <h2>222-course translation</h2>
  <p>{e(batch_line)} Playable files match the lesson length. Cantonese is yue.json: {translation.get("yue_playable", 0)} playable, {translation.get("yue_partial", 0)} still partial. Demo {e(translation.get("demo_course") or DEMO_COURSE)}: {demo_bits}.</p>
  <table>
    <tr><th>Language</th><th>Playable</th><th>Partial</th></tr>
    {"".join(lang_html) or "<tr><td colspan=3>Translation cache was not scanned.</td></tr>"}
  </table>

  <h2>Promotion</h2>
  <p>Last gate: {e(str(snapshot["promote_reason"] or "not run yet"))}. Promoted: {e(str(snapshot["promoted"]))}. A repeated win over the base is not a kept adapter.</p>

  <h2>History</h2>
  <table>
    <tr><th>When</th><th>Frozen</th><th>Weakest split</th><th>Groundedness</th><th>Cantonese playable</th><th>Gate</th></tr>
    {"".join(hist_bits) or "<tr><td colspan=6>No history yet. This snapshot is the baseline.</td></tr>"}
  </table>
</main>
<footer>
  <p>Weekend recheck: run the command in the header and compare frozen accuracy, the weakest subject, groundedness, and Cantonese playable files with the row above.</p>
</footer>
</body>
</html>
"""


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
    ap.add_argument("--batch-log", default=str(Path.home() / "batch-spark.log"))
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--skip-catalog", action="store_true")
    args = ap.parse_args(argv)

    spark_out = Path(args.spark_out)
    translation = None
    if not args.skip_catalog:
        translation = translation_coverage(_catalog_jobs(), Path(args.translation_dir))
    batch = None
    log_path = Path(args.batch_log)
    if log_path.is_file():
        text = log_path.read_bytes().replace(b"\x00", b"").decode("utf-8", "replace")
        marker = text.rfind("222 courses x 21")
        batch = parse_batch_progress(text[marker:] if marker >= 0 else text)
    snapshot = build_snapshot(spark_out=spark_out, translation=translation, batch=batch)
    history_path = Path(args.history or (spark_out / "readiness_history.jsonl"))
    if args.record:
        append_history(history_path, history_row(snapshot))
    history = _read_jsonl(history_path)
    page = render_html(snapshot, history)
    targets = args.html or [
        str(spark_out / "frontier-readiness.html"),
        str(ROOT / "docs" / "status" / "frontier-readiness.html"),
    ]
    for raw in targets:
        dest = Path(raw)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")
        print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
