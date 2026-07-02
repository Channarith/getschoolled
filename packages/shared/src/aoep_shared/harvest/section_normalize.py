"""Clean and merge extracted sections before slide generation.

Raw PDF/HTML extraction often yields table-of-contents fragments, dot leaders,
and one-line stubs. This pass filters junk and merges small sections into
learning units sized for teachable slides.
"""

from __future__ import annotations

import re
from typing import List, Tuple

from .extractors import ExtractedDoc

_DOT_LEADER = re.compile(r"\.{2,}\s*\d*")
_TRAILING_PAGE = re.compile(r"\s+\d{1,4}\s*$")
_CHAPTER_NOTES = re.compile(r"^chapter notes\b", re.I)
_MOSTLY_NON_ALPHA = re.compile(r"^[\d\s\.\-]+$")
_JUNK_HEADING = re.compile(
    r"^(?:H\d+|E\[|Y=\d|ˆY=|F1=|\d{1,2}[A-Za-z]{1,4}$|chapter,\s)",
    re.I,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_ROMAN_PAGE = re.compile(r"\b(?:iv|v|vi{1,3}|ix|x|xi{0,3})\b", re.I)
_METADATA = re.compile(
    r"licensed under|creative commons|compiled on|mlstory\.org|by-nc-nd",
    re.I,
)
_MATH_SYMBOLS = re.compile(r"[⊥∫∑≤≥∈∀∃λθη]|FPR=|TPR=|R⊥")

MIN_UNIT_CHARS = 80
MAX_UNIT_CHARS = 2400
MIN_PROSE_CHARS = 36


def clean_heading(heading: str) -> str:
    h = (heading or "").strip()
    h = _DOT_LEADER.sub("", h).strip()
    h = _TRAILING_PAGE.sub("", h).strip()
    h = re.sub(r"\s+", " ", h)
    # Drop leading section numbers glued to title ("1Introduction" -> "Introduction")
    h = re.sub(r"^\d+\s*", "", h)
    return h[:120] or "Section"


def clean_body_text(text: str) -> str:
    t = (text or "").strip()
    t = _DOT_LEADER.sub(" ", t)
    t = _TRAILING_PAGE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _is_toc_listing(text: str) -> bool:
    """Detect table-of-contents lines (many short topic stubs with dot leaders)."""
    if ". ." in text or text.count(" . ") >= 2:
        return True
    fragments = re.split(r"\.{2,}|\s{2,}", text)
    fragments = [f.strip(" .") for f in fragments if len(f.strip(" .")) > 2]
    if len(fragments) >= 3:
        avg = sum(len(f) for f in fragments) / len(fragments)
        if avg < 48:
            return True
    if text.count(".") > len(text) / 6 and len(text) < 200:
        return True
    return False


def _looks_like_prose_sentence(sentence: str) -> bool:
    s = sentence.strip()
    if len(s) < MIN_PROSE_CHARS:
        return False
    alpha = sum(c.isalpha() for c in s)
    if alpha < len(s) * 0.45:
        return False
    words = s.split()
    if len(words) < 6:
        return False
    if _ROMAN_PAGE.search(s) and len(s) < 120:
        return False
    return True


def extract_prose(text: str) -> str:
    """Pull teachable sentences out of noisy PDF extraction."""
    t = clean_body_text(text)
    t = re.sub(r"\.{2,}", ". ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    sentences = _SENTENCE_RE.split(t)
    good = [s.strip() for s in sentences if _looks_like_prose_sentence(s.strip())]
    if not good and len(t) >= MIN_PROSE_CHARS and not _is_toc_listing(t):
        alpha = sum(c.isalpha() for c in t)
        if alpha >= len(t) * 0.45 and len(t.split()) >= 6:
            return t
    return " ".join(good)


def _heading_alpha_ratio(heading: str) -> float:
    h = heading or ""
    if not h:
        return 0.0
    return sum(c.isalpha() for c in h) / len(h)


def _derive_heading(body: str, fallback: str = "Key idea") -> str:
    prose = extract_prose(body)
    if not prose:
        return fallback
    first = _SENTENCE_RE.split(prose)[0].strip()
    first = re.sub(r"\s+", " ", first)
    if len(first) >= 24:
        return first[:100].rstrip(".")
    return fallback


def sanitize_heading(heading: str, body: str) -> str:
    h = clean_heading(heading)
    if is_junk_heading(h) or _MATH_SYMBOLS.search(h) or _heading_alpha_ratio(h) < 0.35:
        return _derive_heading(body, fallback="Key idea")
    return h


def is_junk_heading(heading: str) -> bool:
    h = clean_heading(heading)
    if _CHAPTER_NOTES.match(h):
        return True
    if _JUNK_HEADING.match(h):
        return True
    if len(h) <= 3 and not h.isalpha():
        return True
    return False


def is_junk_section(heading: str, text: str) -> bool:
    prose = extract_prose(text)
    if _METADATA.search(prose) and len(prose) < 420:
        return True
    if is_junk_heading(heading) and not prose:
        return True
    if not prose or len(prose) < MIN_PROSE_CHARS:
        return True
    if _is_toc_listing(text):
        return True
    if _MOSTLY_NON_ALPHA.match(prose):
        return True
    alpha = sum(c.isalpha() for c in prose)
    if alpha < max(24, len(prose) * 0.35):
        return True
    return False


def merge_learning_units(
    sections: List[Tuple[str, str]],
    *,
    min_chars: int = MIN_UNIT_CHARS,
    max_chars: int = MAX_UNIT_CHARS,
) -> List[Tuple[str, str]]:
    """Merge consecutive sections that share a heading (PDF page splits).

    A new heading always starts a fresh unit. Only back-to-back fragments with
    the same title are joined, up to ``max_chars``.
    """
    units: List[Tuple[str, str]] = []
    cur_heading = ""
    cur_parts: List[str] = []

    def flush() -> None:
        nonlocal cur_heading, cur_parts
        if not cur_parts:
            return
        body = extract_prose(" ".join(cur_parts))
        if body and not is_junk_section(cur_heading, body):
            title = sanitize_heading(cur_heading, body)
            units.append((title, body))
        cur_heading = ""
        cur_parts = []

    for heading, text in sections:
        h = clean_heading(heading)
        prose = extract_prose(text)
        if is_junk_section(h, text) and not prose:
            continue

        # Attach orphan math/chart fragments to the current lesson block.
        if cur_parts and (is_junk_heading(h) or _MATH_SYMBOLS.search(h)):
            cur_parts.append(prose or clean_body_text(text))
            if len(" ".join(cur_parts)) >= max_chars:
                flush()
            continue

        if cur_parts and h.lower() != cur_heading.lower():
            flush()

        if not cur_parts:
            cur_heading = h
        cur_parts.append(prose or clean_body_text(text))

        if len(" ".join(cur_parts)) >= max_chars:
            flush()

    flush()
    return units


def merge_short_lessons(
    sections: List[Tuple[str, str]],
    *,
    target_chars: int = 1200,
    max_chars: int = 4000,
) -> List[Tuple[str, str]]:
    """Combine consecutive thin lessons into chapter-sized teaching blocks."""
    if not sections:
        return []
    out: List[Tuple[str, str]] = []
    cur_h = ""
    cur_body = ""

    def flush() -> None:
        nonlocal cur_h, cur_body
        if cur_body.strip():
            out.append((sanitize_heading(cur_h, cur_body), cur_body.strip()))
        cur_h = ""
        cur_body = ""

    for heading, body in sections:
        h = sanitize_heading(heading, body)
        if cur_body and (
            len(cur_body) >= max_chars
            or (len(cur_body) >= target_chars and h.lower() != cur_h.lower())
        ):
            flush()
        if not cur_body:
            cur_h = h
        cur_body = f"{cur_body} {body}".strip() if cur_body else body

    flush()
    return out


def normalize_document(doc: ExtractedDoc) -> ExtractedDoc:
    """Return a copy of ``doc`` with cleaned, merged sections."""
    raw = [(h, t) for h, t in doc.sections if (t or "").strip()]
    merged = merge_learning_units(raw)
    if doc.source_type == "pdf" and len(merged) > 24:
        merged = merge_short_lessons(merged)
    if not merged and raw:
        # Last resort: keep the longest non-junk sections.
        kept = []
        for h, t in raw:
            h2 = clean_heading(h)
            body = extract_prose(t)
            if body and not is_junk_section(h2, body):
                kept.append((h2, body))
        kept.sort(key=lambda ht: len(ht[1]), reverse=True)
        merged = kept[:12]
    return ExtractedDoc(
        title=doc.title,
        language=doc.language,
        source_type=doc.source_type,
        sections=merged,
    )
