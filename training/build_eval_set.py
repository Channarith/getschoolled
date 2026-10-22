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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "training" / "data" / "eval_frozen.jsonl"))
    ap.add_argument("--per-kind", type=int, default=100)
    args = ap.parse_args(argv)
    items = build_items(args.per_kind)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} items to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
