"""Progressive sentence read-aloud curriculum for dictionary pronunciation training.

Builds natural one-sentence drills, ramps difficulty/rarity, and scores
pronunciation + enunciation (extends language_learning.assess_pronunciation).
"""

from __future__ import annotations

import json
import random
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .dictionary_corpus import (
    DictionaryEntry,
    approved_entries,
    ensure_layout,
    load_staging,
    surface_forms,
)
from .language_learning import assess_pronunciation, mouth_shape_tip


@dataclass
class CurriculumSentence:
    id: str
    text: str
    language: str
    difficulty: int
    target_lemmas: List[str]
    target_forms: List[str]
    source: str = "template"
    rarity_avg: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CurriculumSentence":
        return cls(
            id=str(data.get("id") or ""),
            text=str(data.get("text") or ""),
            language=str(data.get("language") or "en"),
            difficulty=int(data.get("difficulty") or 1),
            target_lemmas=list(data.get("target_lemmas") or []),
            target_forms=list(data.get("target_forms") or []),
            source=str(data.get("source") or "template"),
            rarity_avg=float(data.get("rarity_avg") or 0.0),
        )


@dataclass
class LearnerProgress:
    learner_id: str = "local"
    language: str = "en"
    difficulty: int = 1
    mastery: Dict[str, float] = field(default_factory=dict)  # lemma -> 0..1
    weak: List[str] = field(default_factory=list)
    attempts: int = 0
    last_session_id: str = ""
    updated_ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LearnerProgress":
        return cls(
            learner_id=str(data.get("learner_id") or "local"),
            language=str(data.get("language") or "en"),
            difficulty=int(data.get("difficulty") or 1),
            mastery={str(k): float(v) for k, v in (data.get("mastery") or {}).items()},
            weak=list(data.get("weak") or []),
            attempts=int(data.get("attempts") or 0),
            last_session_id=str(data.get("last_session_id") or ""),
            updated_ts=float(data.get("updated_ts") or time.time()),
        )


_TEMPLATES_EASY = [
    "I see the {form}.",
    "This is a {form}.",
    "Please say {form} clearly.",
    "We need the {form}.",
]
_TEMPLATES_MID = [
    "She carefully {form} the lesson before class.",
    "They discussed every {form} in the meeting.",
    "Can you pronounce {form} with clear endings?",
    "The teacher wrote {form} on the board slowly.",
]
_TEMPLATES_HARD = [
    "Although the {form} seemed rare, she enunciated every syllable.",
    "He practiced the difficult {form} until the consonants were crisp.",
    "Without rushing, repeat {form} and keep the final sounds audible.",
]


def _ipa_complexity(ipa: str) -> float:
    if not ipa:
        return 0.2
    # Count consonant clusters / stress markers roughly.
    return min(1.0, len(re.findall(r"[A-Z]{2,}|\d", ipa)) * 0.15 + len(ipa) / 40.0)


def score_difficulty(entry: DictionaryEntry, sentence: str) -> int:
    words = len(sentence.split())
    rarity = float(entry.rarity)
    complex_ipa = _ipa_complexity(entry.ipa)
    idiom_boost = 1.0 if entry.kind in ("slang", "idiom", "figurative") else 0.0
    raw = rarity * 2.2 + (words / 12.0) + complex_ipa + idiom_boost
    if raw < 0.9:
        return 1
    if raw < 1.6:
        return 2
    if raw < 2.3:
        return 3
    if raw < 3.0:
        return 4
    return 5


def _pick_form(entry: DictionaryEntry, rng: random.Random) -> str:
    forms = surface_forms(entry)
    if not forms:
        return entry.lemma
    # Prefer non-lemma forms sometimes for naturalness.
    non_lemma = [f for f in forms if f != entry.lemma.lower()]
    if non_lemma and rng.random() < 0.45:
        return rng.choice(non_lemma)
    return entry.lemma


def sentence_from_tatoeba(entry: DictionaryEntry) -> Optional[CurriculumSentence]:
    for ex in entry.examples or []:
        text = str(ex.get("text") or "").strip()
        if not text or entry.language == "en" and ex.get("lang") not in (None, "", "en"):
            # examples from attach_tatoeba don't always set lang
            pass
        if not text:
            continue
        forms = [str(f) for f in (ex.get("target_forms") or [entry.lemma]) if f]
        # Prefer examples that actually contain a surface form.
        low = text.lower()
        hit = next((f for f in surface_forms(entry) if re.search(rf"\b{re.escape(f)}\b", low)), None)
        if not hit and forms:
            hit = forms[0] if forms[0] in low else None
        if not hit:
            continue
        diff = score_difficulty(entry, text)
        return CurriculumSentence(
            id=f"sent-{entry.id}-{hash(text) & 0xffff:04x}",
            text=text,
            language=entry.language,
            difficulty=diff,
            target_lemmas=[entry.lemma],
            target_forms=[hit],
            source="tatoeba",
            rarity_avg=entry.rarity,
        )
    return None


def sentence_from_template(entry: DictionaryEntry, rng: random.Random) -> CurriculumSentence:
    form = _pick_form(entry, rng)
    # Verbs often need past/gerund templates that still read ok with bare form.
    if entry.rarity < 0.25:
        tmpl = rng.choice(_TEMPLATES_EASY)
    elif entry.rarity < 0.55:
        tmpl = rng.choice(_TEMPLATES_MID)
    else:
        tmpl = rng.choice(_TEMPLATES_HARD)
    text = tmpl.format(form=form)
    return CurriculumSentence(
        id=f"sent-{entry.id}-{rng.randint(0, 0xffff):04x}",
        text=text,
        language=entry.language,
        difficulty=score_difficulty(entry, text),
        target_lemmas=[entry.lemma],
        target_forms=[form],
        source="template",
        rarity_avg=entry.rarity,
    )


def build_sentence_for_entry(entry: DictionaryEntry, *, seed: Optional[int] = None) -> CurriculumSentence:
    rng = random.Random(seed)
    natural = sentence_from_tatoeba(entry)
    if natural is not None:
        return natural
    return sentence_from_template(entry, rng)


def max_focus_words(difficulty: int) -> int:
    if difficulty <= 2:
        return 1
    if difficulty == 3:
        return 2
    return 3


def select_focus_entries(
    entries: Sequence[DictionaryEntry],
    *,
    difficulty: int,
    weak: Sequence[str],
    n: int = 1,
    seed: Optional[int] = None,
) -> List[DictionaryEntry]:
    rng = random.Random(seed)
    approved = approved_entries(entries)
    if not approved:
        return []
    # Band by rarity matching difficulty.
    bands = {
        1: (0.0, 0.25),
        2: (0.15, 0.4),
        3: (0.3, 0.6),
        4: (0.5, 0.8),
        5: (0.65, 1.01),
    }
    lo, hi = bands.get(max(1, min(5, difficulty)), (0.0, 1.01))
    weak_set = {w.lower() for w in weak}
    preferred = [e for e in approved if e.lemma.lower() in weak_set]
    banded = [e for e in approved if lo <= e.rarity < hi]
    pool = preferred or banded or approved
    rng.shuffle(pool)
    return pool[: max(1, min(n, max_focus_words(difficulty)))]


def build_curriculum(
    entries: Sequence[DictionaryEntry],
    *,
    language: str = "en",
    per_difficulty: int = 20,
    seed: Optional[int] = None,
) -> List[CurriculumSentence]:
    rng = random.Random(seed)
    approved = [e for e in approved_entries(entries) if e.language == language]
    out: List[CurriculumSentence] = []
    for diff in range(1, 6):
        picks = select_focus_entries(approved, difficulty=diff, weak=[], n=per_difficulty, seed=(seed or 0) + diff)
        # If band empty, fall back to sorted by rarity.
        if not picks:
            picks = sorted(approved, key=lambda e: e.rarity)[:per_difficulty]
        for e in picks:
            sent = build_sentence_for_entry(e, seed=rng.randint(0, 10_000_000))
            # Force difficulty band label for curriculum slices.
            sent.difficulty = max(sent.difficulty, diff) if e.rarity >= 0.5 else diff
            out.append(sent)
    # Deduplicate by text
    seen = set()
    unique: List[CurriculumSentence] = []
    for s in out:
        key = s.text.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique


def sentences_path(root: Optional[Path] = None, language: str = "en") -> Path:
    return ensure_layout(root) / "sentences" / f"{language}.jsonl"


def save_sentences(sentences: Sequence[CurriculumSentence], root: Optional[Path] = None, language: str = "en") -> Path:
    path = sentences_path(root, language)
    with path.open("w", encoding="utf-8") as fh:
        for s in sentences:
            fh.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")
    return path


def load_sentences(root: Optional[Path] = None, language: str = "en") -> List[CurriculumSentence]:
    path = sentences_path(root, language)
    if not path.is_file():
        return []
    out: List[CurriculumSentence] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("text"):
            out.append(CurriculumSentence.from_dict(row))
    return out


def progress_path(learner_id: str = "local", root: Optional[Path] = None) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", learner_id) or "local"
    return ensure_layout(root) / "progress" / f"{safe}.json"


def load_progress(learner_id: str = "local", root: Optional[Path] = None) -> LearnerProgress:
    path = progress_path(learner_id, root)
    if not path.is_file():
        return LearnerProgress(learner_id=learner_id)
    try:
        return LearnerProgress.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return LearnerProgress(learner_id=learner_id)


def save_progress(progress: LearnerProgress, root: Optional[Path] = None) -> Path:
    path = progress_path(progress.learner_id, root)
    progress.updated_ts = time.time()
    path.write_text(json.dumps(progress.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def next_read_aloud(
    *,
    language: str = "en",
    learner_id: str = "local",
    root: Optional[Path] = None,
    seed: Optional[int] = None,
) -> dict:
    """Pick the next sentence for a learner session."""
    progress = load_progress(learner_id, root)
    progress.language = language
    sentences = load_sentences(root, language)
    if not sentences:
        entries = load_staging(root, language)
        if not entries and language == "km":
            entries = load_staging(root, "en")
        sentences = build_curriculum(entries, language=language if entries else "en", seed=seed)
        if sentences:
            save_sentences(sentences, root, language)

    diff = max(1, min(5, progress.difficulty))
    band = [s for s in sentences if s.difficulty == diff]
    if not band:
        band = [s for s in sentences if abs(s.difficulty - diff) <= 1] or sentences
    if not band:
        return {
            "session_id": "",
            "sentence": "",
            "targets": [],
            "ipa_hints": [],
            "mouth_tips": [],
            "difficulty": diff,
            "error": "no_sentences",
        }

    # Prefer sentences whose lemmas are weak.
    weak = set(w.lower() for w in progress.weak)
    preferred = [s for s in band if any(t.lower() in weak for t in s.target_lemmas)]
    pool = preferred or band
    rng = random.Random(seed)
    sent = rng.choice(pool)
    session_id = uuid.uuid4().hex[:12]
    progress.last_session_id = session_id
    save_progress(progress, root)

    # IPA / mouth tips from staging when available.
    entries = {e.lemma.lower(): e for e in load_staging(root, language)}
    ipa_hints = []
    mouth_tips = []
    targets = []
    for lemma, form in zip(sent.target_lemmas, sent.target_forms or sent.target_lemmas):
        e = entries.get(lemma.lower())
        ipa = e.ipa if e else ""
        ipa_hints.append({"lemma": lemma, "form": form, "ipa": ipa})
        mouth_tips.append(mouth_shape_tip(form))
        targets.append({"lemma": lemma, "form": form, "gloss_en": e.gloss_en if e else ""})

    return {
        "session_id": session_id,
        "sentence": sent.text,
        "sentence_id": sent.id,
        "targets": targets,
        "ipa_hints": ipa_hints,
        "mouth_tips": mouth_tips,
        "difficulty": sent.difficulty,
        "source": sent.source,
        "learner_id": learner_id,
        "language": language,
    }


def _ending_issues(target: str, heard: str) -> List[str]:
    issues: List[str] = []
    tw = re.findall(r"[a-z']+", (target or "").lower())
    hw = re.findall(r"[a-z']+", (heard or "").lower())
    hw_set = set(hw)
    for w in tw:
        if w in hw_set:
            continue
        # truncated ending?
        stem_hit = any(h.startswith(w[: max(2, len(w) - 2)]) and len(h) < len(w) for h in hw)
        if stem_hit or w.endswith(("ed", "ing", "s", "es", "ly")):
            issues.append(w)
    return issues


def score_read_aloud(
    *,
    sentence: str,
    heard: str,
    target_forms: Sequence[str],
    mouth_openness: Optional[float] = None,
    learner_id: str = "local",
    language: str = "en",
    root: Optional[Path] = None,
) -> dict:
    """Score a read-aloud attempt; update learner progress."""
    base = assess_pronunciation(sentence, heard, mouth_openness=mouth_openness)
    forms = [f for f in target_forms if f]
    heard_l = (heard or "").lower()
    per_target = []
    missed = []
    for form in forms:
        ok = bool(re.search(rf"\b{re.escape(form.lower())}\b", heard_l))
        per_target.append({"form": form, "hit": ok})
        if not ok:
            missed.append(form)

    endings = _ending_issues(sentence, heard)
    enunciation_penalty = min(25, 8 * len(missed) + 5 * len(endings))
    score = max(0, int(base.get("score") or 0) - enunciation_penalty)
    stars = 3 if score >= 85 else 2 if score >= 60 else 1 if score >= 1 else 0

    feedback = str(base.get("feedback") or "")
    if missed:
        feedback = f"Enunciate clearly: {', '.join(missed)}. " + feedback
    elif endings:
        feedback = (
            "Over-articulate the highlighted endings: "
            + ", ".join(endings[:4])
            + ". "
            + feedback
        )
    elif 50 <= score < 85:
        feedback = "Good — slow down and over-articulate the focus words. " + feedback

    progress = load_progress(learner_id, root)
    progress.language = language
    progress.attempts += 1
    # Update mastery for target forms' lemmas (use form as key if unknown).
    for form, row in zip(forms, per_target):
        key = form.lower()
        prev = progress.mastery.get(key, 0.4)
        delta = 0.12 if row["hit"] and score >= 60 else -0.08
        progress.mastery[key] = max(0.0, min(1.0, prev + delta))
        if progress.mastery[key] < 0.55:
            if key not in progress.weak:
                progress.weak.append(key)
        elif key in progress.weak:
            progress.weak = [w for w in progress.weak if w != key]

    # Ramp difficulty when recent performance is strong.
    if score >= 85 and progress.attempts % 3 == 0:
        progress.difficulty = min(5, progress.difficulty + 1)
    elif score < 45:
        progress.difficulty = max(1, progress.difficulty - 1)

    save_progress(progress, root)

    return {
        **base,
        "score": score,
        "stars": stars,
        "per_target": per_target,
        "missed_forms": missed,
        "ending_issues": endings,
        "enunciation_penalty": enunciation_penalty,
        "feedback": feedback.strip(),
        "difficulty": progress.difficulty,
        "weak": list(progress.weak),
        "learner_id": learner_id,
        "sentence": sentence,
        "heard": heard,
    }
