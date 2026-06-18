#!/usr/bin/env python3
"""Export class sessions + feedback into JSONL training examples (offline).

Reads a sessions JSON file and writes JSONL via the (tested, dependency-free)
pipeline.dataset. No ML libraries needed - this is the data step and runs
anywhere, fully offline.

Sessions JSON shape (a list of objects):
  [
    {
      "audience": {"age_band": "teen", "language": "en", "reading_level": "beginner", ...},
      "turns": [{"role": "student", "text": "..."}, {"role": "teacher", "text": "..."}],
      "rewards": [1.0],            # optional, one per student->teacher pair
      "tags": ["intro-to-fractions"]   # optional
    },
    ...
  ]

Protected attributes (race, ethnicity) in "audience" are accepted but NEVER
written into a training example's context (enforced by pipeline.dataset).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from pipeline.dataset import AudienceContext, TrainingExample, class_session_to_examples


def _examples_from_sessions(sessions: list) -> List[TrainingExample]:
    examples: List[TrainingExample] = []
    for s in sessions:
        audience = AudienceContext(**(s.get("audience") or {}))
        examples.extend(
            class_session_to_examples(
                s.get("turns", []),
                audience,
                rewards=s.get("rewards"),
                tags=s.get("tags", ()),
            )
        )
    return examples


def _write_jsonl(examples: List[TrainingExample], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex.to_dict(), ensure_ascii=False) + "\n")
    return len(examples)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", required=True, help="sessions JSON file")
    ap.add_argument("--out", default="training/data/train.jsonl", help="train JSONL out")
    ap.add_argument("--eval-out", default=None, help="optional eval JSONL out")
    ap.add_argument("--eval-split", type=float, default=0.0, help="fraction held out for eval")
    ap.add_argument(
        "--corrections", default=None,
        help="optional JSONL of gold correction examples to merge into train",
    )
    args = ap.parse_args(argv)

    sessions = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    examples = _examples_from_sessions(sessions)
    if not examples:
        print("no training examples produced", file=sys.stderr)
        return 1

    split = max(0.0, min(0.9, args.eval_split))
    n_eval = int(len(examples) * split)
    train = examples[n_eval:]

    # Merge gold correction examples (already in training-example dict form) so
    # the trainer back-propagates admin/user corrections (see corrections API).
    correction_rows = []
    if args.corrections and Path(args.corrections).is_file():
        for line in Path(args.corrections).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                correction_rows.append(json.loads(line))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for ex in train:
            fh.write(json.dumps(ex.to_dict(), ensure_ascii=False) + "\n")
        for row in correction_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    written = len(train) + len(correction_rows)
    print(f"wrote {written} train examples ({len(correction_rows)} from corrections) -> {args.out}")
    if args.eval_out and n_eval:
        ev = _write_jsonl(examples[:n_eval], Path(args.eval_out))
        print(f"wrote {ev} eval examples -> {args.eval_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
