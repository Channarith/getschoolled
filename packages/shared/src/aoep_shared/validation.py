"""Course validation via multi-engine web corroboration.

Extracts claims from course content, searches them across the configured
`SearchProvider`s (Workstream 1), and corroborates each claim against the
returned snippets to produce a verdict (supported / unverified / contradicted)
with a confidence score and citations. Pure/offline-testable: the corroboration
is a transparent lexical-overlap heuristic; an LLM judge can be layered later
behind the same `validate_claim` shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .providers.base import SearchProvider

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "be", "of", "to", "in", "on",
    "and", "or", "for", "with", "that", "this", "it", "as", "by", "from", "at",
    "into", "using", "uses", "use", "can", "we", "our", "you", "your", "they",
}
# Lightweight contradiction cues near claim terms.
_NEGATION = {"not", "no", "never", "false", "myth", "debunked", "incorrect", "untrue"}


def _tokens(text: str) -> List[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2]


def _recall(claim_tokens: Sequence[str], snippet_tokens: Sequence[str]) -> float:
    """Fraction of the claim's content tokens present in the snippet."""
    if not claim_tokens:
        return 0.0
    snip = set(snippet_tokens)
    hit = sum(1 for t in set(claim_tokens) if t in snip)
    return hit / len(set(claim_tokens))


@dataclass
class Claim:
    text: str
    topic: str = ""


@dataclass
class Citation:
    title: str
    url: str
    snippet: str
    engine: str
    overlap: float


@dataclass
class ClaimVerdict:
    claim: str
    status: str            # supported | unverified | contradicted
    confidence: float      # 0..1
    citations: List[Citation] = field(default_factory=list)
    engines_consulted: int = 0


@dataclass
class CourseValidationReport:
    total: int
    supported: int
    unverified: int
    contradicted: int
    verdicts: List[ClaimVerdict] = field(default_factory=list)

    @property
    def flagged(self) -> List[ClaimVerdict]:
        return [v for v in self.verdicts if v.status != "supported"]


_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def extract_claims(text: str, *, topic: str = "", min_tokens: int = 4) -> List[Claim]:
    """Split content into candidate factual claims (substantive sentences)."""
    claims: List[Claim] = []
    for raw in _SENTENCE.split(text.strip()):
        s = raw.strip()
        if s and len(_tokens(s)) >= min_tokens:
            claims.append(Claim(text=s, topic=topic))
    return claims


def validate_claim(
    claim: str,
    engines: Sequence[SearchProvider],
    *,
    max_results: int = 5,
    support_threshold: float = 0.5,
    min_engines_for_support: int = 1,
) -> ClaimVerdict:
    """Corroborate one claim across the given search engines."""
    claim_tokens = _tokens(claim)
    citations: List[Citation] = []
    supporting_engines = set()
    contradicting = False
    consulted = 0

    for engine in engines:
        try:
            results = engine.search(claim, max_results=max_results)
        except Exception:  # noqa: BLE001 - a flaky/unconfigured engine is skipped
            continue
        consulted += 1
        best = 0.0
        for r in results:
            snippet_tokens = _tokens(r.snippet)
            ov = _recall(claim_tokens, snippet_tokens)
            if ov > 0:
                citations.append(
                    Citation(r.title, r.url, r.snippet, r.engine, round(ov, 3))
                )
            if ov >= support_threshold:
                supporting_engines.add(getattr(engine, "engine", "search"))
            best = max(best, ov)
            if any(n in snippet_tokens for n in _NEGATION) and ov >= support_threshold:
                contradicting = True

    citations.sort(key=lambda c: c.overlap, reverse=True)
    citations = citations[:max_results]

    if contradicting:
        status, confidence = "contradicted", 0.5
    elif len(supporting_engines) >= min_engines_for_support and citations:
        status = "supported"
        # Confidence grows with best overlap and number of corroborating engines.
        best_overlap = citations[0].overlap if citations else 0.0
        confidence = min(1.0, 0.6 * best_overlap + 0.4 * min(1.0, len(supporting_engines) / 2))
    else:
        status, confidence = "unverified", round(citations[0].overlap if citations else 0.0, 3)

    return ClaimVerdict(
        claim=claim,
        status=status,
        confidence=round(confidence, 3),
        citations=citations,
        engines_consulted=consulted,
    )


def validate_course(
    claims: Sequence[Claim],
    engines: Sequence[SearchProvider],
    *,
    max_results: int = 5,
    support_threshold: float = 0.5,
) -> CourseValidationReport:
    verdicts = [
        validate_claim(c.text, engines, max_results=max_results,
                       support_threshold=support_threshold)
        for c in claims
    ]
    supported = sum(1 for v in verdicts if v.status == "supported")
    contradicted = sum(1 for v in verdicts if v.status == "contradicted")
    unverified = sum(1 for v in verdicts if v.status == "unverified")
    return CourseValidationReport(
        total=len(verdicts),
        supported=supported,
        unverified=unverified,
        contradicted=contradicted,
        verdicts=verdicts,
    )
