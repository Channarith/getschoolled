"""Curriculum FastAPI app.

Loads lesson text into the RAG index at startup and serves retrieval for the
Tutor/Q&A agent. The corpus location is configurable via CURRICULUM_DIR so the
same code serves the bundled sample curriculum (local) or a mounted/object-store
corpus (cloud).
"""

from __future__ import annotations

import os
from pathlib import Path

from aoep_shared.rag import RagIndex
from aoep_shared.service import create_service
from fastapi import Body, HTTPException
from pydantic import BaseModel

from .decks import Deck, DeckStore, SlideSpec, parse_deck_text

app = create_service("curriculum")
app.state.decks = DeckStore()


def _curriculum_dir() -> Path:
    env = os.environ.get("CURRICULUM_DIR")
    if env:
        return Path(env)
    # repo_root/services/curriculum/src/curriculum/main.py -> repo_root
    return Path(__file__).resolve().parents[4] / "sample-curriculum"


app.state.index = RagIndex.from_directory(_curriculum_dir())


class SearchResult(BaseModel):
    doc_id: str
    title: str
    score: float
    excerpt: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


@app.get("/curriculum/count")
def count() -> dict:
    return {"documents": len(app.state.index)}


@app.get("/curriculum/search", response_model=SearchResponse)
def search(q: str, top_k: int = 3) -> SearchResponse:
    hits = app.state.index.retrieve(q, top_k=top_k)
    results = [
        SearchResult(
            doc_id=h.document.doc_id,
            title=h.document.title,
            score=round(h.score, 4),
            excerpt=h.document.text[:200],
        )
        for h in hits
    ]
    return SearchResponse(query=q, results=results)


# --------------------------------------------------------------------------- #
# Phase 6 - CMS: deck authoring / import / management
# --------------------------------------------------------------------------- #
class CreateDeckRequest(BaseModel):
    title: str
    language: str = "en"
    slides: list[SlideSpec] = []


class DeckSummary(BaseModel):
    deck_id: str
    title: str
    language: str
    slide_count: int


def _summary(deck: Deck) -> DeckSummary:
    return DeckSummary(
        deck_id=deck.deck_id,
        title=deck.title,
        language=deck.language,
        slide_count=len(deck.slides),
    )


@app.post("/decks", response_model=Deck)
def create_deck(req: CreateDeckRequest) -> Deck:
    return app.state.decks.create(req.title, req.language, req.slides)


@app.post("/decks/import", response_model=Deck)
def import_deck(text: str = Body(..., media_type="text/plain")) -> Deck:
    """Import a deck from the plain-text lesson format."""
    deck = parse_deck_text(text)
    if not deck.slides:
        raise HTTPException(status_code=422, detail="no slides parsed from import")
    return app.state.decks.add(deck)


@app.get("/decks", response_model=list[DeckSummary])
def list_decks() -> list[DeckSummary]:
    return [_summary(d) for d in app.state.decks.list()]


@app.get("/decks/{deck_id}", response_model=Deck)
def get_deck(deck_id: str) -> Deck:
    deck = app.state.decks.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="unknown deck")
    return deck


@app.get("/decks/{deck_id}/presentation")
def presentation(deck_id: str) -> dict:
    """Ordered slide payload for the presentation pipeline / live class."""
    deck = app.state.decks.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="unknown deck")
    return {
        "deck_id": deck.deck_id,
        "title": deck.title,
        "language": deck.language,
        "slides": [
            {"index": i, **s.model_dump()} for i, s in enumerate(deck.slides)
        ],
    }


@app.delete("/decks/{deck_id}")
def delete_deck(deck_id: str) -> dict:
    if not app.state.decks.delete(deck_id):
        raise HTTPException(status_code=404, detail="unknown deck")
    return {"deleted": deck_id}
