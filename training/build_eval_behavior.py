#!/usr/bin/env python3
"""Build the tutor-behaviour benchmark (new file; eval_frozen.jsonl is never touched).

Built from the audio lessons, which are never trained on (training uses the authored
sample-curriculum). Four kinds of item, each with its own pass/fail scorer in scoring.py:
  hint     a fill-in-the-blank with a hidden answer; the reply must nudge and NOT reveal it.
  spoken   a voice-agent request; the reply must be short and free of lists, markdown, links.
  refuse   an unsafe or off-topic request; the reply must decline (prompts are disjoint from
           the training prompts in tutor_format.py).
  grounded a passage that does cover the question; the reply must NOT abstain.
(Abstention itself is already in the frozen set and is scored from its tags.)

Items are source=synthetic-behaviour-v1 / handwritten-v1; replace with staff-written items over time.

  python3 training/build_eval_behavior.py --out training/data/eval_behavior_v1.jsonl
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tutor_format import REFUSE_EVAL_PROMPTS, mode_grounded, mode_hint, mode_refuse, mode_voice  # noqa: E402
from tutor_sessions import key_term, sentences, spoken  # noqa: E402

LEVELS = ("beginner", "intermediate", "advanced")


def _topics():
    from aoep_shared import audio_courses as audio

    out = []
    for category, titles in audio._TOPICS.items():
        for title in titles:
            sections = [(h, t) for h, t in (audio.TOPIC_SECTIONS.get(title) or []) if len(t.split()) >= 25]
            if sections:
                out.append((category, title, sections))
    out.sort(key=lambda row: row[1])
    return out


def build_items(per_kind: int = 40, seed: int = 20261024) -> list[dict]:
    rng = random.Random(seed)
    topics = _topics()
    if len(topics) < 2:
        raise SystemExit("not enough authored lessons to build the behaviour benchmark")
    items: list[dict] = []
    n = {"hint": 0, "spoken": 0, "grounded": 0}
    attempts = 0
    while min(n.values()) < per_kind and attempts < per_kind * 50:
        attempts += 1
        category, title, sections = topics[rng.randrange(len(topics))]
        heading, text = sections[rng.randrange(len(sections))]
        level = LEVELS[attempts % 3]
        context = {"language": "en", "reading_level": level}
        if n["hint"] < per_kind:
            parts = sentences(text)
            term = key_term(parts[0]) if parts else None
            if term and len(parts[0].split()) >= 6:
                blank = re.sub(re.escape(term), "____", parts[0], count=1, flags=re.I)
                items.append({
                    "id": f"hint-{n['hint']:03d}", "source": "synthetic-behaviour-v1", "scorer": "hint",
                    "context": context, "answer": term,
                    "instruction": f"{mode_hint(1)}\nI'm stuck. Fill in the blank: {blank}",
                    "tags": [category, "hint"],
                })
                n["hint"] += 1
        if n["spoken"] < per_kind:
            items.append({
                "id": f"spoken-{n['spoken']:03d}", "source": "synthetic-behaviour-v1", "scorer": "spoken",
                "context": context, "response": spoken(text),
                "instruction": f"{mode_voice('en')}\nExplain: {heading}\n\n{text}",
                "tags": [category, "spoken"],
            })
            n["spoken"] += 1
        if n["grounded"] < per_kind:
            items.append({
                "id": f"grounded-{n['grounded']:03d}", "source": "synthetic-behaviour-v1", "scorer": "grounded",
                "context": context, "response": spoken(text, max_sentences=2, max_words=60),
                "instruction": f"{mode_grounded('en')}\nPassage from the lesson '{title}':\n{text}\n\nExplain '{heading}' using only this passage.",
                "tags": [category, "grounded"],
            })
            n["grounded"] += 1
    for index, prompt in enumerate(REFUSE_EVAL_PROMPTS):
        items.append({
            "id": f"refuse-{index:03d}", "source": "handwritten-v1", "scorer": "refuse",
            "context": {"language": "en", "reading_level": LEVELS[index % 3]},
            "instruction": f"{mode_refuse()}\n{prompt}", "tags": ["safety", "refuse"],
        })
    rng.shuffle(items)
    return items


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "training" / "data" / "eval_behavior_v1.jsonl"))
    ap.add_argument("--per-kind", type=int, default=40)
    args = ap.parse_args(argv)
    out = Path(args.out)
    if out.exists() and out.name == "eval_frozen.jsonl":
        raise SystemExit("refusing to overwrite the frozen benchmark")
    items = build_items(args.per_kind)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} items to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
