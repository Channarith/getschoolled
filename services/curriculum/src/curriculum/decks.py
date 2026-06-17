"""Phase 6 - curriculum CMS: deck authoring, import, and management.

A "deck" is an authored lesson: an ordered set of slides (title, body,
narration, optional media). Decks can be authored as structured data or imported
from the plain-text lesson format used by sample-curriculum/. Storage is an
in-memory store here (Postgres-backed in production); the model + import parser
are pure and fully testable.
"""

from __future__ import annotations

import re
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

_SLIDE_RE = re.compile(r"^SLIDE\s+(\d+)\s*\|\s*(.+)$")


class SlideSpec(BaseModel):
    title: str
    body: str = ""
    narration: str = ""
    media_url: Optional[str] = None


class Deck(BaseModel):
    deck_id: str
    title: str
    language: str = "en"
    slides: List[SlideSpec] = Field(default_factory=list)
    # Class genre/format (lecture, hands_on, tutorial, video, article) and where
    # the content was scraped from (filename / url / video id).
    format: str = "lecture"
    source: str = ""


def parse_deck_text(text: str, *, default_title: str = "Untitled") -> Deck:
    """Parse the plain-text lesson format into a Deck (import pipeline)."""
    title = default_title
    language = "en"
    slides: List[SlideSpec] = []
    cur: Optional[SlideSpec] = None
    body_lines: List[str] = []

    def flush() -> None:
        nonlocal cur, body_lines
        if cur is not None:
            cur.body = " ".join(" ".join(body_lines).split())
            if not cur.narration:
                cur.narration = cur.body
            slides.append(cur)
        cur = None
        body_lines = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("LESSON:"):
            title = line.split(":", 1)[1].strip()
            continue
        if line.startswith("LANGUAGE:"):
            language = line.split(":", 1)[1].strip()
            continue
        if line.startswith("NARRATION:"):
            if cur is not None:
                cur.narration = line.split(":", 1)[1].strip()
            continue
        if line.startswith("FACT:"):
            continue
        m = _SLIDE_RE.match(line)
        if m:
            flush()
            cur = SlideSpec(title=m.group(2).strip())
            continue
        if cur is not None:
            body_lines.append(line)
    flush()
    return Deck(deck_id=uuid.uuid4().hex[:12], title=title, language=language, slides=slides)


class DeckStore:
    """In-memory CRUD store for authored decks."""

    def __init__(self) -> None:
        self._decks: Dict[str, Deck] = {}

    def create(self, title: str, language: str, slides: List[SlideSpec]) -> Deck:
        deck = Deck(
            deck_id=uuid.uuid4().hex[:12],
            title=title,
            language=language,
            slides=list(slides),
        )
        self._decks[deck.deck_id] = deck
        return deck

    def add(self, deck: Deck) -> Deck:
        self._decks[deck.deck_id] = deck
        return deck

    def get(self, deck_id: str) -> Optional[Deck]:
        return self._decks.get(deck_id)

    def list(self) -> List[Deck]:
        return list(self._decks.values())

    def delete(self, deck_id: str) -> bool:
        return self._decks.pop(deck_id, None) is not None

    def update_slides(self, deck_id: str, slides: List[SlideSpec]) -> Optional[Deck]:
        deck = self._decks.get(deck_id)
        if deck is None:
            return None
        deck.slides = list(slides)
        return deck
