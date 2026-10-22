#!/usr/bin/env python3
"""Build the frozen tutoring benchmark from the authored audio lessons.

The nightly run already splits 10% of its own sessions for evaluation, but that
set is drawn from the same pool it trains on. This benchmark is written once,
committed, and never trained on, so a model can only beat it by getting better.

Two kinds of item, scored with the same token-overlap F1 as the rest of the
pipeline:
  recall   - a passage and a request to explain it; the reference is the
             passage's own opening sentences (stay faithful to the source).
  abstain  - a passage from one lesson and a question about another topic; the
             reference is a refusal to answer from material that does not cover it.

Items are marked source=synthetic-v1 so the staff review lab can replace them
with human-written references over time.

  python3 training/build_eval_set.py --out training/data/eval_frozen.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

ABSTAIN_REFERENCE = (
    "The passage does not cover that, so I can't answer it from this material. "
    "I don't want to guess."
)
LEVELS = ("beginner", "intermediate", "advanced")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _lead(text: str, sentences: int = 2) -> str:
    parts = [p for p in _SENTENCE.split(" ".join(text.split())) if p]
    return " ".join(parts[:sentences])


def build_items(per_kind: int = 100, seed: int = 20261021) -> list[dict]:
    from aoep_shared import audio_courses as audio

    rng = random.Random(seed)
    topics = []
    for category, titles in audio._TOPICS.items():
        for title in titles:
            sections = audio.TOPIC_SECTIONS.get(title) or []
            usable = [(h, t) for h, t in sections if len(t.split()) >= 25]
            if usable:
                topics.append((category, title, usable))
    topics.sort(key=lambda row: row[1])
    if len(topics) < 2:
        raise SystemExit("not enough authored lessons to build a benchmark")

    by_category: dict[str, list] = {}
    for row in topics:
        by_category.setdefault(row[0], []).append(row)
    categories = sorted(by_category)

    def _pick(index: int):
        category = categories[index % len(categories)]
        return by_category[category][rng.randrange(len(by_category[category]))]

    recall: list[dict] = []
    abstain: list[dict] = []
    for index in range(per_kind):
        category, title, sections = _pick(index)
        heading, text = sections[rng.randrange(len(sections))]
        level = LEVELS[index % len(LEVELS)]
        recall.append({
            "id": f"recall-{index:03d}",
            "source": "synthetic-v1",
            "context": {"language": "en", "reading_level": level},
            "instruction": (
                f"Passage from the lesson '{title}':\n{text}\n\n"
                f"Explain '{heading}' using only this passage."
            ),
            "response": _lead(text),
            "passage": text,
            "tags": [category, "recall"],
        })
    for index in range(per_kind):
        category, title, sections = _pick(index + per_kind)
        _other_category, other_title, _other_sections = topics[rng.randrange(len(topics))]
        while other_title == title:
            _other_category, other_title, _other_sections = topics[rng.randrange(len(topics))]
        heading, text = sections[rng.randrange(len(sections))]
        level = LEVELS[index % len(LEVELS)]
        abstain.append({
            "id": f"abstain-{index:03d}",
            "source": "synthetic-v1",
            "context": {"language": "en", "reading_level": level},
            "instruction": (
                f"Passage from the lesson '{title}':\n{text}\n\n"
                f"Using only this passage, what can you tell me about {other_title}?"
            ),
            "response": ABSTAIN_REFERENCE,
            "passage": text,
            "tags": [category, "abstain"],
        })
    items = recall + abstain
    rng.shuffle(items)
    return items


def slide_passages(text: str, *, min_words: int = 12) -> list[tuple[str, str]]:
    """Slide title plus the longer of the slide body and the narration."""
    slides: list[tuple[str, str]] = []
    title: str | None = None
    body: list[str] = []
    narration = ""

    def flush() -> None:
        nonlocal title, body, narration
        if title:
            paragraph = re.sub(r"\s+", " ", " ".join(part.strip() for part in body if part.strip())).strip()
            spoken = re.sub(r"\s+", " ", narration).strip()
            passage = paragraph if len(paragraph.split()) >= len(spoken.split()) else spoken
            if len(passage.split()) >= min_words:
                slides.append((title.strip(), passage))
        title, body, narration = None, [], ""

    for raw in text.splitlines():
        line = raw.strip()
        matched = re.match(r"^SLIDE\s+\d+\s*\|\s*(.+)$", line)
        if matched:
            flush()
            title = matched.group(1)
            continue
        if line.startswith("NARRATION:"):
            narration = line.split(":", 1)[1].strip()
            continue
        if line.startswith(("FACT:", "LESSON:", "LANGUAGE:")):
            continue
        if title is not None and line:
            body.append(line)
    flush()
    return slides


def build_stem_items(
    curriculum: Path,
    *,
    per_course: int = 2,
    seed: int = 20261022,
) -> list[dict]:
    """Frozen recall and abstain items from the STEM lesson files.

    The general frozen exam is audio-lesson topics and does not contain
    linear algebra. This set is the subject floor for the STEM adapter.
    Host stub decks are left out. Selection is deterministic.
    """
    from spark_seed_sessions import is_stem_course

    courses: list[tuple[str, str, list[tuple[str, str]]]] = []
    for lesson_path in sorted(curriculum.glob("**/lesson.txt")):
        course = lesson_path.parent.name
        if course.startswith("host-") or not is_stem_course(course):
            continue
        passages = slide_passages(lesson_path.read_text(encoding="utf-8", errors="replace"))
        if not passages:
            continue
        lesson_title = course
        for raw in lesson_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if raw.startswith("LESSON:"):
                lesson_title = raw.split(":", 1)[1].strip() or course
                break
        courses.append((course, lesson_title, passages))
    if len(courses) < 2:
        raise SystemExit(f"not enough STEM lessons under {curriculum}")

    items: list[dict] = []
    for index, (course, lesson_title, passages) in enumerate(courses):
        other = courses[(index + 1) % len(courses)][1]
        for slot in range(min(per_course, len(passages))):
            heading, text = passages[slot]
            items.append({
                "id": f"stem-recall-{course}-{slot:02d}",
                "source": "synthetic-v1",
                "context": {"language": "en", "reading_level": LEVELS[slot % len(LEVELS)]},
                "instruction": (
                    f"Passage from the lesson '{lesson_title}':\n{text}\n\n"
                    f"Explain '{heading}' using only this passage."
                ),
                "response": _lead(text),
                "passage": text,
                "tags": [course, "recall"],
            })
            items.append({
                "id": f"stem-abstain-{course}-{slot:02d}",
                "source": "synthetic-v1",
                "context": {"language": "en", "reading_level": LEVELS[slot % len(LEVELS)]},
                "instruction": (
                    f"Passage from the lesson '{lesson_title}':\n{text}\n\n"
                    f"Using only this passage, what can you tell me about {other}?"
                ),
                "response": ABSTAIN_REFERENCE,
                "passage": text,
                "tags": [course, "abstain"],
            })
    random.Random(seed).shuffle(items)
    return items


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "training" / "data" / "eval_frozen.jsonl"))
    ap.add_argument("--per-kind", type=int, default=100)
    ap.add_argument("--stem", action="store_true", help="write the STEM-subject exam instead")
    ap.add_argument("--curriculum", default=str(ROOT / "sample-curriculum"))
    ap.add_argument("--per-course", type=int, default=2)
    args = ap.parse_args(argv)
    if args.stem:
        items = build_stem_items(Path(args.curriculum), per_course=args.per_course)
    else:
        items = build_items(args.per_kind)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} items to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
