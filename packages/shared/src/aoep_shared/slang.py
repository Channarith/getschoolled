"""Culture-aware slang & idiom understanding.

A data-driven lexicon of slang/idioms keyed by language + region/culture, plus a
normalizer that detects them in student input and produces a plain-meaning
"gloss". The Tutor runs this before retrieval/LLM so it understands what a
student actually means (e.g. "it's a piece of cake" -> "it is very easy"), and
can answer in the student's register.

Pure and dependency-free, so it is fully testable offline. The lexicon is the
extensible backbone; an LLM can be layered on for unseen expressions, behind the
same ``normalize`` shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


@dataclass(frozen=True)
class SlangEntry:
    phrase: str
    meaning: str
    language: str = "en"
    region: str = "global"   # us | uk | mx | fr | kh | global | ...
    kind: str = "idiom"      # idiom | slang
    register: str = "casual"


# Seed lexicon across several languages/cultures. Tasteful, widely-known entries;
# extend freely (or load from a DB) - this is just the starting set.
LEXICON: List[SlangEntry] = [
    # English (US)
    SlangEntry("hit the books", "study hard", "en", "us", "idiom"),
    SlangEntry("piece of cake", "very easy", "en", "us", "idiom"),
    SlangEntry("ace the test", "do extremely well on the test", "en", "us", "idiom"),
    SlangEntry("no cap", "no lie / for real", "en", "us", "slang"),
    SlangEntry("lit", "exciting or excellent", "en", "us", "slang"),
    SlangEntry("my bad", "my mistake / I apologize", "en", "us", "slang"),
    SlangEntry("ghosted", "suddenly stopped responding", "en", "us", "slang"),
    # English (UK)
    SlangEntry("knackered", "very tired / exhausted", "en", "uk", "slang"),
    SlangEntry("chuffed", "very pleased", "en", "uk", "slang"),
    SlangEntry("gutted", "very disappointed", "en", "uk", "slang"),
    SlangEntry("bits and bobs", "small miscellaneous items", "en", "uk", "idiom"),
    # Spanish (Mexico)
    SlangEntry("que onda", "what's up / how's it going", "es", "mx", "slang"),
    SlangEntry("no manches", "no way / you're kidding", "es", "mx", "slang"),
    SlangEntry("echarle ganas", "to put in effort / try hard", "es", "mx", "idiom"),
    # French
    SlangEntry("avoir le cafard", "to feel down / have the blues", "fr", "fr", "idiom"),
    SlangEntry("c'est du gateau", "it's a piece of cake / very easy", "fr", "fr", "idiom"),
    # Khmer (romanized, common in learning contexts)
    SlangEntry("sok sabay", "doing well / fine", "km", "kh", "idiom"),
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


@dataclass
class Detection:
    phrase: str
    meaning: str
    region: str
    kind: str
    start: int
    end: int


@dataclass
class NormalizedText:
    original: str
    plain: str                       # idioms expanded inline for RAG/LLM
    detections: List[Detection] = field(default_factory=list)

    @property
    def glossed(self) -> List[str]:
        return [f"{d.phrase} = {d.meaning}" for d in self.detections]


class SlangLexicon:
    def __init__(self, entries: Optional[Sequence[SlangEntry]] = None) -> None:
        self._entries: List[SlangEntry] = list(entries if entries is not None else LEXICON)

    def add(self, entry: SlangEntry) -> None:
        self._entries.append(entry)

    def _candidates(self, language: Optional[str], region: Optional[str]) -> List[SlangEntry]:
        out = self._entries
        if language:
            out = [e for e in out if e.language == language]
        if region:
            out = [e for e in out if e.region in (region, "global")]
        # Longest phrases first so multi-word idioms win over sub-spans.
        return sorted(out, key=lambda e: len(e.phrase), reverse=True)

    def lookup(
        self, phrase: str, *, language: Optional[str] = None, region: Optional[str] = None
    ) -> Optional[SlangEntry]:
        target = _norm(phrase)
        for e in self._candidates(language, region):
            if _norm(e.phrase) == target:
                return e
        return None

    def detect(
        self, text: str, *, language: Optional[str] = None, region: Optional[str] = None
    ) -> List[Detection]:
        hay = _norm(text)
        consumed = [False] * len(hay)
        detections: List[Detection] = []
        for e in self._candidates(language, region):
            needle = _norm(e.phrase)
            pattern = re.compile(
                r"(?<![\w'])" + re.escape(needle) + r"(?![\w'])"
            )
            for m in pattern.finditer(hay):
                s, en = m.start(), m.end()
                if any(consumed[s:en]):
                    continue
                for i in range(s, en):
                    consumed[i] = True
                detections.append(
                    Detection(
                        phrase=e.phrase,
                        meaning=e.meaning,
                        region=e.region,
                        kind=e.kind,
                        start=s,
                        end=en,
                    )
                )
        detections.sort(key=lambda d: d.start)
        return detections

    def normalize(
        self, text: str, *, language: Optional[str] = None, region: Optional[str] = None
    ) -> NormalizedText:
        detections = self.detect(text, language=language, region=region)
        # Build a plain version by appending the meaning after each detected
        # phrase (on the normalized text), so retrieval/LLM see both.
        hay = _norm(text)
        plain_parts: List[str] = []
        cursor = 0
        for d in detections:
            plain_parts.append(hay[cursor:d.end])
            plain_parts.append(f" ({d.meaning})")
            cursor = d.end
        plain_parts.append(hay[cursor:])
        plain = "".join(plain_parts).strip() if detections else text
        return NormalizedText(original=text, plain=plain, detections=detections)


_default: Optional[SlangLexicon] = None


def default_lexicon() -> SlangLexicon:
    global _default
    if _default is None:
        _default = SlangLexicon()
    return _default
