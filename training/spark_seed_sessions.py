#!/usr/bin/env python3
"""Build class-session JSON from the local STEM seed curriculum.

There is no live session store on this host. This reads the packaged
sample-curriculum STEM lessons (and the checked-in sample_sessions.json) and
writes the sessions list that training/export.py already consumes.

Pedagogical audience fields only. Race and ethnicity are never written.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

SLIDE_RE = re.compile(r"^SLIDE\s+\d+\s*\|\s*(.+)$")

# Course directory names (or prefixes) that map to the Track B "stem" adapter:
# math, science, and introductory computing (technology -> stem in routes.py).
STEM_NAMES = {
    "arithmetic",
    "calculus-1",
    "calculus-2",
    "differential-equations",
    "geometry",
    "intro-physics",
    "intro-python",
    "intro-science",
    "intro-to-fractions",
    "intro-to-photosynthesis",
    "linear-algebra",
    "math-olympiad",
    "problem-solving-math",
    "statistics",
    "trigonometry",
}

READING_LEVELS = ("beginner", "intermediate", "advanced")
STYLES = ("visual", "auditory", "reading", "mixed")
MASTERY = {"beginner": 0.25, "intermediate": 0.55, "advanced": 0.8}


def is_stem_course(name: str) -> bool:
    if name in STEM_NAMES:
        return True
    if name.startswith("python-"):
        return True
    if name.startswith("host-") and "math" in name:
        return True
    return False


def parse_lesson(text: str) -> tuple[str, str, list[tuple[str, str]]]:
    """Return (lesson title, language, [(slide title, answer), ...])."""
    language = "en"
    lesson = ""
    slides: list[tuple[str, str]] = []
    title: str | None = None
    body: list[str] = []
    narration = ""

    def flush() -> None:
        nonlocal title, body, narration
        if title:
            answer = narration.strip() or " ".join(part.strip() for part in body if part.strip())
            answer = re.sub(r"\s+", " ", answer).strip()
            if answer:
                slides.append((title.strip(), answer))
        title, body, narration = None, [], ""

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("LESSON:"):
            lesson = line.split(":", 1)[1].strip()
            continue
        if line.startswith("LANGUAGE:"):
            language = line.split(":", 1)[1].strip() or "en"
            continue
        matched = SLIDE_RE.match(line)
        if matched:
            flush()
            title = matched.group(1)
            continue
        if line.startswith("FACT:"):
            continue
        if line.startswith("NARRATION:"):
            narration = line.split(":", 1)[1].strip()
            continue
        if title is not None:
            body.append(line)
    flush()
    return lesson, language, slides


def _audience(index: int, language: str) -> dict:
    level = READING_LEVELS[index % len(READING_LEVELS)]
    age = "teen" if level == "beginner" else "adult"
    professionalism = {"beginner": "casual", "intermediate": "neutral", "advanced": "formal"}[level]
    return {
        "age_band": age,
        "language": language or "en",
        "reading_level": level,
        "learning_style": STYLES[index % len(STYLES)],
        "professionalism": professionalism,
        "prior_mastery": MASTERY[level],
    }


def sessions_from_curriculum(curriculum: Path) -> list[dict]:
    sessions: list[dict] = []
    if not curriculum.is_dir():
        return sessions
    for lesson_path in sorted(curriculum.glob("**/lesson.txt")):
        course = lesson_path.parent.name
        if not is_stem_course(course):
            continue
        _lesson, language, slides = parse_lesson(lesson_path.read_text(encoding="utf-8", errors="replace"))
        for title, answer in slides:
            sessions.append(
                {
                    "audience": _audience(len(sessions), language),
                    "turns": [
                        {"role": "student", "text": f"Explain: {title}"},
                        {"role": "teacher", "text": answer},
                    ],
                    "rewards": [1.0],
                    "tags": [course, "stem"],
                    "source": "authored:sample-curriculum",
                    "consent": "authored",
                }
            )
    return sessions


def load_sample_sessions(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"sample sessions must be a list: {path}")
    # The checked-in samples are authored examples; stamp provenance so the quality gate admits them.
    return [{"source": "authored:sample_sessions.json", "consent": "authored", **row} for row in data]


def build_sessions(curriculum: Path, sample: Path, *, seed: int = 17) -> list[dict]:
    sessions = sessions_from_curriculum(curriculum) + load_sample_sessions(sample)
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for session in sessions:
        turns = session.get("turns") or []
        if len(turns) < 2:
            continue
        key = (turns[0].get("text", ""), turns[1].get("text", ""))
        if key in seen or not key[0] or not key[1]:
            continue
        seen.add(key)
        unique.append(session)
    random.Random(seed).shuffle(unique)
    return unique


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curriculum", default="sample-curriculum")
    parser.add_argument("--sample", default="training/data/sample_sessions.json")
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args(argv)

    sessions = build_sessions(Path(args.curriculum), Path(args.sample), seed=args.seed)
    if not sessions:
        raise SystemExit("no STEM seed sessions produced")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sessions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(sessions)} seed sessions -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
