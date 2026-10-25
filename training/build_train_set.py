#!/usr/bin/env python3
"""Grow the training set from the three sources that can move the frozen score, and say where to aim.

Why: the nightly fine-tunes the same 373 examples for one epoch, so the adapter (and the 20.4% frozen
score) never changes. More cycles cannot help; more and better data can.

Sources, all passed through the same quality gate (dedupe, PII scrub, consent, language, no protected
attributes) in training/pipeline/quality.py:
  1. authored sessions   output/spark/data/sessions.json and tutor_sessions.json (sample-curriculum)
  2. staff-reviewed gold pairs from the translation review lab (human-checked targets)
  3. consent-gated class sessions: kept ONLY with explicit consent (opt-in / guardian-opt-in) and a source

  python3 training/build_train_set.py --report-only
  python3 training/build_train_set.py --gold-pairs export/gold_pairs.jsonl --out output/spark/data/sessions.grown.json

Never trains and never uses race or ethnicity. Writes the grown sessions (unless --report-only), a
manifest with counts per subject, language, source and consent, and needs_data.json listing the subjects
under the floor with how many training examples they have.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline.quality import run_gate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SESSIONS = ("output/spark/data/sessions.json", "output/spark/data/tutor_sessions.json")
DEFAULT_METRICS = (
    "output/spark/eval/stem.frozen.json",
    "output/spark/eval/stem.stemfrozen.json",
    "output/spark/eval/stem.json",
)
CLASS_CONSENT = {"opt-in", "guardian-opt-in"}
LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "vi": "Vietnamese", "th": "Thai", "km": "Khmer", "zh": "Chinese",
    "sw": "Swahili", "bn": "Bengali", "hi": "Hindi", "fr": "French", "de": "German", "ja": "Japanese",
    "ko": "Korean", "ar": "Arabic", "pt": "Portuguese", "ru": "Russian", "it": "Italian", "id": "Indonesian",
}
# Weakest subjects in the 2026-10-24 briefing, used only when no metrics files are available.
BRIEFING_WEAK = {
    "Health & Wellness": 0.102,
    "calculus-1": 0.112,
    "python-11-files-and-exceptions": 0.129,
    "linear-algebra": 0.336,
}


def read_json_or_jsonl(path: Path) -> List[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        return [row for row in data if isinstance(row, dict)]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def load_sessions(paths: Iterable[Path]) -> List[dict]:
    rows: List[dict] = []
    for path in paths:
        if path.is_file():
            rows.extend(read_json_or_jsonl(path))
    return rows


def gold_pair_sessions(pairs: Sequence[dict]) -> List[dict]:
    """Reviewed (source, target) translation pairs become short tutoring sessions in the target language.

    Only pairs a staff reviewer finalised are used (``target`` present); the English source passage is the
    question context and the reviewed target is the answer, so the model learns the reviewed wording.
    """
    sessions: List[dict] = []
    for pair in pairs:
        target = str(pair.get("target") or "").strip()
        source = pair.get("source") or {}
        heading = str(source.get("heading") or "").strip()
        text = str(source.get("text") or "").strip()
        lang = str(pair.get("lang") or "").strip()
        if not target or not lang or not (heading or text):
            continue
        sessions.append({
            "audience": {"age_band": "adult", "language": lang, "reading_level": "intermediate",
                         "learning_style": "reading", "professionalism": "neutral", "prior_mastery": 0.5},
            "turns": [
                {"role": "student",
                 "text": f"Say this in {LANGUAGE_NAMES.get(lang, lang)}: {heading}. {text}".strip()},
                {"role": "teacher", "text": target},
            ],
            "rewards": [1.0],
            "tags": ["translation-gold", lang],
            "source": f"review-lab:{pair.get('key', 'unit')}",
            "consent": "staff-reviewed",
        })
    return sessions


def consented_class_sessions(rows: Sequence[dict]) -> tuple[List[dict], Dict[str, int]]:
    """Keep a class session only with explicit consent and a source. Everything else is counted and dropped."""
    kept: List[dict] = []
    dropped: Dict[str, int] = {}
    for row in rows:
        consent = str(row.get("consent") or "").strip()
        if consent not in CLASS_CONSENT:
            dropped["no_explicit_consent"] = dropped.get("no_explicit_consent", 0) + 1
            continue
        if not str(row.get("source") or "").strip():
            dropped["no_source"] = dropped.get("no_source", 0) + 1
            continue
        kept.append(row)
    return kept, dropped


def subject_of(session: dict) -> str:
    tags = session.get("tags") or []
    return str(tags[0]) if tags else "untagged"


def _count(sessions: Iterable[dict], key) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for session in sessions:
        name = str(key(session))
        out[name] = out.get(name, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def load_subject_scores(paths: Iterable[Path]) -> Dict[str, dict]:
    """Per-subject score and item count from evaluate.py metrics files (lowest score wins across files)."""
    scores: Dict[str, dict] = {}
    for path in paths:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        counts = data.get("by_category_n") or {}
        for subject, score in (data.get("by_category") or {}).items():
            current = scores.get(subject)
            if current is None or float(score) < current["score"]:
                scores[subject] = {"score": float(score), "eval_n": int(counts.get(subject, 0)), "exam": path.name}
    return scores


def _matches(subject: str, session_subject: str) -> bool:
    a, b = subject.lower(), session_subject.lower()
    return a == b or a in b or b in a


def needs_data(clean: Sequence[dict], scores: Dict[str, dict], floor: float, *, target_examples: int = 30) -> List[dict]:
    """Subjects under the floor, with how many training examples they have and how many to add."""
    train_counts = _count(clean, subject_of)
    rows: List[dict] = []
    for subject, info in sorted(scores.items(), key=lambda kv: kv[1]["score"]):
        if info["score"] >= floor:
            continue
        have = sum(n for name, n in train_counts.items() if _matches(subject, name))
        rows.append({"subject": subject, "score": round(info["score"], 4), "eval_n": info["eval_n"],
                     "exam": info["exam"], "train_examples": have,
                     "suggested_new_examples": max(0, target_examples - have),
                     "note": _note(have, target_examples)})
    return rows


def _note(have: int, target_examples: int) -> str:
    if have == 0:
        return "no training examples at all"
    if have >= target_examples:
        return "has data but is still under the floor: fix quality, wording or epochs, not volume"
    return ""


def build(*, authored: Sequence[dict], gold_pairs: Sequence[dict], class_sessions: Sequence[dict],
          scores: Dict[str, dict], floor: float = 0.40, target_examples: int = 30) -> tuple[List[dict], dict]:
    consented, class_dropped = consented_class_sessions(class_sessions)
    gold = gold_pair_sessions(gold_pairs)
    merged = list(authored) + gold + consented
    clean, gate = run_gate(merged, scrub=True)
    manifest = {
        "inputs": {"authored": len(authored), "gold_pairs": len(gold), "class_sessions_offered": len(class_sessions),
                   "class_sessions_with_consent": len(consented)},
        "class_sessions_dropped": class_dropped,
        "gate": {k: v for k, v in gate.items() if k != "hard"},
        "hard_failures": gate.get("hard", []),
        "kept": len(clean),
        "by_subject": _count(clean, subject_of),
        "by_language": _count(clean, lambda s: (s.get("audience") or {}).get("language") or "en"),
        "by_source": _count(clean, lambda s: str(s.get("source") or "").split(":")[0]),
        "by_consent": _count(clean, lambda s: s.get("consent")),
        "floor": floor,
        "needs_data": needs_data(clean, scores, floor, target_examples=target_examples),
        "scores_from_briefing": not scores,
    }
    if not scores:
        manifest["needs_data"] = [
            {"subject": name, "score": score, "eval_n": None, "exam": "briefing 2026-10-24",
             "train_examples": sum(n for s, n in manifest["by_subject"].items() if _matches(name, s)),
             "suggested_new_examples": max(0, target_examples - sum(
                 n for s, n in manifest["by_subject"].items() if _matches(name, s))),
             "note": "score from the briefing, not a live measurement"
             + ("; has data but is still under the floor: fix quality, wording or epochs, not volume"
                if sum(n for s, n in manifest["by_subject"].items() if _matches(name, s)) >= target_examples
                else "")}
            for name, score in BRIEFING_WEAK.items() if score < floor
        ]
    return clean, manifest


def render(manifest: dict) -> str:
    lines = [f"kept {manifest['kept']} sessions from {sum(manifest['inputs'].values())} offered inputs",
             f"by source: {manifest['by_source']}", f"by language: {manifest['by_language']}",
             f"subjects with training data: {len(manifest['by_subject'])}", "",
             f"Subjects under the {manifest['floor']:.0%} floor (aim new data here):"]
    for row in manifest["needs_data"]:
        lines.append(f"  {row['subject']:<34} score {row['score']:.1%}  train {row['train_examples']:>3}  "
                     f"add ~{row['suggested_new_examples']:>3}  {row['note']}")
    if not manifest["needs_data"]:
        lines.append("  none")
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sessions", nargs="*", default=list(DEFAULT_SESSIONS))
    ap.add_argument("--gold-pairs", nargs="*", default=[], help="review-lab gold pair export (JSON or JSONL)")
    ap.add_argument("--class-sessions", nargs="*", default=[], help="class sessions; kept only with consent")
    ap.add_argument("--eval-metrics", nargs="*", default=list(DEFAULT_METRICS))
    ap.add_argument("--floor", type=float, default=0.40)
    ap.add_argument("--target-examples", type=int, default=30, help="examples per weak subject to aim for")
    ap.add_argument("--out", default="output/spark/data/sessions.grown.json")
    ap.add_argument("--report", default="")
    ap.add_argument("--report-only", action="store_true", help="print the report; write no sessions")
    args = ap.parse_args(argv)

    def resolve(p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else ROOT / path

    # Fleet jobs pass a single comma-separated --sessions token; expand it.
    session_paths: list[str] = []
    for entry in args.sessions:
        session_paths.extend(part.strip() for part in str(entry).split(",") if part.strip())
    authored = load_sessions(resolve(p) for p in session_paths)
    gold = load_sessions(resolve(p) for p in args.gold_pairs)
    classes = load_sessions(resolve(p) for p in args.class_sessions)
    scores = load_subject_scores(resolve(p) for p in args.eval_metrics)
    clean, manifest = build(authored=authored, gold_pairs=gold, class_sessions=classes, scores=scores,
                            floor=args.floor, target_examples=args.target_examples)
    print(render(manifest))
    if manifest["hard_failures"]:
        for line in manifest["hard_failures"][:10]:
            print(f"HARD FAILURE: {line}", file=sys.stderr)
        return 3
    if args.report_only:
        return 0
    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = resolve(args.report) if args.report else out.with_name(out.stem + ".manifest.json")
    report.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out.parent / "needs_data.json").write_text(json.dumps(manifest["needs_data"], indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(clean)} sessions -> {out}\nmanifest -> {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
