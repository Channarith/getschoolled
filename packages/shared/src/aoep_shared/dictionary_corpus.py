"""Self-hosted dictionary corpus: staging schema, merge, inflections, review routing.

Offline-first. Large baseline dumps live under ``AOEP_DICTIONARY_DIR`` (default
``~/.cache/aoep/dictionary``); only curated content packs are shipped in-repo.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

AUDIO_QUALITIES = ("missing", "raw", "crisp", "gold", "rejected")
REVIEW_STATUSES = ("auto", "queued", "approved", "rejected")
KINDS = ("literal", "slang", "idiom", "figurative", "mwe")


def dictionary_dir() -> Path:
    raw = os.environ.get("AOEP_DICTIONARY_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / ".cache" / "aoep" / "dictionary"


def ensure_layout(root: Optional[Path] = None) -> Path:
    """Create the on-disk layout and return the root."""
    base = root or dictionary_dir()
    for sub in (
        "baselines",
        "staging",
        "review",
        "sentences",
        "progress",
        "audio/en/raw",
        "audio/en/crisp",
        "audio/km/raw",
        "audio/km/crisp",
        "export",
    ):
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


@dataclass
class AudioSlot:
    raw: Optional[str] = None
    crisp: Optional[str] = None
    quality: str = "missing"
    snr_db: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "raw": self.raw,
            "crisp": self.crisp,
            "quality": self.quality if self.quality in AUDIO_QUALITIES else "missing",
            "snr_db": self.snr_db,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "AudioSlot":
        if not isinstance(data, dict):
            return cls()
        q = str(data.get("quality") or "missing")
        if q not in AUDIO_QUALITIES:
            q = "missing"
        snr = data.get("snr_db")
        return cls(
            raw=data.get("raw"),
            crisp=data.get("crisp"),
            quality=q,
            snr_db=float(snr) if snr is not None else None,
        )


@dataclass
class DictionaryEntry:
    id: str
    lemma: str
    language: str = "en"
    pos: str = ""
    gloss_en: str = ""
    translations: Dict[str, dict] = field(default_factory=dict)
    ipa: str = ""
    inflections: Dict[str, str] = field(default_factory=dict)
    rarity: float = 0.5
    freq_rank: int = 999999
    examples: List[dict] = field(default_factory=list)
    kind: str = "literal"
    sources: List[str] = field(default_factory=list)
    confidence: float = 0.5
    review_status: str = "queued"
    audio: Dict[str, AudioSlot] = field(default_factory=dict)
    sense_count: int = 1
    notes: str = ""

    def to_dict(self) -> dict:
        audio = {
            lang: (slot.to_dict() if isinstance(slot, AudioSlot) else AudioSlot.from_dict(slot).to_dict())
            for lang, slot in (self.audio or {}).items()
        }
        return {
            "id": self.id,
            "lemma": self.lemma,
            "language": self.language,
            "pos": self.pos,
            "gloss_en": self.gloss_en,
            "translations": dict(self.translations or {}),
            "ipa": self.ipa,
            "inflections": dict(self.inflections or {}),
            "rarity": float(self.rarity),
            "freq_rank": int(self.freq_rank),
            "examples": list(self.examples or []),
            "kind": self.kind if self.kind in KINDS else "literal",
            "sources": list(self.sources or []),
            "confidence": float(self.confidence),
            "review_status": (
                self.review_status if self.review_status in REVIEW_STATUSES else "queued"
            ),
            "audio": audio,
            "sense_count": int(self.sense_count),
            "notes": self.notes or "",
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DictionaryEntry":
        audio_raw = data.get("audio") or {}
        audio: Dict[str, AudioSlot] = {}
        if isinstance(audio_raw, dict):
            for lang, slot in audio_raw.items():
                audio[str(lang)] = AudioSlot.from_dict(slot if isinstance(slot, dict) else None)
        return cls(
            id=str(data.get("id") or ""),
            lemma=str(data.get("lemma") or "").strip(),
            language=str(data.get("language") or "en"),
            pos=str(data.get("pos") or ""),
            gloss_en=str(data.get("gloss_en") or ""),
            translations=dict(data.get("translations") or {}),
            ipa=str(data.get("ipa") or ""),
            inflections={
                str(k): str(v) for k, v in (data.get("inflections") or {}).items() if v
            },
            rarity=float(data.get("rarity") if data.get("rarity") is not None else 0.5),
            freq_rank=int(data.get("freq_rank") or 999999),
            examples=list(data.get("examples") or []),
            kind=str(data.get("kind") or "literal"),
            sources=list(data.get("sources") or []),
            confidence=float(data.get("confidence") if data.get("confidence") is not None else 0.5),
            review_status=str(data.get("review_status") or "queued"),
            audio=audio,
            sense_count=int(data.get("sense_count") or 1),
            notes=str(data.get("notes") or ""),
        )


def entry_id(language: str, lemma: str, pos: str = "") -> str:
    base = f"{language}:{(lemma or '').strip().lower()}:{pos or 'x'}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]
    safe = re.sub(r"[^a-z0-9]+", "-", (lemma or "").lower()).strip("-")[:32] or "word"
    return f"{language}-{safe}-{digest}"


def rarity_from_rank(rank: int, *, universe: int = 10000) -> float:
    """Map frequency rank (1=most common) to rarity in [0, 1]."""
    r = max(1, int(rank or universe))
    return round(min(1.0, max(0.0, (r - 1) / max(1, universe - 1))), 4)


# --------------------------------------------------------------------------- #
# Simple English inflection heuristics (offline; WordNet/Wiktionary enrich later)
# --------------------------------------------------------------------------- #
_IRREGULAR_PLURALS = {
    "child": "children",
    "man": "men",
    "woman": "women",
    "person": "people",
    "mouse": "mice",
    "goose": "geese",
    "tooth": "teeth",
    "foot": "feet",
    "ox": "oxen",
}
_IRREGULAR_VERBS = {
    "be": {"past": "was", "past_participle": "been", "gerund": "being", "third_sing": "is"},
    "go": {"past": "went", "past_participle": "gone", "gerund": "going", "third_sing": "goes"},
    "have": {"past": "had", "past_participle": "had", "gerund": "having", "third_sing": "has"},
    "do": {"past": "did", "past_participle": "done", "gerund": "doing", "third_sing": "does"},
    "say": {"past": "said", "past_participle": "said", "gerund": "saying", "third_sing": "says"},
    "make": {"past": "made", "past_participle": "made", "gerund": "making", "third_sing": "makes"},
    "take": {"past": "took", "past_participle": "taken", "gerund": "taking", "third_sing": "takes"},
    "come": {"past": "came", "past_participle": "come", "gerund": "coming", "third_sing": "comes"},
    "see": {"past": "saw", "past_participle": "seen", "gerund": "seeing", "third_sing": "sees"},
    "get": {"past": "got", "past_participle": "gotten", "gerund": "getting", "third_sing": "gets"},
    "know": {"past": "knew", "past_participle": "known", "gerund": "knowing", "third_sing": "knows"},
    "think": {"past": "thought", "past_participle": "thought", "gerund": "thinking", "third_sing": "thinks"},
    "teach": {"past": "taught", "past_participle": "taught", "gerund": "teaching", "third_sing": "teaches"},
    "learn": {"past": "learned", "past_participle": "learned", "gerund": "learning", "third_sing": "learns"},
    "read": {"past": "read", "past_participle": "read", "gerund": "reading", "third_sing": "reads"},
    "write": {"past": "wrote", "past_participle": "written", "gerund": "writing", "third_sing": "writes"},
    "speak": {"past": "spoke", "past_participle": "spoken", "gerund": "speaking", "third_sing": "speaks"},
    "run": {"past": "ran", "past_participle": "run", "gerund": "running", "third_sing": "runs"},
}


def _pluralize(lemma: str) -> str:
    w = lemma.lower()
    if w in _IRREGULAR_PLURALS:
        return _IRREGULAR_PLURALS[w]
    if w.endswith(("s", "x", "z", "ch", "sh")):
        return w + "es"
    if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        return w[:-1] + "ies"
    if w.endswith("f"):
        return w[:-1] + "ves"
    if w.endswith("fe"):
        return w[:-2] + "ves"
    return w + "s"


def _third_sing(lemma: str) -> str:
    w = lemma.lower()
    if w.endswith(("s", "x", "z", "ch", "sh")):
        return w + "es"
    if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        return w[:-1] + "ies"
    return w + "s"


def _gerund(lemma: str) -> str:
    w = lemma.lower()
    if len(w) >= 3 and w[-1] not in "aeiouwy" and w[-2] in "aeiou" and w[-3] not in "aeiou":
        return w + w[-1] + "ing"
    if w.endswith("ie"):
        return w[:-2] + "ying"
    if w.endswith("e") and not w.endswith("ee"):
        return w[:-1] + "ing"
    return w + "ing"


def _past(lemma: str) -> str:
    w = lemma.lower()
    if w.endswith("e"):
        return w + "d"
    if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        return w[:-1] + "ied"
    if len(w) >= 3 and w[-1] not in "aeiouwy" and w[-2] in "aeiou" and w[-3] not in "aeiou":
        return w + w[-1] + "ed"
    return w + "ed"


CLOSED_CLASS = frozenset({
    "the", "a", "an", "of", "to", "and", "or", "but", "in", "on", "at", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall", "should",
    "may", "might", "can", "could", "must", "i", "you", "he", "she", "it", "we",
    "they", "me", "him", "her", "us", "them", "my", "your", "his", "its", "our",
    "their", "this", "that", "these", "those", "not", "no", "yes", "so", "if",
    "then", "than", "too", "very", "just", "also", "into", "out", "up", "down",
})


def english_inflections(lemma: str, pos: str = "") -> Dict[str, str]:
    """Return a small paradigm for an English lemma."""
    w = (lemma or "").strip().lower()
    if not w or " " in w or w in CLOSED_CLASS:
        return {}
    pos_l = (pos or "").lower()
    out: Dict[str, str] = {}
    if pos_l in ("", "n", "noun"):
        out["plural"] = _pluralize(w)
        out["poss"] = w + "'s"
    if pos_l in ("", "v", "verb"):
        irr = _IRREGULAR_VERBS.get(w)
        if irr:
            out.update(irr)
        else:
            out["third_sing"] = _third_sing(w)
            out["past"] = _past(w)
            out["past_participle"] = out["past"]
            out["gerund"] = _gerund(w)
    if pos_l in ("", "a", "adj", "adjective"):
        if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
            out["comparative"] = w[:-1] + "ier"
            out["superlative"] = w[:-1] + "iest"
        elif w.endswith("e"):
            out["comparative"] = w + "r"
            out["superlative"] = w + "st"
        elif len(w) <= 6:
            out["comparative"] = w + "er"
            out["superlative"] = w + "est"
    return {k: v for k, v in out.items() if v}


def surface_forms(entry: DictionaryEntry) -> List[str]:
    forms = {entry.lemma.lower()}
    for v in (entry.inflections or {}).values():
        if v:
            forms.add(str(v).lower())
    return sorted(forms)


# --------------------------------------------------------------------------- #
# Staging I/O
# --------------------------------------------------------------------------- #
def staging_path(root: Optional[Path] = None, language: str = "en") -> Path:
    base = ensure_layout(root)
    return base / "staging" / f"{language}.jsonl"


def load_staging(root: Optional[Path] = None, language: str = "en") -> List[DictionaryEntry]:
    path = staging_path(root, language)
    if not path.is_file():
        return []
    out: List[DictionaryEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("lemma"):
            out.append(DictionaryEntry.from_dict(row))
    return out


def save_staging(
    entries: Sequence[DictionaryEntry],
    root: Optional[Path] = None,
    language: str = "en",
) -> Path:
    path = staging_path(root, language)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
    return path


def review_queue_path(root: Optional[Path] = None) -> Path:
    return ensure_layout(root) / "review" / "queue.jsonl"


def load_review_queue(root: Optional[Path] = None) -> List[DictionaryEntry]:
    path = review_queue_path(root)
    if not path.is_file():
        return []
    out: List[DictionaryEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("lemma"):
            out.append(DictionaryEntry.from_dict(row))
    return out


def save_review_queue(entries: Sequence[DictionaryEntry], root: Optional[Path] = None) -> Path:
    path = review_queue_path(root)
    with path.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
    return path


# --------------------------------------------------------------------------- #
# Merge + routing
# --------------------------------------------------------------------------- #
_FIGURATIVE_MARKERS = (
    "figurative",
    "idiom",
    "slang",
    "informal",
    "colloquial",
    "metaphor",
)


def merge_entries(entries: Iterable[DictionaryEntry]) -> List[DictionaryEntry]:
    """Merge by (language, lemma, pos); keep best gloss/confidence and union sources."""
    buckets: Dict[Tuple[str, str, str], DictionaryEntry] = {}
    for e in entries:
        if not e.lemma:
            continue
        key = (e.language, e.lemma.lower(), (e.pos or "").lower())
        cur = buckets.get(key)
        if cur is None:
            buckets[key] = e
            continue
        # Prefer higher confidence / more sources / lower freq_rank.
        if e.confidence > cur.confidence or (
            e.confidence == cur.confidence and e.freq_rank < cur.freq_rank
        ):
            winner, loser = e, cur
        else:
            winner, loser = cur, e
        sources = sorted(set(winner.sources) | set(loser.sources))
        inflections = dict(loser.inflections)
        inflections.update(winner.inflections)
        examples = list(winner.examples)
        seen = {(ex.get("text") or "").lower() for ex in examples}
        for ex in loser.examples:
            t = (ex.get("text") or "").lower()
            if t and t not in seen:
                examples.append(ex)
                seen.add(t)
        translations = dict(loser.translations)
        translations.update(winner.translations)
        audio = dict(loser.audio)
        audio.update(winner.audio)
        buckets[key] = DictionaryEntry(
            id=winner.id or loser.id or entry_id(winner.language, winner.lemma, winner.pos),
            lemma=winner.lemma,
            language=winner.language,
            pos=winner.pos or loser.pos,
            gloss_en=winner.gloss_en or loser.gloss_en,
            translations=translations,
            ipa=winner.ipa or loser.ipa,
            inflections=inflections,
            rarity=min(winner.rarity, loser.rarity),
            freq_rank=min(winner.freq_rank, loser.freq_rank),
            examples=examples[:12],
            kind=winner.kind if winner.kind != "literal" else loser.kind,
            sources=sources,
            confidence=max(winner.confidence, loser.confidence),
            review_status=winner.review_status,
            audio=audio,
            sense_count=max(winner.sense_count, loser.sense_count),
            notes=winner.notes or loser.notes,
        )
    return sorted(buckets.values(), key=lambda x: (x.freq_rank, x.lemma.lower()))


def should_queue_for_review(entry: DictionaryEntry) -> Tuple[bool, str]:
    """Return (queue?, reason)."""
    if entry.kind in ("slang", "idiom", "figurative", "mwe"):
        return True, f"kind={entry.kind}"
    gloss = (entry.gloss_en or "").lower()
    if any(m in gloss for m in _FIGURATIVE_MARKERS):
        return True, "figurative_gloss"
    if entry.sense_count > 1 and entry.confidence < 0.85:
        return True, "multi_sense"
    # Single-source is fine when confidence is already high (e.g. curated packs).
    if len(entry.sources) < 2 and entry.freq_rank > 500 and entry.confidence < 0.85:
        return True, "low_source_agreement"
    km = (entry.translations or {}).get("km") or {}
    if km.get("target") and not str(km.get("roman") or "").strip():
        return True, "km_missing_roman"
    if entry.language == "km" and "km_missing_roman" in (entry.notes or ""):
        return True, "km_missing_roman"
    if entry.language == "en" and entry.pos in ("n", "noun", "v", "verb", "") and not entry.inflections:
        return True, "missing_inflections"
    if " " in entry.lemma.strip():
        return True, "multiword"
    return False, ""


def route_entries(entries: Sequence[DictionaryEntry]) -> Tuple[List[DictionaryEntry], List[DictionaryEntry]]:
    """Split into (auto_or_keep, queued). Mutates review_status on copies."""
    auto: List[DictionaryEntry] = []
    queued: List[DictionaryEntry] = []
    for e in entries:
        # Preserve human decisions.
        if e.review_status in ("approved", "rejected"):
            auto.append(e)
            continue
        queue, reason = should_queue_for_review(e)
        row = DictionaryEntry.from_dict(e.to_dict())
        if queue:
            row.review_status = "queued"
            if reason and not row.notes:
                row.notes = reason
            elif reason:
                row.notes = f"{row.notes}; {reason}" if row.notes else reason
            queued.append(row)
        else:
            row.review_status = "auto"
            auto.append(row)
    return auto, queued


def apply_human_status(
    entries: Sequence[DictionaryEntry],
    *,
    entry_id_value: str,
    status: str,
    gloss_en: str = "",
    inflections: Optional[Dict[str, str]] = None,
    notes: str = "",
) -> List[DictionaryEntry]:
    if status not in REVIEW_STATUSES:
        raise ValueError(f"status must be one of {REVIEW_STATUSES}")
    out: List[DictionaryEntry] = []
    for e in entries:
        row = DictionaryEntry.from_dict(e.to_dict())
        if row.id == entry_id_value:
            row.review_status = status
            if gloss_en:
                row.gloss_en = gloss_en
            if inflections:
                row.inflections.update(inflections)
            if notes:
                row.notes = notes
        out.append(row)
    return out


def approved_entries(entries: Sequence[DictionaryEntry]) -> List[DictionaryEntry]:
    return [e for e in entries if e.review_status in ("auto", "approved")]


def to_vocabulary_pack_record(entry: DictionaryEntry, *, target_lang: str = "km") -> Optional[dict]:
    """Map a staging entry to a content-pack vocabulary record."""
    if entry.language == target_lang:
        en = entry.gloss_en or entry.lemma
        target = entry.lemma
        roman = ""
    elif entry.language == "en":
        tr = (entry.translations or {}).get(target_lang) or {}
        target = str(tr.get("target") or "").strip()
        roman = str(tr.get("roman") or "").strip()
        en = entry.lemma
        if not target:
            # English-only pack row: target == lemma for EN study.
            if target_lang != "en":
                return None
            target = entry.lemma
    else:
        return None
    if not en or not target:
        return None
    return {
        "language": target_lang if entry.language == "en" and target_lang != "en" else entry.language,
        "id": entry.id,
        "category": entry.kind if entry.kind != "literal" else "core",
        "en": en,
        "target": target,
        "roman": roman,
        "pos": entry.pos,
        "ipa": entry.ipa,
        "inflections": dict(entry.inflections or {}),
        "rarity": entry.rarity,
        "freq_rank": entry.freq_rank,
        "gloss_en": entry.gloss_en,
    }


def to_slang_pack_record(entry: DictionaryEntry) -> Optional[dict]:
    if entry.kind not in ("slang", "idiom", "figurative"):
        return None
    return {
        "phrase": entry.lemma,
        "meaning": entry.gloss_en or entry.lemma,
        "language": entry.language,
        "region": "global",
        "kind": "idiom" if entry.kind in ("idiom", "figurative") else "slang",
        "register": "curated",
    }


# --------------------------------------------------------------------------- #
# Baseline parsers (fixture-friendly; no network)
# --------------------------------------------------------------------------- #
def parse_wordfreq_lines(text: str) -> List[DictionaryEntry]:
    """Parse ``word\\trank`` or ``word\\tfreq`` lines into EN literal entries."""
    out: List[DictionaryEntry] = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"[\s,]+", line)
        if not parts:
            continue
        lemma = parts[0].lower()
        if not re.fullmatch(r"[a-z][a-z'-]*", lemma):
            continue
        rank = i
        if len(parts) > 1 and parts[1].isdigit():
            rank = int(parts[1])
        pos = "noun"
        infl = english_inflections(lemma, pos)
        out.append(
            DictionaryEntry(
                id=entry_id("en", lemma, pos),
                lemma=lemma,
                language="en",
                pos=pos,
                gloss_en="",
                ipa="",
                inflections=infl,
                rarity=rarity_from_rank(rank),
                freq_rank=rank,
                kind="literal",
                sources=["wordfreq"],
                confidence=0.7,
                review_status="queued",
            )
        )
    return out


def parse_cmudict_lines(text: str) -> Dict[str, str]:
    """Return lemma -> ARPAbet-ish string (kept as ipa field placeholder)."""
    out: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(";;;"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        word = parts[0].lower()
        word = re.sub(r"\(\d+\)$", "", word)
        phones = " ".join(parts[1:])
        out.setdefault(word, phones)
    return out


def parse_wordnet_gloss_lines(text: str) -> Dict[str, Tuple[str, str, int]]:
    """Parse ``lemma|pos|gloss|sense_count`` lines → lemma -> (pos, gloss, senses)."""
    out: Dict[str, Tuple[str, str, int]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        lemma = parts[0].strip().lower()
        pos = parts[1].strip()
        gloss = parts[2].strip()
        senses = int(parts[3]) if len(parts) > 3 and parts[3].strip().isdigit() else 1
        if lemma:
            out[lemma] = (pos, gloss, senses)
    return out


def parse_tatoeba_lines(text: str) -> List[dict]:
    """Parse ``lang\\tsentence`` or ``en\\tsentence\\tkm\\tsentence`` TSV."""
    rows: List[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) == 2:
            rows.append({"lang": parts[0], "text": parts[1]})
        elif len(parts) >= 4:
            rows.append({
                "lang": parts[0],
                "text": parts[1],
                "target_lang": parts[2],
                "target_text": parts[3],
            })
    return rows


def parse_wiktionary_lines(text: str) -> List[DictionaryEntry]:
    """Parse ``lemma|pos|kind|gloss`` fixture lines."""
    out: List[DictionaryEntry] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 4:
            continue
        lemma, pos, kind, gloss = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
        kind = kind if kind in KINDS else "literal"
        out.append(
            DictionaryEntry(
                id=entry_id("en", lemma, pos),
                lemma=lemma.lower(),
                language="en",
                pos=pos,
                gloss_en=gloss,
                inflections=english_inflections(lemma, pos) if kind == "literal" else {},
                kind=kind,
                sources=["wiktionary"],
                confidence=0.75 if kind == "literal" else 0.55,
                sense_count=2 if kind != "literal" else 1,
                review_status="queued",
                rarity=0.6,
                freq_rank=5000,
            )
        )
    return out


def enrich_with_cmudict(entries: Sequence[DictionaryEntry], cmudict: Dict[str, str]) -> List[DictionaryEntry]:
    out: List[DictionaryEntry] = []
    for e in entries:
        row = DictionaryEntry.from_dict(e.to_dict())
        if not row.ipa and row.lemma.lower() in cmudict:
            row.ipa = cmudict[row.lemma.lower()]
            if "cmudict" not in row.sources:
                row.sources = list(row.sources) + ["cmudict"]
        out.append(row)
    return out


def enrich_with_wordnet(
    entries: Sequence[DictionaryEntry],
    wn: Dict[str, Tuple[str, str, int]],
) -> List[DictionaryEntry]:
    out: List[DictionaryEntry] = []
    for e in entries:
        row = DictionaryEntry.from_dict(e.to_dict())
        hit = wn.get(row.lemma.lower())
        if hit:
            pos, gloss, senses = hit
            if not row.pos:
                row.pos = pos
            if not row.gloss_en:
                row.gloss_en = gloss
            row.sense_count = max(row.sense_count, senses)
            if "wordnet" not in row.sources:
                row.sources = list(row.sources) + ["wordnet"]
            row.confidence = min(0.95, row.confidence + 0.1)
            if not row.inflections:
                row.inflections = english_inflections(row.lemma, row.pos)
        out.append(row)
    return out


def attach_tatoeba_examples(
    entries: Sequence[DictionaryEntry],
    sentences: Sequence[dict],
    *,
    max_per: int = 3,
) -> List[DictionaryEntry]:
    by_lemma: Dict[str, List[dict]] = {}
    for s in sentences:
        text = str(s.get("text") or "")
        if s.get("lang") not in ("en", None, ""):
            # still index English side when paired
            if s.get("lang") != "en":
                continue
        tokens = set(re.findall(r"[a-z']+", text.lower()))
        for tok in tokens:
            by_lemma.setdefault(tok, []).append({
                "text": text,
                "source": "tatoeba",
                "target_forms": [tok],
                "target_lang": s.get("target_lang"),
                "target_text": s.get("target_text"),
            })
    out: List[DictionaryEntry] = []
    for e in entries:
        row = DictionaryEntry.from_dict(e.to_dict())
        cands = by_lemma.get(row.lemma.lower(), [])[:max_per]
        if cands:
            existing = {(ex.get("text") or "").lower() for ex in row.examples}
            for c in cands:
                if c["text"].lower() not in existing:
                    row.examples.append(c)
            if "tatoeba" not in row.sources:
                row.sources = list(row.sources) + ["tatoeba"]
            # Pull KM translation from first paired sentence if missing.
            if "km" not in row.translations:
                for c in cands:
                    if c.get("target_lang") == "km" and c.get("target_text"):
                        row.translations["km"] = {
                            "target": c["target_text"],
                            "roman": "",
                        }
                        break
            row.confidence = min(0.95, row.confidence + 0.05)
        out.append(row)
    return out


def merge_khmer_pack_records(records: Sequence[dict]) -> List[DictionaryEntry]:
    """Lift existing vocabulary pack rows into staging entries (EN + KM views)."""
    out: List[DictionaryEntry] = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        en = str(rec.get("en") or "").strip()
        target = str(rec.get("target") or "").strip()
        roman = str(rec.get("roman") or "").strip()
        lang = str(rec.get("language") or "km")
        if not en or not target:
            continue
        eid = str(rec.get("id") or entry_id("en", en, "noun"))
        out.append(
            DictionaryEntry(
                id=eid,
                lemma=en.lower(),
                language="en",
                pos=str(rec.get("pos") or "noun"),
                gloss_en=en,
                translations={"km": {"target": target, "roman": roman}},
                ipa=str(rec.get("ipa") or ""),
                inflections=english_inflections(en, str(rec.get("pos") or "noun")),
                rarity=float(rec.get("rarity") if rec.get("rarity") is not None else 0.3),
                freq_rank=int(rec.get("freq_rank") or (1000 + i)),
                kind="literal",
                sources=["khmer_pack"],
                confidence=0.9 if roman else 0.7,
                review_status="auto" if roman else "queued",
            )
        )
        out.append(
            DictionaryEntry(
                id=f"km-{eid}",
                lemma=target,
                language="km",
                pos=str(rec.get("pos") or "noun"),
                gloss_en=en,
                translations={"en": {"target": en, "roman": ""}},
                inflections={},
                rarity=float(rec.get("rarity") if rec.get("rarity") is not None else 0.3),
                freq_rank=int(rec.get("freq_rank") or (1000 + i)),
                kind="literal",
                sources=["khmer_pack"],
                confidence=0.9 if roman else 0.7,
                review_status="auto" if roman else "queued",
                notes="" if roman else "km_missing_roman",
            )
        )
    return out


def ingest_from_baseline_dir(baseline_dir: Path) -> List[DictionaryEntry]:
    """Load all known fixture/dump filenames from a baselines directory."""
    entries: List[DictionaryEntry] = []
    wf = baseline_dir / "wordfreq_en.txt"
    if wf.is_file():
        entries.extend(parse_wordfreq_lines(wf.read_text(encoding="utf-8")))
    wn_path = baseline_dir / "wordnet_glosses.txt"
    wn = parse_wordnet_gloss_lines(wn_path.read_text(encoding="utf-8")) if wn_path.is_file() else {}
    cmu_path = baseline_dir / "cmudict.txt"
    cmu = parse_cmudict_lines(cmu_path.read_text(encoding="utf-8")) if cmu_path.is_file() else {}
    wiki = baseline_dir / "wiktionary_en.txt"
    if wiki.is_file():
        entries.extend(parse_wiktionary_lines(wiki.read_text(encoding="utf-8")))
    tat = baseline_dir / "tatoeba.tsv"
    sentences = parse_tatoeba_lines(tat.read_text(encoding="utf-8")) if tat.is_file() else []

    if wn:
        entries = enrich_with_wordnet(entries, wn)
    if cmu:
        entries = enrich_with_cmudict(entries, cmu)
    if sentences:
        entries = attach_tatoeba_examples(entries, sentences)

    # Optional local khmer pack dump (JSON list) for offline merge without import cycle.
    km_path = baseline_dir / "khmer_vocab.json"
    if km_path.is_file():
        try:
            data = json.loads(km_path.read_text(encoding="utf-8"))
            recs = data.get("records") if isinstance(data, dict) else data
            if isinstance(recs, list):
                entries.extend(merge_khmer_pack_records(recs))
        except json.JSONDecodeError:
            pass

    return merge_entries(entries)


def fingerprint_baselines(baseline_dir: Path) -> str:
    h = hashlib.sha256()
    if not baseline_dir.is_dir():
        return h.hexdigest()
    for path in sorted(baseline_dir.iterdir()):
        if not path.is_file():
            continue
        st = path.stat()
        h.update(path.name.encode("utf-8"))
        h.update(str(st.st_size).encode("utf-8"))
        h.update(str(int(st.st_mtime)).encode("utf-8"))
    return h.hexdigest()


def write_fingerprint(root: Path, fp: str) -> None:
    ensure_layout(root)
    (root / "baselines" / ".fingerprint").write_text(fp + "\n", encoding="utf-8")


def read_fingerprint(root: Path) -> str:
    path = root / "baselines" / ".fingerprint"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()
