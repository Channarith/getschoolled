#!/usr/bin/env python3
"""Build the multilingual benchmark slice (new file; eval_frozen.jsonl is never touched).

For each target language the learner is given an ENGLISH passage and asked, in grounded
mode, to explain it in their own language. The reference is the first two sentences of
that passage in the target language, so a good answer is faithful, in the right script and
overlaps the reference. Languages: Khmer, Spanish, Vietnamese, Thai, Swahili, Bengali, Chinese.

Reference sources, best first:
  --gold-jsonl   staff-reviewed pairs exported from the translation review lab
                 ({"lang","source":{"heading","text"},"target"} per line)  -> source=staff-reviewed
  data/course_translations/<course>/<lang>.json  (machine translation, never reviewed)
                                                                              -> source=mt-unreviewed
Unreviewed references are a rough yardstick: treat scores on them as relative, not absolute.

  python3 training/build_eval_multilingual.py --out training/data/eval_multilingual_v1.jsonl
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

from tutor_format import LANGUAGE_NAMES, mode_grounded  # noqa: E402

LANGUAGES = ("km", "es", "vi", "th", "sw", "bn", "zh")
LEVELS = ("beginner", "intermediate", "advanced")
_SPLIT = re.compile(r"(?<=[.!?។。！？।])\s*")


def lead(text: str, sentences: int = 2) -> str:
    parts = [p for p in _SPLIT.split(" ".join(text.split())) if p]
    return " ".join(parts[:sentences]) if " " in text.strip() or len(parts) > 1 else text.strip()


def _english_segments(course_id: str):
    from aoep_shared import audio_courses as audio

    try:
        course = audio.get_course(course_id)
    except Exception:  # noqa: BLE001 - a course that no longer exists is simply skipped
        return None
    if course is None:  # get_course returns None for an unknown id
        return None
    return [(s.heading, s.text) for s in course.segments]


def _item(index: int, lang: str, title: str, heading: str, english: str, target: str, source: str) -> dict:
    return {
        "id": f"ml-{lang}-{index:03d}",
        "source": source,
        "scorer": "language",
        "context": {"language": lang, "reading_level": LEVELS[index % 3]},
        "instruction": (
            f"{mode_grounded(lang)}\nPassage from the lesson '{title}':\n{english}\n\n"
            f"Explain '{heading}' in {LANGUAGE_NAMES.get(lang, lang)}, using only this passage."
        ),
        "response": lead(target),
        "tags": ["multilingual", lang],
    }


def from_gold(path: Path, per_lang: int, rng: random.Random) -> dict[str, list[dict]]:
    by_lang: dict[str, list[dict]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        lang = row.get("lang")
        if lang in LANGUAGES and row.get("target") and row.get("source", {}).get("text"):
            by_lang.setdefault(lang, []).append(row)
    out: dict[str, list[dict]] = {}
    for lang, rows in by_lang.items():
        rng.shuffle(rows)
        out[lang] = [
            _item(i, lang, "reviewed lesson", r["source"].get("heading", ""), r["source"]["text"], r["target"], "staff-reviewed")
            for i, r in enumerate(rows[:per_lang])
        ]
    return out


def from_translations(root: Path, per_lang: int, rng: random.Random) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {lang: [] for lang in LANGUAGES}
    courses = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    rng.shuffle(courses)
    for course_id in courses:
        english = None
        for lang in LANGUAGES:
            if len(out[lang]) >= per_lang:
                continue
            path = root / course_id / f"{lang}.json"
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            segments = data.get("segments") or []
            if english is None:
                english = _english_segments(course_id) or []
            if not english or len(english) != len(segments):
                continue  # not aligned: never guess which segment matches
            usable = [i for i, (_h, t) in enumerate(english) if len(t.split()) >= 25 and segments[i].get("text")]
            rng.shuffle(usable)
            for i in usable[:2]:
                if len(out[lang]) >= per_lang:
                    break
                out[lang].append(_item(len(out[lang]), lang, data.get("title") or course_id,
                                       english[i][0], english[i][1], segments[i]["text"], "mt-unreviewed"))
    return out


def build_items(translations: Path, gold: Path | None, per_lang: int = 20, seed: int = 20261024) -> list[dict]:
    rng = random.Random(seed)
    items: list[dict] = []
    reviewed = from_gold(gold, per_lang, rng) if gold and gold.is_file() else {}
    machine = from_translations(translations, per_lang, rng)
    for lang in LANGUAGES:
        chosen = list(reviewed.get(lang, []))
        for row in machine.get(lang, []):
            if len(chosen) >= per_lang:
                break
            chosen.append({**row, "id": f"ml-{lang}-{len(chosen):03d}"})
        items.extend(chosen)
    return items


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "training" / "data" / "eval_multilingual_v1.jsonl"))
    ap.add_argument("--translations", default=str(ROOT / "data" / "course_translations"))
    ap.add_argument("--gold-jsonl", default="")
    ap.add_argument("--per-lang", type=int, default=20)
    args = ap.parse_args(argv)
    out = Path(args.out)
    if out.name == "eval_frozen.jsonl":
        raise SystemExit("refusing to overwrite the frozen benchmark")
    items = build_items(Path(args.translations), Path(args.gold_jsonl) if args.gold_jsonl else None, args.per_lang)
    if not items:
        raise SystemExit("no multilingual items could be built (no aligned translations or gold pairs)")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for i in items:
        counts[i["tags"][1]] = counts.get(i["tags"][1], 0) + 1
    print(f"wrote {len(items)} items {counts} to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
