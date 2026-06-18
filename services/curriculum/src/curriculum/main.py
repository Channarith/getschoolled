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
    serialize,
    sign_scene,
    verify_scene,
)
from aoep_shared.homework import (
    Assignment,
    assignment_from_slides,
    detect_authorship,
    ocr_to_submission,
)
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
from fastapi import Body, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

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


@app.post("/courses", response_model=Course)
def create_course(req: CreateCourseRequest) -> Course:
    return app.state.catalog.create_course(Course(**req.model_dump()))


@app.get("/courses", response_model=list[Course])
def list_courses() -> list[Course]:
    return app.state.catalog.list_courses()


@app.get("/courses/{course_id}", response_model=Course)
def get_course(course_id: str) -> Course:
    course = app.state.catalog.get_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="unknown course")
    return course


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
def list_programs() -> list[Program]:
    return app.state.catalog.list_programs()


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


@app.post("/corrections/bulk")
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


@app.post("/corrections/{correction_id}/approve", response_model=Correction)
def approve_correction(correction_id: str) -> Correction:
    return _set_status(correction_id, CorrectionStatus.APPROVED)


@app.post("/corrections/{correction_id}/reject", response_model=Correction)
def reject_correction(correction_id: str) -> Correction:
    return _set_status(correction_id, CorrectionStatus.REJECTED)


@app.post("/corrections/{correction_id}/apply")
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


class AuthorshipRequest(BaseModel):
    text: str
    handwritten: bool = False


@app.post("/homework/authorship")
def homework_authorship(req: AuthorshipRequest) -> dict:
    """AI-vs-human authorship signal for a submission (Phase 8)."""
    v = detect_authorship(req.text, handwritten=req.handwritten)
    return {"label": v.label, "ai_probability": v.ai_probability, "signals": v.signals,
            "note": "Probabilistic signal, not proof; borderline cases route to human review."}


@app.post("/homework/scan")
async def homework_scan(
    file: UploadFile = File(...), hint: str | None = Form(None), expected: int | None = Form(None)
) -> dict:
    """OCR a scanned/typed homework upload into a Submission (Phase 7)."""
    content = await file.read()
    ocr = app.state.factory.ocr()
    try:
        result = ocr.read(content, hint=hint)
    except (NotImplementedError, Exception) as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"OCR unavailable: {exc}")
    sub = ocr_to_submission(result, expected=expected)
    return sub.model_dump()


@app.post("/homework/generate", response_model=Assignment)
def homework_generate(req: GenerateHomeworkRequest) -> Assignment:
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
        slides, title=req.title, subject=req.subject, source=source,
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


@app.post("/provenance/sign", response_model=SignedManifest)
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
