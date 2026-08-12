"""Turn raw PDF/PPTX page text into teachable slide content.

Raw extraction yields covers, tables of contents, reference lists, running
headers/footers and page numbers. Feeding those straight into a course produces
slides that teach nothing. This module classifies pages, strips per-document
boilerplate, and derives a usable title/body.

Fully offline: pure stdlib string heuristics, no models or network.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

_WS_RE = re.compile(r"[ \t\u00a0]+")
_DOT_LEADER_RE = re.compile(r"\.{4,}\s*\d+\s*$")
_PAGE_NUM_ONLY_RE = re.compile(r"^\s*(?:page\s*)?[-–—]?\s*\d{1,4}\s*(?:of\s*\d{1,4})?\s*[-–—]?\s*$", re.I)
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")
# Running headers/footers vary per page ("... | Policy 4.12 | Page 5"), so
# repetition alone will not catch them.
_RUNNING_HEAD_RE = re.compile(
    r"^(?:.{0,80}\|.{0,80}\|.{0,80}|.{0,60}\bpage\s+\d{1,4}(?:\s+of\s+\d{1,4})?\b.{0,20})$",
    re.I,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']+")
_CITATION_RE = re.compile(
    r"\b\d+\s*(?:C\.?F\.?R\.?|U\.?S\.?C\.?|F\.?\s?Supp|U\.?S\.?)\b|\bv\.\s+[A-Z]|\(\d{4}\)"
)

_TOC_MARKERS = ("table of contents", "contents", "index")
_REF_MARKERS = (
    "references",
    "bibliography",
    "works cited",
    "further reading",
    "appendix",
    "glossary",
)
_COVER_MARKERS = (
    "training",
    "presented by",
    "prepared by",
    "revised",
    "all rights reserved",
    "copyright",
    "office of",
    "department of",
)


class PageKind(str, Enum):
    CONTENT = "content"
    COVER = "cover"
    TOC = "toc"
    REFERENCES = "references"
    BLANK = "blank"
    JUNK = "junk"


@dataclass
class CleanPage:
    index: int
    kind: PageKind
    title: str
    body: str
    reason: str = ""
    removed_lines: int = 0

    @property
    def teachable(self) -> bool:
        return self.kind is PageKind.CONTENT


@dataclass
class DocumentAnalysis:
    pages: list[CleanPage] = field(default_factory=list)
    boilerplate: list[str] = field(default_factory=list)

    @property
    def teachable_pages(self) -> list[CleanPage]:
        return [p for p in self.pages if p.teachable]

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for page in self.pages:
            out[page.kind.value] = out.get(page.kind.value, 0) + 1
        return out


def _norm_line(line: str) -> str:
    return _WS_RE.sub(" ", line).strip()


def detect_boilerplate(page_texts: list[str], min_ratio: float = 0.5) -> set[str]:
    """Lines repeated across most pages are headers/footers, not teaching content."""
    if len(page_texts) < 3:
        return set()
    counts: Counter[str] = Counter()
    for text in page_texts:
        seen: set[str] = set()
        for raw in (text or "").splitlines():
            line = _norm_line(raw)
            # Only short lines are plausible headers/footers.
            if not line or len(line) > 90:
                continue
            if line in seen:
                continue
            seen.add(line)
            counts[line] += 1
    threshold = max(2, int(len(page_texts) * min_ratio))
    return {line for line, n in counts.items() if n >= threshold}


def clean_text(text: str, boilerplate: set[str] | None = None) -> tuple[str, int]:
    """Strip boilerplate/page numbers/dot leaders; repair hyphenated line breaks."""
    boilerplate = boilerplate or set()
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text or "")
    kept: list[str] = []
    removed = 0
    for raw in text.splitlines():
        line = _norm_line(raw)
        if not line:
            continue
        if line in boilerplate:
            removed += 1
            continue
        if _PAGE_NUM_ONLY_RE.match(line):
            removed += 1
            continue
        if _DOT_LEADER_RE.search(line):
            removed += 1
            continue
        if _RUNNING_HEAD_RE.match(line):
            removed += 1
            continue
        kept.append(line)
    return "\n".join(kept), removed


def _alpha_ratio(text: str) -> float:
    if not text:
        return 0.0
    alpha = sum(1 for ch in text if ch.isalpha() or ch.isspace())
    return alpha / len(text)


def classify_page(title: str, body: str) -> tuple[PageKind, str]:
    """Decide whether a page can teach anything."""
    text = f"{title}\n{body}".strip()
    lowered = text.lower()
    words = _WORD_RE.findall(text)
    stripped = text.strip()

    if len(stripped) < 60 or len(words) < 12:
        return PageKind.BLANK, "too little text to teach"

    lines = [ln for ln in text.splitlines() if ln.strip()]

    # Table of contents: many lines that end in a page number.
    numbered_tail = sum(1 for ln in lines if re.search(r"\.{2,}\s*\d+\s*$|\s\d{1,3}\s*$", ln))
    if lines and (
        any(m in lowered[:200] for m in _TOC_MARKERS) and numbered_tail >= 2
        or numbered_tail / len(lines) > 0.5
    ):
        return PageKind.TOC, "table of contents / index listing"

    # Reference or appendix pages: citation-dense, low prose.
    first_line = _norm_line(lines[0]).lower() if lines else ""
    citations = len(_CITATION_RE.findall(text))
    if any(first_line.startswith(m) for m in _REF_MARKERS) and citations >= 1:
        return PageKind.REFERENCES, "reference/appendix list, not teachable prose"
    if citations >= 3 and len(words) < 120:
        return PageKind.REFERENCES, "citation list rather than explanation"

    # Checked after TOC/references so those get an accurate reason.
    if _alpha_ratio(text) < 0.72:
        return PageKind.JUNK, "mostly numbers/symbols (likely OCR noise or a table)"

    # Cover page: short, title-ish, org/date metadata, few real sentences.
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(body or "") if len(s.split()) >= 6]
    cover_hits = sum(1 for m in _COVER_MARKERS if m in lowered)
    if len(words) < 45 and len(sentences) <= 1 and cover_hits >= 1:
        return PageKind.COVER, "cover/title page metadata"

    # Needs at least one real explanatory sentence.
    if not sentences:
        return PageKind.JUNK, "no complete sentence to narrate"

    return PageKind.CONTENT, ""


def derive_title(body: str, fallback: str, boilerplate: set[str] | None = None) -> str:
    """Pick a human title, skipping headers, page numbers and bare fragments."""
    boilerplate = boilerplate or set()
    for raw in (body or "").splitlines():
        line = _norm_line(raw)
        if not line or line in boilerplate:
            continue
        if _PAGE_NUM_ONLY_RE.match(line) or _DOT_LEADER_RE.search(line):
            continue
        if _RUNNING_HEAD_RE.match(line):
            continue
        words = _WORD_RE.findall(line)
        if len(words) < 2 or len(line) > 120:
            continue
        # Prefer a heading-like line over a mid-sentence fragment.
        return line.rstrip(" .:;,-")

    # No heading line: summarize the opening sentence instead of falling back to
    # a header, which would put boilerplate on the slide.
    for sentence in _SENTENCE_SPLIT_RE.split(body or ""):
        words = sentence.split()
        if len(words) >= 6:
            summary = " ".join(words[:9]).rstrip(" .:;,-")
            return summary[:120]
    return fallback


def _token_set(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text or "")}


def similarity(a: str, b: str) -> float:
    """Jaccard overlap — cheap near-duplicate signal."""
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def analyze_document(
    pages: list[tuple[int, str, str]],
) -> DocumentAnalysis:
    """``pages`` is [(index, raw_title, raw_text)] for ONE document."""
    raw_texts = [text for _i, _t, text in pages]
    boilerplate = detect_boilerplate(raw_texts)
    analysis = DocumentAnalysis(boilerplate=sorted(boilerplate))
    for index, raw_title, raw_text in pages:
        body, removed = clean_text(raw_text, boilerplate)
        title = derive_title(body, fallback=_norm_line(raw_title)[:120], boilerplate=boilerplate)
        kind, reason = classify_page(title, body)
        analysis.pages.append(
            CleanPage(
                index=index,
                kind=kind,
                title=title,
                body=body,
                reason=reason,
                removed_lines=removed,
            )
        )
    return analysis


def dedupe_pages(pages: list[CleanPage], threshold: float = 0.85) -> list[CleanPage]:
    """Drop near-identical pages (repeated policy blocks across documents)."""
    kept: list[CleanPage] = []
    for page in pages:
        if any(similarity(page.body, other.body) >= threshold for other in kept):
            continue
        kept.append(page)
    return kept
