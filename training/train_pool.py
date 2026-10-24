#!/usr/bin/env python3
"""Training rows in the frozen-exam format, from lessons the exam does not use.

The Spark loop was exporting the same STEM seed every cycle (373 rows of
"Explain: <title>" with the full narration as the answer). The frozen exam
asks a different question: stay inside a given passage, or abstain. Repeating
that seed cannot move the frozen score.

This builder writes the exam's own task from every other usable section. A
section is dropped when its text is a frozen passage or shares an 8-word
window with one. The fingerprint of the train file is how a later cycle
refuses to start QLoRA on the same rows again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
sys.path.insert(0, str(ROOT / "training"))

from build_eval_set import ABSTAIN_REFERENCE, LEVELS, _lead, slide_passages  # noqa: E402
from spark_seed_sessions import is_stem_course  # noqa: E402

_TOKEN = re.compile(r"[a-z0-9]+")
_NGRAM = 8


@dataclass(frozen=True)
class Section:
    category: str
    title: str
    heading: str
    text: str


def word_ngrams(text: str, n: int = _NGRAM) -> set[str]:
    tokens = _TOKEN.findall(text.lower())
    return {" ".join(tokens[i : i + n]) for i in range(max(0, len(tokens) - n + 1))}


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(text.lower()))


def load_exam_block(paths: list[Path]) -> tuple[set[str], set[str], set[tuple[str, ...]]]:
    """Exact passages, 8-word windows, and token sequences from the frozen exams."""
    exact: set[str] = set()
    windows: set[str] = set()
    sequences: set[tuple[str, ...]] = set()
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            passage = " ".join((row.get("passage") or "").split())
            instruction = row.get("instruction") or ""
            if passage:
                exact.add(passage)
                sequences.add(_tokens(passage))
            windows |= word_ngrams(passage)
            windows |= word_ngrams(instruction)
            if instruction:
                exact.add(" ".join(instruction.split()))
    return exact, windows, sequences


def _overlaps(text: str, exact: set[str], windows: set[str], sequences: set[tuple[str, ...]]) -> bool:
    normalized = " ".join(text.split())
    if normalized in exact:
        return True
    grams = word_ngrams(normalized)
    if grams & windows:
        return True
    tokens = _tokens(normalized)
    if len(tokens) < _NGRAM:
        for seq in sequences:
            if len(tokens) and len(tokens) <= len(seq):
                width = len(tokens)
                for start in range(len(seq) - width + 1):
                    if seq[start : start + width] == tokens:
                        return True
    return False


def audio_sections() -> list[Section]:
    from aoep_shared import audio_courses as audio

    rows: list[Section] = []
    for category, titles in audio._TOPICS.items():
        for title in titles:
            for heading, text in audio.TOPIC_SECTIONS.get(title) or []:
                if len(text.split()) < 25:
                    continue
                rows.append(Section(category, title, heading.strip(), " ".join(text.split())))
    rows.sort(key=lambda s: (s.category, s.title, s.heading, s.text))
    return rows


def stem_sections(curriculum: Path) -> list[Section]:
    rows: list[Section] = []
    if not curriculum.is_dir():
        return rows
    for lesson_path in sorted(curriculum.glob("**/lesson.txt")):
        course = lesson_path.parent.name
        if course.startswith("host-") or not is_stem_course(course):
            continue
        raw = lesson_path.read_text(encoding="utf-8", errors="replace")
        lesson_title = course
        for line in raw.splitlines():
            if line.startswith("LESSON:"):
                lesson_title = line.split(":", 1)[1].strip() or course
                break
        for heading, text in slide_passages(raw):
            rows.append(Section(course, lesson_title, heading.strip(), " ".join(text.split())))
    rows.sort(key=lambda s: (s.category, s.title, s.heading, s.text))
    return rows


def held_out_sections(
    curriculum: Path,
    exam_paths: list[Path],
    *,
    include_audio: bool = True,
) -> tuple[list[Section], int]:
    exact, windows, sequences = load_exam_block(exam_paths)
    source = stem_sections(curriculum)
    if include_audio:
        source = audio_sections() + source
    kept: list[Section] = []
    dropped = 0
    seen: set[tuple[str, str, str]] = set()
    for section in source:
        key = (section.title, section.heading, section.text)
        if key in seen or _overlaps(section.text, exact, windows, sequences):
            dropped += 1
            continue
        seen.add(key)
        kept.append(section)
    return kept, dropped


def _other_title(titles: list[str], title: str, index: int) -> str:
    if len(titles) < 2:
        return "a different subject"
    start = titles.index(title) if title in titles else 0
    return titles[(start + 1 + (index % (len(titles) - 1))) % len(titles)]


def build_rows(sections: list[Section], *, seed: int = 20261024) -> list[dict]:
    """One recall item and one abstain item per held-out section."""
    titles = sorted({section.title for section in sections})
    rows: list[dict] = []
    for index, section in enumerate(sections):
        level = LEVELS[index % len(LEVELS)]
        context = {"language": "en", "reading_level": level}
        other = _other_title(titles, section.title, index)
        rows.append({
            "source": "held-out-v1",
            "context": context,
            "instruction": (
                f"Passage from the lesson '{section.title}':\n{section.text}\n\n"
                f"Explain '{section.heading}' using only this passage."
            ),
            "response": _lead(section.text),
            "tags": [section.category, "recall"],
        })
        rows.append({
            "source": "held-out-v1",
            "context": {"language": "en", "reading_level": level},
            "instruction": (
                f"Passage from the lesson '{section.title}':\n{section.text}\n\n"
                f"Using only this passage, what can you tell me about {other}?"
            ),
            "response": ABSTAIN_REFERENCE,
            "tags": [section.category, "abstain"],
        })
    random.Random(seed).shuffle(rows)
    return rows


def split_rows(rows: list[dict], eval_fraction: float) -> tuple[list[dict], list[dict]]:
    fraction = max(0.0, min(0.9, eval_fraction))
    n_eval = int(len(rows) * fraction)
    return rows[n_eval:], rows[:n_eval]


def fingerprint(rows: list[dict]) -> str:
    payload = "\n".join(
        json.dumps(
            {"instruction": row["instruction"], "response": row["response"]},
            ensure_ascii=False,
            sort_keys=True,
        )
        for row in sorted(rows, key=lambda row: (row["instruction"], row["response"]))
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def should_train(current: str, previous: str | None, *, scored: bool) -> bool:
    """Train when the file is new, or when this file has never been scored."""
    if not current:
        return False
    if not previous or previous != current:
        return True
    return not scored


def _read_fingerprint(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curriculum", default=str(ROOT / "sample-curriculum"))
    parser.add_argument("--frozen", action="append", default=[], help="frozen exam JSONL to exclude")
    parser.add_argument("--train-out", default="")
    parser.add_argument("--eval-out", default="")
    parser.add_argument("--fingerprint-out", default="")
    parser.add_argument("--eval-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=20261024)
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--should-train", action="store_true",
                        help="exit 0 when a cycle should train, 1 when the fingerprint is unchanged")
    parser.add_argument("--current", default="", help="fingerprint file for --should-train")
    parser.add_argument("--previous", default="", help="last finished fingerprint file")
    parser.add_argument("--scored", default="", help="frozen metrics JSON; presence means the last cycle scored")
    args = parser.parse_args(argv)

    if args.should_train:
        current = _read_fingerprint(Path(args.current)) if args.current else None
        previous = _read_fingerprint(Path(args.previous)) if args.previous else None
        scored = bool(args.scored) and Path(args.scored).is_file()
        train = should_train(current or "", previous, scored=scored)
        print("train" if train else "skip")
        return 0 if train else 1

    exam_paths = [Path(p) for p in args.frozen] or [
        ROOT / "training" / "data" / "eval_frozen.jsonl",
        ROOT / "training" / "data" / "eval_frozen_stem.jsonl",
    ]
    sections, dropped = held_out_sections(
        Path(args.curriculum), exam_paths, include_audio=not args.no_audio,
    )
    if not sections:
        print("no held-out sections", file=sys.stderr)
        return 1
    rows = build_rows(sections, seed=args.seed)
    train_rows, eval_rows = split_rows(rows, args.eval_split)
    digest = fingerprint(train_rows)
    if args.train_out:
        _write_jsonl(Path(args.train_out), train_rows)
    if args.eval_out:
        _write_jsonl(Path(args.eval_out), eval_rows)
    if args.fingerprint_out:
        path = Path(args.fingerprint_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(digest + "\n", encoding="utf-8")
    print(
        f"wrote train={len(train_rows)} eval={len(eval_rows)} "
        f"sections={len(sections)} dropped={dropped} fingerprint={digest}"
    )
    return 0


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
