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
from fastapi import Body, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .decks import Deck, DeckStore, SlideSpec, parse_deck_text
from .ingest import (
    ClassFormat,
    TranscriptSegment,
    extract_html,
    extract_pdf,
    extract_transcript,
    sections_to_deck,
)

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


# --------------------------------------------------------------------------- #
# Content scraper: ingest sources -> generated decks (stored in the CMS)
# --------------------------------------------------------------------------- #
def _fmt(value: str) -> ClassFormat:
    try:
        return ClassFormat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"unknown class format {value!r}")


@app.post("/ingest/pdf", response_model=Deck)
async def ingest_pdf(
    file: UploadFile = File(...),
    title: str = Form("Untitled"),
    fmt: str = Form("lecture"),
) -> Deck:
    data = await file.read()
    try:
        result = extract_pdf(data, default_title=title)
    except Exception as exc:  # noqa: BLE001 - surface parse errors clearly
        raise HTTPException(status_code=422, detail=f"could not parse PDF: {exc}")
    if not result.sections:
        raise HTTPException(status_code=422, detail="no extractable text in PDF")
    deck = sections_to_deck(result, fmt=_fmt(fmt), source=file.filename or "pdf")
    return app.state.decks.add(deck)


class IngestHtmlRequest(BaseModel):
    html: str
    title: str = "Untitled"
    fmt: str = "article"


@app.post("/ingest/html", response_model=Deck)
def ingest_html(req: IngestHtmlRequest) -> Deck:
    result = extract_html(req.html, default_title=req.title)
    if not result.sections:
        raise HTTPException(status_code=422, detail="no extractable text in HTML")
    deck = sections_to_deck(result, fmt=_fmt(req.fmt), source="html")
    return app.state.decks.add(deck)


class IngestUrlRequest(BaseModel):
    url: str
    title: str = ""
    fmt: str = "article"


@app.post("/ingest/url", response_model=Deck)
def ingest_url(req: IngestUrlRequest) -> Deck:
    try:
        import requests  # lazy/runtime
    except ImportError:
        raise HTTPException(status_code=503, detail="requests not installed")
    try:
        resp = requests.get(req.url, timeout=15, headers={"User-Agent": "AOEP-scraper"})
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"fetch failed: {exc}")
    result = extract_html(resp.text, default_title=req.title or req.url)
    if not result.sections:
        raise HTTPException(status_code=422, detail="no extractable text at URL")
    deck = sections_to_deck(result, fmt=_fmt(req.fmt), source=req.url)
    return app.state.decks.add(deck)


class Segment(BaseModel):
    start: float
    text: str


class IngestTranscriptRequest(BaseModel):
    title: str = "Video"
    segments: list[Segment] = []
    fmt: str = "video"


@app.post("/ingest/transcript", response_model=Deck)
def ingest_transcript(req: IngestTranscriptRequest) -> Deck:
    segs = [TranscriptSegment(start=s.start, text=s.text) for s in req.segments]
    if not segs:
        raise HTTPException(status_code=422, detail="no transcript segments")
    result = extract_transcript(segs, title=req.title)
    deck = sections_to_deck(result, fmt=_fmt(req.fmt), source="transcript")
    return app.state.decks.add(deck)


class IngestYouTubeRequest(BaseModel):
    video_id: str
    title: str = ""
    fmt: str = "video"


@app.post("/ingest/youtube", response_model=Deck)
def ingest_youtube(req: IngestYouTubeRequest) -> Deck:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # lazy/runtime
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="youtube-transcript-api not installed (optional runtime dep)",
        )
    try:
        raw = YouTubeTranscriptApi.get_transcript(req.video_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"transcript fetch failed: {exc}")
    segs = [TranscriptSegment(start=float(r["start"]), text=r["text"]) for r in raw]
    result = extract_transcript(segs, title=req.title or req.video_id)
    deck = sections_to_deck(result, fmt=_fmt(req.fmt), source=f"youtube:{req.video_id}")
    return app.state.decks.add(deck)
