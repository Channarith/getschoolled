"""Curriculum FastAPI app.

Loads lesson text into the RAG index at startup and serves retrieval for the
Tutor/Q&A agent. The corpus location is configurable via CURRICULUM_DIR so the
same code serves the bundled sample curriculum (local) or a mounted/object-store
corpus (cloud).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from aoep_shared.rag import RagIndex
from aoep_shared.scene import (
    ExtractedObject,
    Layer,
    Scene,
    SceneDelta,
    SignedScene,
    TimeRange,
    Transform,
    apply_delta,
    extract_region,
    sign_scene,
    verify_scene,
)
from aoep_shared.homework import (
    Assignment,
    assignment_from_slides,
    detect_authorship,
    grade_submission,
    ocr_to_submission,
    segment_answers,
)
from aoep_shared.homework import Assignment as HomeworkAssignment
from aoep_shared.provenance import (
    SignedManifest,
    build_manifest,
    sha256_hex,
    sign_manifest,
    verify_against_content,
    verify_manifest,
)
from aoep_shared.service import create_service
from aoep_shared.validation import (
    Claim,
    extract_claims,
    validate_claim,
    validate_course,
)
from fastapi import Body, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from aoep_shared.internal_auth import require_internal

from aoep_shared.corrections import (
    Correction,
    CorrectionStatus,
    TargetKind,
    correction_to_training_example,
    parse_bulk,
)

from .catalog import CatalogStore, Course, DeliveryMode, Module, Program
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
app.state.scenes = {}
app.state.catalog = CatalogStore(path=os.environ.get("CATALOG_PATH") or None)
app.state.corrections = {}  # id -> Correction (review queue)

# Human-in-the-loop co-grading (Phase 12): a review queue for AI-proposed grades.
from aoep_shared.hil import (  # noqa: E402
    AutonomyLevel,
    ReviewItem,
    ReviewKind,
    ReviewQueue,
    ReviewStatus,
    should_escalate,
)
from aoep_shared.optimization import OptimizationLedger  # noqa: E402

app.state.grade_reviews = ReviewQueue()
app.state.grade_optimization = OptimizationLedger()
try:
    app.state.autonomy = AutonomyLevel(os.environ.get("HIL_AUTONOMY", "autonomous"))
except ValueError:
    app.state.autonomy = AutonomyLevel.AUTONOMOUS


def _signing_key() -> bytes:
    return os.environ.get("SCENE_SIGNING_KEY", "dev-scene-signing-key").encode()


def _provenance_key() -> bytes:
    return os.environ.get(
        "PROVENANCE_SIGNING_KEY", os.environ.get("SCENE_SIGNING_KEY", "dev-provenance-key")
    ).encode()


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


# --------------------------------------------------------------------------- #
# Course catalog + dynamic training programs
# --------------------------------------------------------------------------- #
class CreateCourseRequest(BaseModel):
    title: str
    subject: str = "general"
    language: str = "en"
    description: str = ""
    modules: list[Module] = []
    human_of_record: str | None = None
    reviewed_by: str | None = None
    delivery_mode: DeliveryMode = DeliveryMode.AI
    category: str = ""
    tags: list[str] = []
    audio_language: str = ""
    media_format: str = "video"
    level: str = "beginner"
    duration_min: int = 0
    hands_on: bool = False
    preview: str = ""
    access_tier: str = "free"
    price_usd: float = 0.0
    thumbnail: str | None = None
    maturity_rating: str = "all"
    subtitle_languages: list[str] = []
    hls_url: str | None = None
    dash_url: str | None = None
    trailer_url: str | None = None
    audiences: list[str] = []
    core_skill: bool = False


@app.post("/courses", response_model=Course)
def create_course(req: CreateCourseRequest) -> Course:
    return app.state.catalog.create_course(Course(**req.model_dump()))


@app.get("/courses", response_model=list[Course])
def list_courses() -> list[Course]:
    return app.state.catalog.list_courses()


@app.get("/courses/search", response_model=list[Course])
def search_courses(
    q: str | None = None,
    category: str | None = None,
    language: str | None = None,
    audio: str | None = None,
    media_format: str | None = None,
    level: str | None = None,
    tag: str | None = None,
    hands_on: bool | None = None,
    delivery_mode: str | None = None,
    access_tier: str | None = None,
    maturity: str | None = None,
    audience: str | None = None,
    core_skill: bool | None = None,
    source: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Course]:
    """Unified faceted search across catalog, audio, live lessons, languages, games."""
    return _search_learnable_as_courses(
        q=q, category=category, language=language, audio=audio,
        media_format=media_format, level=level, tag=tag, hands_on=hands_on,
        access_tier=access_tier, maturity=maturity, audience=audience,
        core_skill=core_skill, source=source, limit=limit, offset=offset,
    )


def _learnable_index(locale: str = "en"):
    from curriculum.learnable_service import build_index_for_store

    return build_index_for_store(app.state.catalog, locale=locale)


def _search_learnable_as_courses(**kwargs) -> list[Course]:
    from aoep_shared.learnable import search_learnable

    limit = int(kwargs.pop("limit", 100))
    offset = int(kwargs.pop("offset", 0))
    audio = kwargs.pop("audio", None)
    media_format = kwargs.pop("media_format", None)
    result = search_learnable(
        _learnable_index(),
        q=kwargs.get("q"),
        category=kwargs.get("category"),
        language=kwargs.get("language"),
        audio_language=audio,
        format=media_format,
        level=kwargs.get("level"),
        tag=kwargs.get("tag"),
        hands_on=kwargs.get("hands_on"),
        maturity=kwargs.get("maturity"),
        audience=kwargs.get("audience"),
        core_skill=kwargs.get("core_skill"),
        source=kwargs.get("source"),
        offset=offset,
        limit=limit,
    )
    return [_course_from_learnable_item(i) for i in result["items"]]


def _course_from_learnable_item(item) -> Course:
    from aoep_shared.learnable.index import _item_as_catalog_dict

    data = _item_as_catalog_dict(item)
    return Course(
        course_id=data["course_id"],
        title=data["title"],
        subject=data["subject"],
        category=data["category"],
        language=data["language"],
        audio_language=data["audio_language"],
        media_format=data["media_format"],
        level=data["level"],
        duration_min=data["duration_min"],
        hands_on=data["hands_on"],
        preview=data["preview"],
        description=data["description"],
        tags=data["tags"],
        access_tier=data["access_tier"],
        delivery_mode=DeliveryMode.AI,
        maturity_rating=data["maturity_rating"],
        popularity=data.get("popularity", 0),
        source=data.get("source", ""),
        deep_link=data.get("deep_link", ""),
        global_id=data.get("global_id", ""),
    )


def _catalog_dicts() -> list[dict]:
    from aoep_shared.learnable import learnable_catalog_dicts

    return learnable_catalog_dicts(_learnable_index())


def _course_relevance_dict(course) -> dict:
    from aoep_shared.skills_taxonomy import course_relevance

    return course_relevance({
        "course_id": course.course_id, "title": course.title, "subject": course.subject,
        "category": course.category, "tags": course.tags,
        "audiences": course.audiences, "core_skill": course.core_skill})


@app.get("/skills/professions")
def skills_professions() -> dict:
    """Professions + the subjects that feed each (for audience facets/discovery)."""
    from aoep_shared.skills_taxonomy import professions_catalog

    return {"professions": professions_catalog()}


@app.get("/courses/{course_id}/relevance")
def course_relevance_ep(course_id: str) -> dict:
    course = app.state.catalog.get_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="unknown course")
    return {"course_id": course_id, **_course_relevance_dict(course)}


class ParseJobRequest(BaseModel):
    description: str


@app.post("/jobs/parse")
def jobs_parse(req: ParseJobRequest) -> dict:
    """Parse a pasted job description -> skills, certifications, matched courses,
    and targeted specialized/certification classes (e.g. Cisco UCSM)."""
    from aoep_shared.jobs import recommend_from_description

    return recommend_from_description(req.description, _catalog_dicts())


@app.get("/jobs")
def jobs_list(q: str | None = None, location: str | None = None, limit: int = 50) -> dict:
    """Open roles from the job market (LinkedIn/other via provider; sample offline)."""
    from aoep_shared.jobs import get_jobs_provider

    provider = get_jobs_provider()
    try:
        postings = provider.search(query=q or "", location=location or "", limit=limit)
    except NotImplementedError:
        # Real provider configured but unreachable here -> fall back to the sample board.
        from aoep_shared.jobs import MockJobsProvider
        postings = MockJobsProvider().search(query=q or "", location=location or "", limit=limit)
        provider = MockJobsProvider()
    return {"source": provider.source, "count": len(postings),
            "jobs": [j.model_dump() for j in postings]}


@app.get("/jobs/{job_id}")
def job_detail(job_id: str) -> dict:
    """A job + the catalog courses that cover its skills (coverage %, gap, path)."""
    from aoep_shared.jobs import get_job, match_courses_to_job

    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    m = match_courses_to_job(job, _catalog_dicts())
    return m.model_dump()


@app.get("/courses/{course_id}/jobs")
def course_related_jobs(course_id: str) -> dict:
    """Open roles whose required skills this course helps with."""
    from aoep_shared.jobs import SAMPLE_JOBS, jobs_for_course

    course = app.state.catalog.get_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="unknown course")
    cdict = {"course_id": course.course_id, "title": course.title,
             "subject": course.subject, "category": course.category, "tags": course.tags}
    rel = jobs_for_course(cdict, SAMPLE_JOBS)
    return {"course_id": course_id, "jobs": [
        {"job": r["job"].model_dump(), "relevant_skills": r["relevant_skills"]} for r in rel]}


@app.get("/audio/categories")
def audio_categories(locale: str = "en") -> dict:
    """List categories with localized labels.

    ``locale`` selects the UI language; categories are translated into
    13 locales (en, es, fr, de, it, pt, ru, ar, hi, zh, ja, ko, vi) and
    fall back to English otherwise. Each row carries both ``category``
    (the localized display label) and ``category_id`` (the canonical
    English identifier you pass back to ``/audio/courses?category=``).
    """
    from aoep_shared.audio_courses import categories

    return {"categories": categories(locale=locale), "locale": locale}


@app.get("/audio/courses")
def audio_courses(category: str | None = None, q: str | None = None,
                  max_minutes: int | None = None, offset: int = 0,
                  limit: int = 50, locale: str = "en",
                  training_locale: str | None = None) -> dict:
    """Audio-only, drive-safe classes for hands-free learning.

    ``locale`` localizes category/level labels and segment headings.
    ``training_locale`` (en/es/zh) localizes spoken lesson bodies for TTS;
    defaults from ``locale`` when omitted.
    """
    from aoep_shared.audio_courses import list_courses

    return list_courses(category=category, q=q, max_minutes=max_minutes,
                        offset=max(0, offset), limit=max(1, min(limit, 100)),
                        locale=locale, training_locale=training_locale)


@app.get("/audio/courses/{course_id}")
def audio_course(course_id: str, locale: str = "en",
                 training_locale: str | None = None) -> dict:
    """Full course (with every segment) in the requested locale."""
    from aoep_shared.audio_courses import get_course
    from aoep_shared.training_content_i18n import normalize_training_locale

    tloc = normalize_training_locale(training_locale or locale)
    c = get_course(course_id, locale=locale, training_locale=tloc)
    if c is None:
        raise HTTPException(status_code=404, detail="unknown audio course")
    out = c.model_dump()
    out["locale"] = locale
    out["training_locale"] = tloc
    return out


@app.get("/home")
def home_feed(kids: bool = False, per_rail: int = 12, locale: str = "en") -> dict:
    """Netflix-style home feed from the unified learnable index."""
    from aoep_shared.learnable import learnable_home_rails

    return {
        "rails": learnable_home_rails(
            _learnable_index(locale=locale), kids_only=kids, per_rail=per_rail,
        ),
        "locale": locale,
    }


@app.get("/learn/search")
def learn_search(
    q: str | None = None,
    category: str | None = None,
    source: str | None = None,
    format: str | None = None,
    level: str | None = None,
    language: str | None = None,
    maturity: str | None = None,
    hands_on: bool | None = None,
    tag: str | None = None,
    audience: str | None = None,
    core_skill: bool | None = None,
    kids: bool = False,
    limit: int = 50,
    offset: int = 0,
    locale: str = "en",
) -> dict:
    """Search all learnable content (catalog, audio, live, languages, games)."""
    from aoep_shared.course_artwork import resolve_course_poster_from_mapping
    from aoep_shared.learnable import search_learnable

    result = search_learnable(
        _learnable_index(locale=locale),
        q=q, category=category, source=source, format=format, level=level,
        language=language, maturity=maturity, hands_on=hands_on, tag=tag,
        audience=audience, core_skill=core_skill, kids_only=kids,
        offset=offset, limit=limit,
    )
    return {
        **result,
        "items": [
            {
                **i.model_dump(),
                "thumbnail": resolve_course_poster_from_mapping({
                    **i.model_dump(),
                    "format": i.format,
                }),
            }
            for i in result["items"]
        ],
    }


@app.get("/learn/facets")
def learn_facets() -> dict:
    from aoep_shared.learnable import learnable_facets

    return learnable_facets(_learnable_index())


@app.get("/learn/home")
def learn_home(kids: bool = False, per_rail: int = 12, locale: str = "en") -> dict:
    from aoep_shared.learnable import learnable_home_rails

    return {
        "rails": learnable_home_rails(
            _learnable_index(locale=locale), kids_only=kids, per_rail=per_rail,
        ),
        "locale": locale,
    }


@app.get("/learn/items/{global_id}")
def learn_item(global_id: str) -> dict:
    from curriculum.learnable_service import find_item

    item = find_item(_learnable_index(), global_id=global_id)
    if item is None:
        raise HTTPException(status_code=404, detail="unknown learnable item")
    return item.model_dump()


@app.get("/notifications/feed")
def notifications_feed(
    student_id: str = "guest",
    interests: str | None = None,
    in_progress: str | None = None,
    completed: str | None = None,
    streak_days: int = 0,
    limit: int = 30,
    locale: str = "en",
) -> dict:
    """Personalized notification feed for the mobile/web inbox.

    ``interests`` / ``in_progress`` / ``completed`` are comma-separated strings;
    the mobile app reads its locally-tracked state (AsyncStorage) and passes it
    in so the server-rendered feed matches the device. ``locale`` selects the
    language of the rendered titles + bodies (defaults to English). The same
    items are also used by the client to schedule LOCAL push notifications via
    expo-notifications - no remote push server is required.
    """
    from aoep_shared.notifications import build_feed

    def _split(s: str | None) -> list[str]:
        return [p.strip() for p in (s or "").split(",") if p.strip()]

    feed = build_feed(
        student_id=student_id,
        interests=_split(interests),
        in_progress_course_ids=_split(in_progress),
        completed_course_ids=_split(completed),
        streak_days=max(0, streak_days),
        limit=max(1, min(limit, 100)),
        locale=(locale or "en").lower().split("-")[0],
    )
    return feed.model_dump()


@app.get("/notifications/locales")
def notifications_locales() -> dict:
    """List the language codes for which the notification feed is translated."""
    from aoep_shared.notifications import SUPPORTED_NOTIFICATION_LOCALES

    return {"locales": list(SUPPORTED_NOTIFICATION_LOCALES)}


@app.post("/courses/{course_id}/view")
def course_view(course_id: str) -> dict:
    """Record a view/open to feed the 'Popular now' rail."""
    c = app.state.catalog.bump_popularity(course_id)
    if c is None:
        raise HTTPException(status_code=404, detail="unknown course")
    return {"course_id": course_id, "popularity": c.popularity}


class RecommendRequest(BaseModel):
    student_id: str = "student"
    mastery: dict[str, float] = {}
    completed_course_ids: list[str] = []
    interests: list[str] = []
    top_n: int = 5


def _course_duration_min(course_id: str) -> int:
    """Resolve duration from catalog or the unified learnable index."""
    from curriculum.learnable_service import find_item

    course = app.state.catalog.get_course(course_id)
    if course is not None:
        return int(course.duration_min or 0)
    idx = _learnable_index()
    item = find_item(idx, global_id=course_id) or find_item(idx, source_id=course_id)
    if item is not None:
        return int(item.duration_min or 5)
    return 5


@app.post("/recommend")
def recommend(req: RecommendRequest) -> dict:
    """Foresight: suggest courses + gaps + adapted difficulty for a student.

    New / empty profiles get popular beginner starter picks (cold_start=true)
    instead of an error or empty list.
    """
    from aoep_shared.foresight import StudentProfile

    from .recommend_service import run_recommend

    courses = app.state.catalog.list_courses()
    profile = StudentProfile(
        student_id=req.student_id,
        mastery=req.mastery or {},
        completed_course_ids=req.completed_course_ids or [],
        interests=req.interests or [],
    )
    return run_recommend(profile, courses, top_n=req.top_n)


@app.get("/courses/{course_id}/ad-breaks")
def course_ad_breaks(course_id: str, tier: str = "free", format: str = "json"):
    """Ad-break schedule for playing a course (VMAP/VAST, tier-gated).

    Paid tiers (pro/premium) are ad-free. format=vmap returns IAB VMAP XML.
    """
    from aoep_shared.ads import AD_FREE_TIERS, ad_plan_for, build_vmap

    # Existence check must be independent of duration (which defaults to a
    # positive value for unknown ids), so unknown courses still 404.
    if app.state.catalog.get_course(course_id) is None:
        from curriculum.learnable_service import find_item

        idx = _learnable_index()
        if find_item(idx, global_id=course_id) is None and (
            find_item(idx, source_id=course_id) is None
        ):
            raise HTTPException(status_code=404, detail="course not found")

    duration = _course_duration_min(course_id)
    breaks = ad_plan_for(tier, duration_min=max(1, duration))
    if format == "vmap":
        from fastapi import Response

        return Response(content=build_vmap(breaks), media_type="application/xml")
    return {
        "course_id": course_id,
        "tier": tier,
        "ad_free": (tier or "free").lower() in AD_FREE_TIERS,
        "breaks": [b.model_dump(mode="json") for b in breaks],
    }


@app.get("/catalog/export", dependencies=[Depends(require_internal)])
def catalog_export(format: str = "json"):
    """Acquisition-ready catalog export (Netflix-compatible interchange).

    format=json -> a portable content feed; format=mrss -> Media RSS (XML).
    Gated by require_internal because the full catalog dump is a
    partner-facing artifact, not a public endpoint.
    """
    from fastapi import Response

    from .interchange import catalog_json_feed, catalog_mrss

    courses = app.state.catalog.list_courses()
    if format == "mrss":
        return Response(content=catalog_mrss(courses), media_type="application/rss+xml")
    return catalog_json_feed(courses)


@app.get("/courses/facets")
def course_facets() -> dict:
    """Distinct facet values from the unified learnable index."""
    from aoep_shared.learnable import learnable_facets

    facets = learnable_facets(_learnable_index())
    facets.setdefault("media_formats", facets.get("formats", []))
    return facets


def _course_audiences_facet(courses) -> list[dict]:
    from aoep_shared.skills_taxonomy import PROFESSIONS, course_relevance

    seen: set[str] = set()
    for c in courses:
        rel = course_relevance({"title": c.title, "subject": c.subject,
                                "category": c.category, "tags": c.tags,
                                "audiences": c.audiences, "core_skill": c.core_skill})
        seen |= set(rel["audiences"])
    return sorted(({"slug": s, "label": PROFESSIONS.get(s, s.title())} for s in seen),
                  key=lambda x: x["label"])


@app.get("/courses/{course_id}", response_model=Course)
def get_course(course_id: str) -> Course:
    from curriculum.learnable_service import find_item

    course = app.state.catalog.get_course(course_id)
    if course is not None:
        return course
    item = find_item(_learnable_index(), source_id=course_id)
    if item is None:
        raise HTTPException(status_code=404, detail="unknown course")
    return _course_from_learnable_item(item)


@app.delete("/courses/{course_id}")
def delete_course(course_id: str) -> dict:
    if not app.state.catalog.delete_course(course_id):
        raise HTTPException(status_code=404, detail="unknown course")
    return {"deleted": course_id}


class CreateProgramRequest(BaseModel):
    title: str
    audience: str = ""
    description: str = ""
    course_ids: list[str] = []
    adaptive_rules: dict = {}
    delivery_mode: DeliveryMode = DeliveryMode.AI


@app.post("/programs", response_model=Program)
def create_program(req: CreateProgramRequest) -> Program:
    return app.state.catalog.create_program(Program(**req.model_dump()))


@app.get("/programs", response_model=list[Program])
def list_programs(audience: str | None = None) -> list[Program]:
    progs = app.state.catalog.list_programs()
    if audience:
        progs = [p for p in progs if audience.lower() in (p.audience or "").lower()]
    return progs


@app.get("/programs/{program_id}", response_model=Program)
def get_program(program_id: str) -> Program:
    program = app.state.catalog.get_program(program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="unknown program")
    return program


@app.delete("/programs/{program_id}")
def delete_program(program_id: str) -> dict:
    if not app.state.catalog.delete_program(program_id):
        raise HTTPException(status_code=404, detail="unknown program")
    return {"deleted": program_id}


@app.get("/catalog")
def catalog_tree(delivery_mode: str | None = None) -> dict:
    cat = app.state.catalog
    courses = cat.list_courses()
    programs = cat.list_programs()
    if delivery_mode:
        courses = [c for c in courses if c.delivery_mode.value == delivery_mode]
        programs = [p for p in programs if p.delivery_mode.value == delivery_mode]
    return {
        "courses": [
            {"course_id": c.course_id, "title": c.title, "subject": c.subject,
             "modules": len(c.modules), "validation_status": c.validation_status,
             "delivery_mode": c.delivery_mode.value, "human_of_record": c.human_of_record}
            for c in courses
        ],
        "programs": [
            {"program_id": p.program_id, "title": p.title, "audience": p.audience,
             "courses": len(p.course_ids), "delivery_mode": p.delivery_mode.value}
            for p in programs
        ],
    }


# --------------------------------------------------------------------------- #
# Model cards (Trust layer, Phase 5) - transparency about the served model
# --------------------------------------------------------------------------- #
@app.get("/model-cards")
def model_cards() -> dict:
    """List generated model cards (JSON) from MODEL_CARDS_DIR, if any."""
    cards = []
    cards_dir = os.environ.get("MODEL_CARDS_DIR")
    if cards_dir and os.path.isdir(cards_dir):
        for name in sorted(os.listdir(cards_dir)):
            if name.endswith(".json"):
                try:
                    with open(os.path.join(cards_dir, name), "r", encoding="utf-8") as fh:
                        cards.append(json.load(fh))
                except (OSError, json.JSONDecodeError):
                    continue
    return {"model_cards": cards}


class PlanRequest(BaseModel):
    # Per-course mastery (0..1), e.g. from the memory service mastery graph.
    mastery: dict[str, float] = {}


@app.post("/programs/{program_id}/plan")
def program_plan(program_id: str, req: PlanRequest) -> dict:
    """Order a program's courses and gate each by its prerequisite-mastery rule.

    A course with a `prereq_mastery` threshold is unlocked only once every
    preceding course in the sequence is mastered at/above that threshold.
    """
    program = app.state.catalog.get_program(program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="unknown program")
    prereq_rules = program.adaptive_rules.get("prereq_mastery", {})
    plan = []
    for idx, cid in enumerate(program.course_ids):
        course = app.state.catalog.get_course(cid)
        threshold = prereq_rules.get(cid)
        unlocked, reason = True, ""
        if threshold is not None:
            preceding = program.course_ids[:idx]
            unlocked = all(req.mastery.get(p, 0.0) >= threshold for p in preceding)
            if not unlocked:
                reason = f"prior courses must be mastered >= {threshold}"
        plan.append({
            "course_id": cid,
            "title": course.title if course else None,
            "unlocked": unlocked,
            "reason": reason,
        })
    next_course = next((c["course_id"] for c in plan if c["unlocked"]), None)
    return {"program_id": program_id, "next_course": next_course, "plan": plan}


# --------------------------------------------------------------------------- #
# Corrections review queue (single + bulk entry; approve/reject)
# --------------------------------------------------------------------------- #
class CreateCorrectionRequest(BaseModel):
    target_kind: TargetKind = TargetKind.COURSE
    target_id: str = ""
    locator: str = ""
    original: str = ""
    corrected: str
    rationale: str = ""
    author: str = ""
    audience: dict = {}


@app.post("/corrections", response_model=Correction)
def submit_correction(req: CreateCorrectionRequest) -> Correction:
    c = Correction(**req.model_dump())
    app.state.corrections[c.id] = c
    return c


class ReportIssueRequest(BaseModel):
    """Learner-facing 'report / dispute' that opens a Correction for human review."""
    target_kind: TargetKind = TargetKind.CLAIM
    target_id: str = ""
    locator: str = ""          # the disputed answer / slide / claim text
    issue: str                  # what the learner thinks is wrong
    suggested: str = ""         # optional suggested correction
    author: str = ""


@app.post("/report", response_model=Correction)
def report_issue(req: ReportIssueRequest) -> Correction:
    """Open a dispute -> a SUBMITTED correction routed to a human reviewer."""
    c = Correction(
        target_kind=req.target_kind,
        target_id=req.target_id,
        locator=req.locator,
        original=req.locator,
        corrected=req.suggested,
        rationale=req.issue,
        author=req.author,
        status=CorrectionStatus.SUBMITTED,
    )
    app.state.corrections[c.id] = c
    return c


@app.post("/corrections/bulk", dependencies=[Depends(require_internal)])
async def bulk_corrections(
    file: UploadFile = File(...), fmt: str = Form("jsonl")
) -> dict:
    data = (await file.read()).decode("utf-8")
    try:
        items = parse_bulk(data, fmt)
    except (ValueError, Exception) as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"could not parse bulk: {exc}")
    for c in items:
        app.state.corrections[c.id] = c
    return {"count": len(items), "ids": [c.id for c in items]}


@app.get("/corrections", response_model=list[Correction])
def list_corrections(status: str | None = None) -> list[Correction]:
    items = list(app.state.corrections.values())
    if status:
        items = [c for c in items if c.status.value == status]
    return items


@app.get("/corrections/{correction_id}", response_model=Correction)
def get_correction(correction_id: str) -> Correction:
    c = app.state.corrections.get(correction_id)
    if c is None:
        raise HTTPException(status_code=404, detail="unknown correction")
    return c


def _set_status(correction_id: str, status: CorrectionStatus) -> Correction:
    c = app.state.corrections.get(correction_id)
    if c is None:
        raise HTTPException(status_code=404, detail="unknown correction")
    c.status = status
    return c


@app.post("/corrections/{correction_id}/approve", response_model=Correction,
          dependencies=[Depends(require_internal)])
def approve_correction(correction_id: str) -> Correction:
    return _set_status(correction_id, CorrectionStatus.APPROVED)


@app.post("/corrections/{correction_id}/reject", response_model=Correction,
          dependencies=[Depends(require_internal)])
def reject_correction(correction_id: str) -> Correction:
    return _set_status(correction_id, CorrectionStatus.REJECTED)


@app.post("/corrections/{correction_id}/apply",
          dependencies=[Depends(require_internal)])
def apply_correction(correction_id: str) -> dict:
    """Back-propagate an APPROVED correction.

    course/deck -> patch the referenced deck slide; scene -> patch the layer
    text; model/claim -> append a gold (reward=+1) training example to the
    corrections JSONL the trainer merges. Sets status=applied.
    """
    c = app.state.corrections.get(correction_id)
    if c is None:
        raise HTTPException(status_code=404, detail="unknown correction")
    if c.status != CorrectionStatus.APPROVED:
        raise HTTPException(status_code=409, detail="correction must be approved before apply")

    if c.target_kind in (TargetKind.COURSE, TargetKind.DECK):
        deck = app.state.decks.get(c.target_id)
        if deck is None:
            raise HTTPException(status_code=422, detail="unknown deck for correction")
        if not c.locator.isdigit() or int(c.locator) >= len(deck.slides):
            raise HTTPException(status_code=422, detail="locator must be a valid slide index")
        idx = int(c.locator)
        deck.slides[idx].body = c.corrected
        result = {"patched": "deck", "deck_id": c.target_id, "slide": idx}
    elif c.target_kind is TargetKind.SCENE:
        scene = app.state.scenes.get(c.target_id)
        if scene is None:
            raise HTTPException(status_code=422, detail="unknown scene for correction")
        layer = scene.get_layer(c.locator)
        if layer is None:
            raise HTTPException(status_code=422, detail="unknown layer for correction")
        layer.text = c.corrected
        result = {"patched": "scene", "scene_id": c.target_id, "layer": c.locator}
    else:  # MODEL or CLAIM -> gold training example
        example = correction_to_training_example(c)
        path = os.environ.get("CORRECTIONS_JSONL", "training/data/corrections.jsonl")
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(example, ensure_ascii=False) + "\n")
        result = {"emitted": "training_example", "path": path}

    c.status = CorrectionStatus.APPLIED
    return {"applied": True, "correction_id": correction_id, **result}


# --------------------------------------------------------------------------- #
# Course validation (multi-engine web corroboration)
# --------------------------------------------------------------------------- #
class ValidateClaimRequest(BaseModel):
    text: str
    max_results: int = 5


def _verdict_dict(v) -> dict:
    return {
        "claim": v.claim,
        "status": v.status,
        "confidence": v.confidence,
        "engines_consulted": v.engines_consulted,
        "citations": [
            {"title": c.title, "url": c.url, "snippet": c.snippet,
             "engine": c.engine, "overlap": c.overlap}
            for c in v.citations
        ],
    }


@app.post("/validate/claim")
def validate_claim_endpoint(req: ValidateClaimRequest) -> dict:
    engines = app.state.factory.search_engines()
    return _verdict_dict(validate_claim(req.text, engines, max_results=req.max_results))


@app.post("/decks/{deck_id}/validate")
def validate_deck_endpoint(deck_id: str) -> dict:
    deck = app.state.decks.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="unknown deck")
    engines = app.state.factory.search_engines()
    claims: list[Claim] = []
    for slide in deck.slides:
        claims.extend(extract_claims(slide.body, topic=slide.title))
    report = validate_course(claims, engines)
    return {
        "deck_id": deck_id,
        "engines": [getattr(e, "engine", "search") for e in engines],
        "total": report.total,
        "supported": report.supported,
        "unverified": report.unverified,
        "contradicted": report.contradicted,
        "flagged": [_verdict_dict(v) for v in report.flagged],
        "verdicts": [_verdict_dict(v) for v in report.verdicts],
    }


# --------------------------------------------------------------------------- #
# AOEPLX layered scene format (live broadcast content)
# --------------------------------------------------------------------------- #
class CreateSceneRequest(BaseModel):
    title: str = ""
    width: int = 1280
    height: int = 720
    layers: list[Layer] = []


@app.post("/scenes", response_model=Scene)
def create_scene(req: CreateSceneRequest) -> Scene:
    scene = Scene(title=req.title, width=req.width, height=req.height, layers=req.layers)
    app.state.scenes[scene.id] = scene
    return scene


@app.get("/scenes/{scene_id}", response_model=Scene)
def get_scene(scene_id: str) -> Scene:
    scene = app.state.scenes.get(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="unknown scene")
    return scene


@app.post("/scenes/{scene_id}/delta", response_model=Scene)
def scene_delta(scene_id: str, delta: SceneDelta) -> Scene:
    scene = app.state.scenes.get(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="unknown scene")
    try:
        return apply_delta(scene, delta)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class ExtractRequest(BaseModel):
    bbox: Transform | None = None
    layer_ids: list[str] | None = None
    time: TimeRange | None = None
    title: str = ""


@app.post("/scenes/{scene_id}/extract", response_model=ExtractedObject)
def scene_extract(scene_id: str, req: ExtractRequest) -> ExtractedObject:
    scene = app.state.scenes.get(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="unknown scene")
    obj = extract_region(
        scene, bbox=req.bbox, layer_ids=req.layer_ids, time=req.time, title=req.title
    )
    # The extracted multilayer object is itself a reusable scene.
    app.state.scenes[obj.scene.id] = obj.scene
    return obj


@app.post("/scenes/{scene_id}/sign", response_model=SignedScene)
def scene_sign(scene_id: str) -> SignedScene:
    scene = app.state.scenes.get(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="unknown scene")
    return sign_scene(scene, _signing_key())


@app.post("/scenes/verify")
def scene_verify(signed: SignedScene) -> dict:
    return {"valid": verify_scene(signed, _signing_key())}


# --------------------------------------------------------------------------- #
# Homework subtool - generation (Phase 6)
# --------------------------------------------------------------------------- #
class GenerateHomeworkRequest(BaseModel):
    deck_id: str | None = None
    course_id: str | None = None
    title: str = "Homework"
    subject: str = "general"
    num_questions: int = 4
    locale: str = "en"


class GradeHomeworkRequest(BaseModel):
    assignment: dict
    answers: list[str] = []
    submission_text: str | None = None
    handwritten: bool = False
    deck_id: str | None = None
    course_id: str | None = None
    subject: str | None = None


def _context_passages(deck_id: str | None, course_id: str | None) -> list[str]:
    passages: list[str] = []
    decks = []
    if deck_id and (d := app.state.decks.get(deck_id)):
        decks = [d]
    elif course_id and (course := app.state.catalog.get_course(course_id)):
        decks = [app.state.decks.get(m.deck_id) for m in course.modules if m.deck_id]
    for d in decks:
        if d:
            passages.extend(f"{s.title}: {s.body}" for s in d.slides)
    return passages


@app.post("/homework/grade", dependencies=[Depends(require_internal)])
def homework_grade(req: GradeHomeworkRequest) -> dict:
    """Autograde a submission against an assignment (Phase 9).

    INTERNAL-ONLY. This endpoint is called by the AI agentic teacher
    (orchestrator / agent-runtime) when a student turns in homework -
    it must never be reachable from a student client, because then the
    student could grade their own paper. Gated by require_internal:
    pass a valid X-Internal-Token header signed with INTERNAL_TOKEN_KEY
    (or set INTERNAL_TOKEN for local dev).
    """
    assignment = HomeworkAssignment(**req.assignment)
    answers = req.answers
    if req.submission_text:
        answers = segment_answers(req.submission_text)
    joined = req.submission_text or " ".join(answers)
    authorship = detect_authorship(joined, handwritten=req.handwritten) if joined.strip() else None
    grade = grade_submission(
        assignment, answers,
        engines=app.state.factory.search_engines(),
        context_passages=_context_passages(req.deck_id, req.course_id),
        subject=req.subject,
        authorship=authorship,
    )
    result = {
        "score": grade.score, "max_score": grade.max_score, "percentage": grade.percentage,
        "validity_flags": grade.validity_flags, "authorship_label": grade.authorship_label,
        "items": [
            {"question_id": it.question_id, "type": it.type, "correct": it.correct,
             "score": it.score, "citations": it.citations, "rationale": it.rationale}
            for it in grade.items
        ],
        "pending_review": False, "review_id": None,
    }

    # HIL co-grading gate: route low-confidence / flagged grades to a human.
    conf = (grade.score / grade.max_score) if grade.max_score else 0.0
    flagged = bool(set(grade.validity_flags) & {"needs_human_review", "possible_ai_authorship"})
    if flagged or should_escalate(
        autonomy=app.state.autonomy, risk=round(1.0 - conf, 3), ai_confidence=round(conf, 3),
        subject=req.subject,
    ):
        item = app.state.grade_reviews.enqueue(ReviewItem(
            kind=ReviewKind.GRADE, subject=req.subject, ai_confidence=round(conf, 3),
            risk=round(1.0 - conf, 3), payload={**result, "assignment": req.assignment},
        ))
        result["pending_review"] = True
        result["review_id"] = item.id
    return result


# --------------------------------------------------------------------------- #
# HIL co-grading review queue (Phase 12)
# --------------------------------------------------------------------------- #
def _grade_review_dict(it) -> dict:
    return {"id": it.id, "kind": it.kind.value, "payload": it.payload,
            "ai_confidence": it.ai_confidence, "risk": it.risk, "subject": it.subject,
            "status": it.status.value, "final_payload": it.final_payload,
            "decided_by": it.decided_by}


@app.get("/homework/grade-reviews", dependencies=[Depends(require_internal)])
def grade_reviews(status: str | None = None) -> dict:
    """INTERNAL-ONLY. HIL review queue for low-confidence AI grades.
    Visible only to the teacher agent / human grader, never to students."""
    st = ReviewStatus(status) if status else None
    return {"autonomy": app.state.autonomy.value,
            "items": [_grade_review_dict(i) for i in app.state.grade_reviews.list(st)]}


class GradeReviewDecisionRequest(BaseModel):
    action: str                       # approve | edit | reject | takeover
    edited_payload: dict | None = None   # e.g. {"score": 2, "feedback": "...", "corrected": "..."}
    decided_by: str = "human"


@app.post("/homework/grade-reviews/{item_id}/decision",
          dependencies=[Depends(require_internal)])
def grade_review_decision(item_id: str, req: GradeReviewDecisionRequest) -> dict:
    """INTERNAL-ONLY. Decide on a queued grade review (approve / edit /
    reject / takeover). Locked behind the teacher-agent token."""
    try:
        item = app.state.grade_reviews.decide(
            item_id, req.action, edited_payload=req.edited_payload, decided_by=req.decided_by)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown grade review")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # A human override back-propagates: open a Correction (gold) + record an
    # optimization step so the grader improves over time.
    if item.status in (ReviewStatus.EDITED, ReviewStatus.TAKEN_OVER) and req.edited_payload:
        corrected = str(req.edited_payload.get("corrected") or req.edited_payload.get("feedback") or "")
        if corrected:
            c = Correction(
                target_kind=TargetKind.MODEL, target_id=item.id,
                locator=str(item.payload.get("assignment", {}).get("title", "homework grade")),
                corrected=corrected, rationale="human grading override (HIL)",
                author=req.decided_by, status=CorrectionStatus.APPROVED,
            )
            app.state.corrections[c.id] = c
        new_conf = float(req.edited_payload.get("score", item.ai_confidence))
        step = app.state.grade_optimization.commit(
            "grading", {"review_id": item.id}, {"accuracy": new_conf})
        app.state.grade_optimization.promote_if_better(step)
    return _grade_review_dict(item)


class AuthorshipRequest(BaseModel):
    text: str
    handwritten: bool = False


@app.post("/homework/authorship", dependencies=[Depends(require_internal)])
def homework_authorship(req: AuthorshipRequest) -> dict:
    """INTERNAL-ONLY. AI-vs-human authorship signal for a submission
    (Phase 8). Used by the teacher agent to decide whether to route a
    grade to a human; not exposed to student clients."""
    v = detect_authorship(req.text, handwritten=req.handwritten)
    return {"label": v.label, "ai_probability": v.ai_probability, "signals": v.signals,
            "note": "Probabilistic signal, not proof; borderline cases route to human review."}


@app.post("/homework/scan", dependencies=[Depends(require_internal)])
async def homework_scan(
    file: UploadFile = File(...), hint: str | None = Form(None), expected: int | None = Form(None)
) -> dict:
    """INTERNAL-ONLY. OCR a scanned/typed homework upload into a
    Submission (Phase 7). The OCR pipeline is gated so a student
    can't replay other students' uploads through it."""
    content = await file.read()
    ocr = app.state.factory.ocr()
    try:
        result = ocr.read(content, hint=hint)
    except (NotImplementedError, Exception) as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"OCR unavailable: {exc}")
    sub = ocr_to_submission(result, expected=expected)
    return sub.model_dump()


@app.post("/homework/generate", response_model=Assignment,
          dependencies=[Depends(require_internal)])
def homework_generate(req: GenerateHomeworkRequest) -> Assignment:
    """INTERNAL-ONLY. Build a new homework assignment from a deck or
    course. Called by the teacher agent during lesson planning; never
    by a student.
    """
    slides: list = []
    source = ""
    if req.deck_id:
        deck = app.state.decks.get(req.deck_id)
        if deck is None:
            raise HTTPException(status_code=404, detail="unknown deck")
        slides = deck.slides
        source = f"deck:{req.deck_id}"
    elif req.course_id:
        course = app.state.catalog.get_course(req.course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="unknown course")
        for m in course.modules:
            if m.deck_id and (deck := app.state.decks.get(m.deck_id)):
                slides.extend(deck.slides)
        source = f"course:{req.course_id}"
    else:
        raise HTTPException(status_code=422, detail="provide deck_id or course_id")
    if not slides:
        raise HTTPException(status_code=422, detail="no slide content to generate from")
    return assignment_from_slides(
        slides, title=req.title, subject=req.subject, source=source, locale=req.locale,
        num_questions=req.num_questions,
    )


# --------------------------------------------------------------------------- #
# Content credentials / provenance (Trust layer, Phase 2)
# --------------------------------------------------------------------------- #
class SignProvenanceRequest(BaseModel):
    artifact_id: str
    content: str
    ai_generated: bool = False
    model: str | None = None
    human_reviewed: bool = False
    reviewer: str | None = None
    sources: list[str] | None = None
    training_data_source: str | None = None


@app.post("/provenance/sign", response_model=SignedManifest,
          dependencies=[Depends(require_internal)])
def provenance_sign(req: SignProvenanceRequest) -> SignedManifest:
    manifest = build_manifest(
        req.artifact_id, req.content, ai_generated=req.ai_generated, model=req.model,
        human_reviewed=req.human_reviewed, reviewer=req.reviewer, sources=req.sources,
        training_data_source=req.training_data_source,
    )
    return sign_manifest(manifest, _provenance_key())


class VerifyProvenanceRequest(BaseModel):
    signed: SignedManifest
    content: str | None = None  # if given, also re-check the content hash


@app.post("/provenance/verify")
def provenance_verify(req: VerifyProvenanceRequest) -> dict:
    key = _provenance_key()
    if req.content is not None:
        valid = verify_against_content(req.signed, req.content, key)
        content_matches = sha256_hex(req.content) == req.signed.manifest.content_sha256
    else:
        valid = verify_manifest(req.signed, key)
        content_matches = None
    return {
        "valid": valid,
        "content_matches": content_matches,
        "artifact_id": req.signed.manifest.artifact_id,
        "assertions": [a.model_dump() for a in req.signed.manifest.assertions],
    }


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
