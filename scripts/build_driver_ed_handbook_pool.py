#!/usr/bin/env python3
"""Validate and merge handbook-grounded driver's ed items into the class scene pool.

Authoring rows live in a directory of ``*.jsonl`` files (one fact-grounded item per
line). Every row must quote the California Driver Handbook text verbatim in
``evidence``; the check fails if the quote is not found in the handbook text dump
or if a number in the correct answer is absent from the quote.

  python3 scripts/build_driver_ed_handbook_pool.py check  --src GEN_DIR --handbook HB_DIR
  python3 scripts/build_driver_ed_handbook_pool.py build  --src GEN_DIR --handbook HB_DIR

HB_DIR holds the handbook sections as ``<slug>.txt`` (see the section field).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POOL_DIR = ROOT / "packages" / "shared" / "src" / "aoep_shared" / "data" / "content_packs" / "class_scenes"
OUT = POOL_DIR / "drivers_ed_handbook.jsonl"
KINDS = {"mc", "scenario", "sign"}
REQUIRED = ("fact_id", "section", "evidence", "kind", "skill", "prompt", "acceptable", "distractors", "spoken")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORDNUM = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "twelve": "12", "fifteen": "15", "eighteen": "18",
    "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50",
}


def _squash(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _numbers(text: str) -> set[str]:
    nums = {m.group(0).replace(",", "") for m in _NUM.finditer(text)}
    for word, digit in _WORDNUM.items():
        if re.search(rf"\b{word}\b", text.lower()):
            nums.add(digit)
    return nums


def _load_handbook(hb_dir: Path) -> dict[str, str]:
    return {p.stem: _squash(p.read_text(encoding="utf-8", errors="ignore")) for p in hb_dir.glob("*.txt")}


def _existing_prompts() -> set[str]:
    seen: set[str] = set()
    for path in POOL_DIR.glob("*.jsonl"):
        if path == OUT:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen.add(_squash(json.loads(line).get("prompt", "")))
    return seen


def _rows(src: Path) -> list[tuple[str, int, dict]]:
    out = []
    for path in sorted(src.glob("*.jsonl")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    out.append((path.name, i, json.loads(line)))
                except json.JSONDecodeError as exc:
                    out.append((path.name, i, {"_bad": str(exc)}))
    return out


def validate(src: Path, hb_dir: Path) -> tuple[list[dict], list[str]]:
    handbook = _load_handbook(hb_dir)
    existing = _existing_prompts()
    errors: list[str] = []
    good: list[dict] = []
    seen_prompts: set[str] = set()
    for fname, lineno, row in _rows(src):
        where = f"{fname}:{lineno}"
        if "_bad" in row:
            errors.append(f"{where} bad json {row['_bad']}")
            continue
        missing = [k for k in REQUIRED if not row.get(k)]
        if missing:
            errors.append(f"{where} missing {missing}")
            continue
        if row["kind"] not in KINDS:
            errors.append(f"{where} bad kind {row['kind']}")
            continue
        acc = row["acceptable"]
        dis = row["distractors"]
        if not isinstance(acc, list) or not isinstance(dis, list) or len(acc) < 1 or len(dis) != 3:
            errors.append(f"{where} need acceptable list and exactly 3 distractors")
            continue
        correct = str(acc[0]).strip()
        if len({_squash(correct), *(_squash(str(d)) for d in dis)}) != 4:
            errors.append(f"{where} options are not 4 distinct strings")
            continue
        section = row["section"]
        text = handbook.get(section)
        if text is None:
            errors.append(f"{where} unknown section {section}")
            continue
        ev = _squash(row["evidence"])
        if len(ev) < 20 or ev not in text:
            errors.append(f"{where} evidence not found verbatim in {section}: {row['evidence'][:80]!r}")
            continue
        nums = _numbers(correct)
        if nums and not nums <= _numbers(ev):
            errors.append(f"{where} numbers {sorted(nums - _numbers(ev))} in answer are not in evidence")
            continue
        key = _squash(row["prompt"])
        if key in seen_prompts or key in existing:
            errors.append(f"{where} duplicate prompt")
            continue
        seen_prompts.add(key)
        good.append(row)
    return good, errors


def to_scene(row: dict, n: int) -> dict:
    return {
        "topic": "drivers-ed",
        "skill": row["skill"],
        "prompt": row["prompt"].strip(),
        "acceptable": [str(a).strip() for a in row["acceptable"]],
        "rubric": row.get("rubric") or [str(row["acceptable"][0]).strip()],
        "spoken": row["spoken"].strip(),
        "distractors": [str(d).strip() for d in row["distractors"]],
        "locale": "en",
        "source_locale": "en",
        "scene_id": f"drivers-ed-hb-{n:05d}",
        "kind": row["kind"],
        "fact_id": row["fact_id"],
        "section": row["section"],
        "evidence": row["evidence"].strip(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["check", "build"])
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--handbook", type=Path, required=True)
    args = ap.parse_args()
    good, errors = validate(args.src, args.handbook)
    total = len(good) + len(errors)
    print(f"{len(good)} valid / {total} rows; {len(errors)} rejected")
    for err in errors[:60]:
        print("  REJECT", err)
    print("skills:", dict(Counter(r["skill"] for r in good).most_common(40)))
    print("kinds:", dict(Counter(r["kind"] for r in good)))
    if args.mode == "build":
        good.sort(key=lambda r: (r["section"], r["fact_id"], r["prompt"]))
        with OUT.open("w", encoding="utf-8") as fh:
            for n, row in enumerate(good, 1):
                fh.write(json.dumps(to_scene(row, n), ensure_ascii=False) + "\n")
        print(f"wrote {len(good)} scenes to {OUT.relative_to(ROOT)}")
    return 1 if errors and args.mode == "check" else 0


if __name__ == "__main__":
    sys.exit(main())
