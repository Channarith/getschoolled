"""Content scraper -> presentation decks.

Extracts teaching content from multiple sources and turns it into a slide deck
(reusing the CMS Deck model), so a class can be authored from a textbook PDF, a
web article, or a video/YouTube transcript. Supports different class genres via
``ClassFormat`` (lecture, hands-on, tutorial, video, article).

Extraction is dependency-light:
  - PDF   -> pypdf (text per page, split into sections by headings)
  - HTML  -> BeautifulSoup (title + h1-h3 headings with their paragraphs)
  - video -> transcript segments grouped into time windows
The slide condensation is deterministic (no LLM) so it runs and is tested
offline; when an LLM is configured the orchestrator can rewrite slide bodies for
polish, behind the same Deck shape.
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .decks import Deck, SlideSpec

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_HEADING_HINT = re.compile(r"^(chapter|section|unit|lesson|part)\b", re.IGNORECASE)


class ClassFormat(str, enum.Enum):
    LECTURE = "lecture"
    HANDS_ON = "hands_on"
    TUTORIAL = "tutorial"
    VIDEO = "video"
    ARTICLE = "article"


@dataclass
class Section:
    heading: str
    text: str = ""


@dataclass
class ScrapeResult:
    title: str
    language: str
    sections: List[Section] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Extractors
# --------------------------------------------------------------------------- #
def _looks_like_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 80:
        return False
    if _HEADING_HINT.match(s):
        return True
    # Title Case or ALL CAPS short lines with no terminal punctuation.
    if s[-1] in ".,;:":
        return False
    words = s.split()
    if 1 <= len(words) <= 10 and (s.isupper() or s.istitle()):
        return True
    return False


def extract_pdf(data: bytes, *, default_title: str = "Untitled") -> ScrapeResult:
    from pypdf import PdfReader  # lazy
    from io import BytesIO

    reader = PdfReader(BytesIO(data))
    title = default_title
    meta_title = getattr(reader.metadata, "title", None) if reader.metadata else None
    if meta_title:
        title = str(meta_title).strip() or default_title

    sections: List[Section] = []
    current: Optional[Section] = None
    for page in reader.pages:
        text = page.extract_text() or ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if _looks_like_heading(line):
                current = Section(heading=line)
                sections.append(current)
            else:
                if current is None:
                    current = Section(heading=title)
                    sections.append(current)
                current.text = (current.text + " " + line).strip()
    # Drop empty sections.
    sections = [s for s in sections if s.text]
    return ScrapeResult(title=title, language="en", sections=sections)


def extract_html(html: str, *, default_title: str = "Untitled") -> ScrapeResult:
    from bs4 import BeautifulSoup  # lazy

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    title = default_title
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)

    sections: List[Section] = []
    current = Section(heading=title)
    for el in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        if el.name in ("h1", "h2", "h3"):
            current = Section(heading=txt)
            sections.append(current)
        else:
            if current not in sections:
                sections.append(current)
            current.text = (current.text + " " + txt).strip()
    sections = [s for s in sections if s.text]
    if not sections:
        # Fallback: whole-body text as one section.
        body = soup.get_text(" ", strip=True)
        if body:
            sections = [Section(heading=title, text=body)]
    return ScrapeResult(title=title, language="en", sections=sections)


@dataclass
class TranscriptSegment:
    start: float
    text: str


def extract_transcript(
    segments: Sequence[TranscriptSegment],
    *,
    title: str = "Video",
    window_seconds: float = 60.0,
) -> ScrapeResult:
    """Group transcript segments into time-windowed sections."""
    sections: List[Section] = []
    bucket: List[str] = []
    window_start = 0.0
    for seg in segments:
        if seg.start >= window_start + window_seconds and bucket:
            mm = int(window_start // 60)
            sections.append(
                Section(heading=f"{title} [{mm:02d}:00]", text=" ".join(bucket))
            )
            bucket = []
            window_start = seg.start - (seg.start % window_seconds)
        bucket.append(seg.text.strip())
    if bucket:
        mm = int(window_start // 60)
        sections.append(Section(heading=f"{title} [{mm:02d}:00]", text=" ".join(bucket)))
    return ScrapeResult(title=title, language="en", sections=sections)


# --------------------------------------------------------------------------- #
# Deck generation
# --------------------------------------------------------------------------- #
def _condense(text: str, *, max_sentences: int = 3, max_chars: int = 360) -> str:
    sentences = _SENTENCE_RE.split(text.strip())
    body = " ".join(sentences[:max_sentences]).strip()
    return body[:max_chars].rstrip()


def _narration(body: str) -> str:
    sentences = _SENTENCE_RE.split(body.strip())
    return sentences[0].strip() if sentences else body


def sections_to_deck(
    result: ScrapeResult,
    *,
    fmt: ClassFormat = ClassFormat.LECTURE,
    source: str = "",
) -> Deck:
    slides: List[SlideSpec] = []
    for section in result.sections:
        body = _condense(section.text)
        if not body:
            continue
        if fmt is ClassFormat.HANDS_ON:
            body = f"{body}\n\nTry it: practice this step before moving on."
        slides.append(
            SlideSpec(
                title=section.heading[:120],
                body=body,
                narration=_narration(body),
            )
        )
    return Deck(
        deck_id=uuid.uuid4().hex[:12],
        title=result.title,
        language=result.language,
        slides=slides,
        format=fmt.value,
        source=source,
    )
