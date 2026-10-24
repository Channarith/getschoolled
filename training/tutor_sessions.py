#!/usr/bin/env python3
"""Turn authored lessons into tutor-behaviour training sessions (hint ladder, abstain,
voice-short, refuse, and learner-language replies).

Authored lessons come from the same sample-curriculum the STEM seed uses; the audio
lessons stay reserved for the frozen benchmark. Everything here is deterministic and
every session carries source + consent so the quality gate can admit it.

  python3 training/tutor_sessions.py --curriculum sample-curriculum --out output/spark/data/tutor.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spark_seed_sessions import READING_LEVELS, _audience, is_stem_course, parse_lesson  # noqa: E402
from tutor_format import (  # noqa: E402
    ABSTAIN_REPLY,
    HINT_STEPS,
    REFUSE_REPLY,
    REFUSE_TRAIN_PROMPTS,
    mode_grounded,
    mode_hint,
    mode_refuse,
    mode_voice,
)

SOURCE = "authored:tutor-templates"
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_STOP = {"which", "their", "there", "about", "these", "those", "where", "while", "would", "could", "should"}


def sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE.split(" ".join(text.split())) if s]


def spoken(text: str, max_sentences: int = 2, max_words: int = 35) -> str:
    out: list[str] = []
    words = 0
    for sentence in sentences(re.sub(r"[*_`#>\[\]]", "", text))[:max_sentences]:
        n = len(sentence.split())
        if words + n > max_words and out:
            break
        out.append(sentence)
        words += n
    return " ".join(out)


def key_term(sentence: str) -> str | None:
    """The longest plain word in the sentence: the thing the learner is asked to find."""
    words = [w.strip(".,;:!?()\"'") for w in sentence.split()]
    words = [w for w in words if w.isalpha() and len(w) >= 6 and w.lower() not in _STOP]
    return max(words, key=len) if words else None


def hint_ladder(title: str, text: str, audience: dict, tags: list[str]) -> list[dict]:
    """Three consecutive sessions: nudge, narrow, then reveal with the reason."""
    parts = sentences(text)
    if not parts:
        return []
    sentence = parts[0]
    term = key_term(sentence)
    if not term or len(sentence.split()) < 6:
        return []
    blank = re.sub(re.escape(term), "____", sentence, count=1, flags=re.I)
    quiz = f"Fill in the blank: {blank}"
    # The lesson title often contains the hidden word ("Divisibility Rules"): never name it in a hint.
    topic = f"'{title}'" if term.lower() not in title.lower() else "this topic"
    base = {"audience": audience, "source": SOURCE, "consent": "authored", "rewards": [1.0]}
    first, last = term[0].upper(), len(term)
    # An early hint must never contain the hidden word, even by coincidence ("together", "think", "word" can be the term).
    candidates = [
        f"Let's think about {topic} together. What word would fit the blank? Read the sentence again and tell me what you think.",
        f"Take a look at {topic}. Which word belongs in the blank? Read the sentence once more and give it a try.",
        "Read the sentence once more. Which word belongs in the blank? Give it a try.",
    ]
    first_hint = next((c for c in candidates if not re.search(rf"\b{re.escape(term)}\b", c, flags=re.I)), candidates[-1])
    return [
        {**base, "tags": tags + ["hint-ladder", "hint-1"], "turns": [
            {"role": "student", "text": f"{mode_hint(1)}\nI'm stuck on this. {quiz}"},
            {"role": "teacher", "text": first_hint}]},
        {**base, "tags": tags + ["hint-ladder", "hint-2"], "turns": [
            {"role": "student", "text": f"{mode_hint(2)}\nI still don't get it. {quiz}"},
            {"role": "teacher", "text": f"Here is a bigger hint: the missing word has {last} letters and starts with '{first}'. Does that help you guess it?"}]},
        {**base, "tags": tags + ["hint-ladder", f"hint-{HINT_STEPS}"], "turns": [
            {"role": "student", "text": f"{mode_hint(HINT_STEPS)}\nPlease just tell me. {quiz}"},
            {"role": "teacher", "text": f"The missing word is '{term}'. The full sentence is: {sentence} Want to try another one?"}]},
    ]


def abstain_session(title: str, text: str, other_title: str, audience: dict, tags: list[str], language: str) -> dict | None:
    reply = ABSTAIN_REPLY.get(language)
    if not reply:
        return None
    return {
        "audience": {**audience, "language": language}, "source": SOURCE, "consent": "authored", "rewards": [1.0],
        "tags": tags + ["abstain"],
        "turns": [
            {"role": "student", "text": f"{mode_grounded(language)}\nPassage from '{title}':\n{text}\n\nUsing only this passage, what can you tell me about {other_title}?"},
            {"role": "teacher", "text": reply},
        ],
    }


def grounded_session(title: str, heading: str, text: str, audience: dict, tags: list[str]) -> dict | None:
    answer = spoken(text, max_sentences=2, max_words=60)
    if not answer:
        return None
    return {
        "audience": audience, "source": SOURCE, "consent": "authored", "rewards": [1.0], "tags": tags + ["grounded"],
        "turns": [
            {"role": "student", "text": f"{mode_grounded(audience.get('language', 'en'))}\nPassage from '{title}':\n{text}\n\nExplain '{heading}' using only this passage."},
            {"role": "teacher", "text": answer},
        ],
    }


def voice_session(heading: str, text: str, audience: dict, tags: list[str]) -> dict | None:
    answer = spoken(text)
    if not answer or len(answer.split()) < 6:
        return None
    return {
        "audience": audience, "source": SOURCE, "consent": "authored", "rewards": [1.0], "tags": tags + ["voice"],
        "turns": [
            {"role": "student", "text": f"{mode_voice(audience.get('language', 'en'))}\nExplain: {heading}\n\n{text}"},
            {"role": "teacher", "text": answer},
        ],
    }


def refuse_sessions(seed: int = 17) -> list[dict]:
    rng = random.Random(seed)
    out: list[dict] = []
    for i, prompt in enumerate(REFUSE_TRAIN_PROMPTS):
        for language, reply in REFUSE_REPLY.items():
            if language != "en" and rng.random() > 0.35:
                continue
            ask = prompt if language == "en" else f"({language}) {prompt}"
            out.append({
                "audience": _audience(i, language), "source": SOURCE, "consent": "authored", "rewards": [1.0],
                "tags": ["refuse"],
                "turns": [{"role": "student", "text": f"{mode_refuse()}\n{ask}"}, {"role": "teacher", "text": reply}],
            })
    return out


def build_tutor_sessions(curriculum: Path, *, seed: int = 17, per_course: int = 6) -> list[dict]:
    rng = random.Random(seed)
    sessions: list[dict] = []
    titles: list[tuple[str, str]] = []
    lessons: list[tuple[str, str, list[tuple[str, str]]]] = []
    if curriculum.is_dir():
        for lesson_path in sorted(curriculum.glob("**/lesson.txt")):
            course = lesson_path.parent.name
            if not is_stem_course(course):
                continue
            lesson, language, slides = parse_lesson(lesson_path.read_text(encoding="utf-8", errors="replace"))
            if slides:
                lessons.append((course, lesson or course, slides))
                titles.append((course, lesson or course))
    for index, (course, lesson, slides) in enumerate(lessons):
        chosen = slides if len(slides) <= per_course else rng.sample(slides, per_course)
        for j, (heading, text) in enumerate(chosen):
            audience = _audience(index + j, "en")
            tags = [course, "stem"]
            sessions.extend(hint_ladder(heading, text, audience, tags))
            for made in (grounded_session(lesson, heading, text, audience, tags), voice_session(heading, text, audience, tags)):
                if made:
                    sessions.append(made)
            other = rng.choice([t for t in titles if t[0] != course] or titles)
            for language in ("en", "es", "vi", "zh"):
                if language != "en" and rng.random() > 0.3:
                    continue
                made = abstain_session(lesson, text, other[1], audience, tags, language)
                if made:
                    sessions.append(made)
    sessions.extend(refuse_sessions(seed))
    return sessions


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--curriculum", default="sample-curriculum")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--per-course", type=int, default=6)
    args = ap.parse_args(argv)
    sessions = build_tutor_sessions(Path(args.curriculum), seed=args.seed, per_course=args.per_course)
    if not sessions:
        raise SystemExit("no tutor sessions produced")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sessions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    kinds: dict[str, int] = {}
    for s in sessions:
        for t in s["tags"]:
            if t in ("hint-ladder", "abstain", "grounded", "voice", "refuse"):
                kinds[t] = kinds.get(t, 0) + 1
    print(f"wrote {len(sessions)} tutor sessions {kinds} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
