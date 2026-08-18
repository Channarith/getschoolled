"""FastAPI entrypoint for Theodore Course Studio experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .certification_prep import (
    CertCourseRequest,
    CertTrackId,
    TRACK_NAMES,
    build_cert_course,
    list_cert_courses,
)
from .corpus import default_corpus_root, default_data_dir, load_corpus_index, scan_corpus, write_corpus_index
from .early_learning import (
    EarlyCourseRequest,
    EarlyLevel,
    LEVEL_NAMES,
    build_early_course,
    list_early_courses,
)
from .extract import extract_document
from .generate import CourseBuilder
from .offline_trainer import run_offline_training
from .quality_model import default_model_path, load_model, model_to_public_dict
from .quality_telemetry import get_telemetry
from .review_store import ReviewStore
from .studio_tuning import (
    apply_preset,
    get_tuning,
    patch_tuning,
    reset_tuning,
)
from .studio_languages import list_languages, normalize_language
from .studio_page import render_studio_page
from .teach import TeachEngine
from .training_run import run_training_pass
from .tts_client import build_tts_get_url, tts_client_hints, tts_status
from .neural_tts import TTSUnavailable, synthesize as synthesize_local, status as local_tts_status
from .types import CategoryId, LearnerProfileScores, QualityLabel
from .voice_agent import get_voice_agent

app = FastAPI(
    title="Theodore Course Studio",
    description="Labeled corpus training, review comments, course build, Theodore teach/present.",
    version="0.1.0",
)
_AVATAR_STATIC_DIR = Path(__file__).with_name("avatar_static")
app.mount(
    "/api/studio/avatar",
    StaticFiles(directory=_AVATAR_STATIC_DIR, check_dir=True),
    name="theodore-avatar",
)

_reviews = ReviewStore()
_builder = CourseBuilder()
_teach = TeachEngine(_builder)


class TrainingRunRequest(BaseModel):
    extract_text: bool = True
    seed_page_hints: bool = True
    max_docs: int | None = None


class OfflineTrainRequest(BaseModel):
    epochs: int = Field(default=20, ge=1, le=500)
    max_docs: int | None = None
    run_scan: bool = True
    resume_run_id: str | None = None
    fit_passes: int = Field(default=2, ge=1, le=20)
    target_score: float | None = Field(default=None, ge=0.0, le=1.0)


class PageVerdictRequest(BaseModel):
    source_id: str
    page_index: int = Field(ge=0)
    marked_reject: bool
    comment: str = ""


class CommentRequest(BaseModel):
    source_id: str
    body: str = Field(min_length=1)
    author: str = "reviewer"
    page_index: int | None = None
    course_id: str | None = None
    slide_index: int | None = None
    tags: list[str] = Field(default_factory=list)


class BuildCourseRequest(BaseModel):
    source_ids: list[str] | None = None
    category: CategoryId | None = None
    title: str | None = None
    max_slides: int = Field(default=12, ge=1, le=40)
    only_incorporate: bool = True
    language: str = "en"


class TeachStartRequest(BaseModel):
    session_id: str = "studio-teach-1"
    course_id: str
    profile: LearnerProfileScores | None = None
    learner_id: str = "learner-demo"
    known_objective_ids: list[str] = Field(default_factory=list)
    focus_gaps: bool = True
    language: str | None = None
    use_voice_agent: bool = True
    resume: bool = False
    soft_limit_minutes: int | None = Field(default=None, ge=5, le=90)
    voice_gender: str = "female"


class TeachSessionRequest(BaseModel):
    session_id: str = "studio-teach-1"


class TeachCheckpointLookup(BaseModel):
    learner_id: str = "learner-demo"
    course_id: str | None = None


class TeachProfileRequest(BaseModel):
    session_id: str = "studio-teach-1"
    profile: LearnerProfileScores


class TeachLanguageRequest(BaseModel):
    session_id: str = "studio-teach-1"
    language: str = "en"


class VoiceRespondRequest(BaseModel):
    session_id: str = "studio-teach-1"
    message: str = Field(min_length=1)


class PopAnswerRequest(BaseModel):
    session_id: str = "studio-teach-1"
    selected_index: int


class SummaryGradeRequest(BaseModel):
    session_id: str = "studio-teach-1"
    answers: dict[str, int] = Field(default_factory=dict)


class GameGradeRequest(BaseModel):
    session_id: str = "studio-teach-1"
    challenge: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, Any]:
    voice = get_voice_agent().status()
    return {
        "service": "theodore-course-studio",
        "status": "ok",
        "corpus_root": str(default_corpus_root()),
        "languages": len(list_languages()),
        "voice": voice,
        "tts": tts_status(),
    }


@app.get("/api/studio/presenter/manifest")
def presenter_manifest() -> dict[str, Any]:
    """Discover the best available GLB per persona (custom drop-in preferred)."""
    models: dict[str, dict[str, str]] = {}
    for persona in ("female", "male"):
        candidates = (
            (f"custom_{persona}.glb", "v2", "custom"),
            ("custom.glb", "v2", "custom"),
            (f"presenter_{persona}.glb", "procedural", "builtin"),
            ("theodore.glb", "procedural", "builtin"),
        )
        for filename, rig, source in candidates:
            if (_AVATAR_STATIC_DIR / filename).is_file():
                models[persona] = {
                    "file": filename,
                    "url": f"/api/studio/avatar/{filename}",
                    "rig": rig,
                    "source": source,
                }
                break
    return {
        "models": models,
        "rig_config_url": "/api/studio/avatar/avatar_rig_config_v2.json",
    }


@app.get("/api/studio/languages")
def studio_languages() -> dict[str, Any]:
    rows = list_languages()
    return {"count": len(rows), "languages": rows}


@app.get("/api/studio/voice/status")
def voice_status() -> dict[str, Any]:
    return {
        "voice": get_voice_agent().status(),
        "tts": tts_status(),
        "languages": len(list_languages()),
    }


@app.get("/api/studio/tuning")
def studio_tuning() -> dict[str, Any]:
    from .studio_tuning import PRESETS

    return {"tuning": get_tuning().to_dict(), "presets": sorted(PRESETS)}


@app.patch("/api/studio/tuning")
def update_studio_tuning(overrides: dict[str, Any]) -> dict[str, Any]:
    """Live-tune studio knobs. Unknown keys ignored; `reset` reloads env defaults."""
    body = dict(overrides or {})
    if body.pop("reset", False):
        reset_tuning()
    if body:
        try:
            patch_tuning(body)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"tuning": get_tuning().to_dict()}


@app.post("/api/studio/tuning/preset/{name}")
def studio_tuning_preset(name: str) -> dict[str, Any]:
    try:
        apply_preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"tuning": get_tuning().to_dict(), "preset": name}


@app.get("/api/studio/telemetry")
def studio_telemetry() -> dict[str, Any]:
    return get_telemetry().snapshot()


@app.get("/", response_class=HTMLResponse)
@app.get("/studio", response_class=HTMLResponse)
def studio() -> HTMLResponse:
    return HTMLResponse(render_studio_page())


@app.get("/api/studio/corpus")
def get_corpus() -> dict[str, Any]:
    docs = load_corpus_index()
    if not docs:
        docs = scan_corpus()
        if docs:
            write_corpus_index(docs)
    return {
        "count": len(docs),
        "incorporate_count": sum(1 for d in docs if d.incorporate),
        "reject_count": sum(1 for d in docs if d.quality_label is QualityLabel.BAD),
        "documents": [d.model_dump(mode="json") for d in docs],
    }


@app.get("/api/studio/sources/{source_id}")
def get_source(source_id: str) -> dict[str, Any]:
    docs = {d.source_id: d for d in (load_corpus_index() or scan_corpus())}
    doc = docs.get(source_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="source not found")
    extracted = extract_document(doc.path)
    page_reviews = {p.page_index: p for p in _reviews.pages_for(source_id)}
    pages = []
    for page in extracted.pages:
        review = page_reviews.get(page.index)
        marked = bool(review.marked_reject) if review else bool(page.marked_reject_hint)
        pages.append(
            {
                "index": page.index,
                "title": page.title,
                "text": page.text[:2500],
                "marked_reject": marked,
                "verdict": (review.verdict.value if review else "unreviewed"),
            }
        )
    return {
        "document": doc.model_dump(mode="json"),
        "extractor": extracted.extractor,
        "extract_error": extracted.error,
        "pages": pages,
        "comments": [c.model_dump(mode="json") for c in _reviews.comments_for(source_id=source_id)],
    }


@app.post("/api/studio/training/run")
def training_run(req: TrainingRunRequest) -> dict[str, Any]:
    report = run_training_pass(
        extract_text=req.extract_text,
        seed_page_hints=req.seed_page_hints,
        max_docs=req.max_docs,
    )
    return report.model_dump(mode="json")


@app.post("/api/studio/training/offline")
def offline_training(req: OfflineTrainRequest) -> dict[str, Any]:
    """Short/medium offline train from the API (long overnight runs use the CLI)."""
    try:
        state = run_offline_training(
            epochs=req.epochs,
            max_docs=req.max_docs,
            run_scan=req.run_scan and not req.resume_run_id,
            resume_run_id=req.resume_run_id,
            fit_passes=req.fit_passes,
            target_score=req.target_score,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    get_telemetry().record_offline_epochs(req.epochs)
    # Reload builder model so subsequent course builds use the new weights.
    # Carry live teach sessions over — rebinding a fresh engine used to strand
    # every in-flight session (their next advance/pop-quiz 404'd).
    global _builder, _teach
    old_teach = _teach
    _builder = CourseBuilder()
    _teach = TeachEngine(_builder)
    if old_teach is not None:
        _teach._sessions.update(old_teach._sessions)
    return state.model_dump(mode="json")


@app.get("/api/studio/training/offline/status")
def offline_training_status() -> dict[str, Any]:
    data_dir = default_data_dir()
    latest = data_dir / "offline_training" / "latest.json"
    model = load_model(default_model_path(data_dir))
    payload: dict[str, Any] = {
        "latest": None,
        "model": model_to_public_dict(model) if model else None,
    }
    if latest.is_file():
        import json

        payload["latest"] = json.loads(latest.read_text(encoding="utf-8"))
    return payload

@app.post("/api/studio/pages/verdict")
def page_verdict(req: PageVerdictRequest) -> dict[str, Any]:
    review = _reviews.set_page_verdict(
        source_id=req.source_id,
        page_index=req.page_index,
        marked_reject=req.marked_reject,
        comment=req.comment,
    )
    get_telemetry().record_review(keep=not req.marked_reject)
    return review.model_dump(mode="json")


@app.post("/api/studio/comments")
def add_comment(req: CommentRequest) -> dict[str, Any]:
    comment = _reviews.add_comment(
        source_id=req.source_id,
        body=req.body,
        author=req.author,
        page_index=req.page_index,
        course_id=req.course_id,
        slide_index=req.slide_index,
        tags=req.tags,
    )
    return comment.model_dump(mode="json")


@app.get("/api/studio/courses")
def list_courses() -> dict[str, Any]:
    courses = _builder.list_courses()
    return {"courses": [c.model_dump(mode="json") for c in courses]}


@app.get("/api/studio/early-learning/options")
def early_learning_options(level: EarlyLevel | None = None) -> dict[str, Any]:
    options = list_early_courses(level)
    return {
        "default_level": EarlyLevel.PRE_K.value,
        "levels": [
            {"code": item.value, "name": LEVEL_NAMES[item]}
            for item in EarlyLevel
        ],
        "courses": [row.model_dump(mode="json") for row in options],
    }


@app.post("/api/studio/courses/early-learning")
def build_early_learning_course(req: EarlyCourseRequest) -> dict[str, Any]:
    try:
        course = build_early_course(
            level=req.level,
            topic_id=req.topic_id,
            language=req.language,
            title=req.title,
            data_dir=_builder.data_dir,
            allow_xai_translation=req.allow_xai_translation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _builder.save_course(course)
    get_telemetry().record_early_course()
    return course.model_dump(mode="json")


@app.get("/api/studio/certification/options")
def certification_options(track: CertTrackId | None = None) -> dict[str, Any]:
    courses = list_cert_courses(track)
    return {
        "default_track": CertTrackId.CA_DMV_PERMIT.value,
        "prep_only": True,
        "tracks": [
            {
                "code": item.value,
                "name": TRACK_NAMES[item],
                "jurisdiction": (
                    "us-ca" if item is CertTrackId.CA_DMV_PERMIT else "us-ca-alameda"
                ),
            }
            for item in CertTrackId
        ],
        "courses": [row.model_dump(mode="json") for row in courses],
    }


@app.post("/api/studio/courses/certification")
def build_certification_course(req: CertCourseRequest) -> dict[str, Any]:
    try:
        course = build_cert_course(
            track=req.track,
            lesson_id=req.lesson_id,
            language=normalize_language(req.language),
            title=req.title,
            data_dir=_builder.data_dir,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _builder.save_course(course)
    get_telemetry().record_cert_course()
    return course.model_dump(mode="json")


@app.get("/api/studio/courses/{course_id}")
def get_course(course_id: str) -> dict[str, Any]:
    course = _builder.get_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")
    return course.model_dump(mode="json")


@app.post("/api/studio/courses/build")
def build_course(req: BuildCourseRequest) -> dict[str, Any]:
    try:
        course = _builder.build_from_sources(
            source_ids=req.source_ids,
            category=req.category,
            title=req.title,
            max_slides=req.max_slides,
            only_incorporate=req.only_incorporate,
            language=normalize_language(req.language),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    get_telemetry().record_course_built(audience=getattr(course, "audience", "general"))
    return course.model_dump(mode="json")


@app.post("/api/studio/teach/start")
def teach_start(req: TeachStartRequest) -> dict[str, Any]:
    try:
        return _teach.start(
            session_id=req.session_id,
            course_id=req.course_id,
            profile=req.profile,
            learner_id=req.learner_id,
            known_objective_ids=req.known_objective_ids,
            focus_gaps=req.focus_gaps,
            language=req.language,
            use_voice_agent=req.use_voice_agent,
            resume=req.resume,
            soft_limit_minutes=req.soft_limit_minutes,
            voice_gender=req.voice_gender,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/studio/teach/advance")
def teach_advance(req: TeachSessionRequest) -> dict[str, Any]:
    try:
        return _teach.advance(req.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc


@app.post("/api/studio/teach/continue")
def teach_continue(req: TeachSessionRequest) -> dict[str, Any]:
    try:
        return _teach.continue_past_checkpoint(req.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc


@app.post("/api/studio/teach/come-back-later")
def teach_come_back_later(req: TeachSessionRequest) -> dict[str, Any]:
    try:
        return _teach.come_back_later(req.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc


@app.get("/api/studio/teach/checkpoints")
def teach_checkpoints(learner_id: str = "learner-demo", course_id: str | None = None) -> dict[str, Any]:
    if course_id:
        row = _teach.get_checkpoint(learner_id, course_id)
        return {
            "learner_id": learner_id,
            "checkpoints": [row.model_dump(mode="json")] if row else [],
        }
    rows = _teach.list_checkpoints(learner_id)
    return {
        "learner_id": learner_id,
        "checkpoints": [r.model_dump(mode="json") for r in rows],
    }


@app.post("/api/studio/teach/profile")
def teach_profile(req: TeachProfileRequest) -> dict[str, Any]:
    try:
        return _teach.set_profile(req.session_id, req.profile)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc


@app.post("/api/studio/teach/language")
def teach_language(req: TeachLanguageRequest) -> dict[str, Any]:
    try:
        return _teach.set_language(req.session_id, req.language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc


@app.post("/api/studio/teach/voice/respond")
def teach_voice_respond(req: VoiceRespondRequest) -> dict[str, Any]:
    try:
        return _teach.voice_respond(req.session_id, req.message)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc


@app.post("/api/studio/teach/voice/present")
def teach_voice_present(req: TeachSessionRequest) -> dict[str, Any]:
    try:
        return _teach.voice_present_current(req.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc


@app.get("/api/studio/tts/status")
def studio_tts_status() -> dict[str, Any]:
    """Combined gateway + local neural status (probed once by the player)."""
    hints = tts_client_hints("en")
    return {
        "available": bool(hints["speech"].get("available")),
        "engine": hints["speech"].get("engine"),
        "source": hints["speech"].get("source"),
        "gateway": tts_status(),
        "local": local_tts_status(),
        "engine_chain": hints["engine_chain"],
    }


@app.get("/api/studio/tts")
def studio_tts(
    text: str,
    language: str = "en",
    gender: str = "female",
    rate: float = 1.0,
) -> Response:
    """One narration as MP3 via local edge-tts (covers Khmer without the gateway).

    501 (not 500) when nothing can render it: that is the client's cue to fall
    back to the device voice rather than show an error.
    """
    try:
        audio = synthesize_local(text, language, rate=rate, gender=gender)
    except TTSUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"cache-control": "public, max-age=86400"},
    )


@app.get("/api/studio/tts/url")
def tts_url(
    text: str,
    language: str = "en",
    voice_gender: str = "female",
) -> dict[str, Any]:
    lang = normalize_language(language)
    hints = tts_client_hints(lang, voice_gender, text=text)
    return {
        "language": lang,
        "url": hints.get("get_url")
        or build_tts_get_url(text, language=lang, voice_gender=voice_gender),
        "hints": hints,
    }

@app.post("/api/studio/teach/pop-quiz")
def teach_pop_quiz(req: TeachSessionRequest) -> dict[str, Any]:
    try:
        return _teach.pop_quiz(req.session_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc


@app.post("/api/studio/teach/pop-answer")
def teach_pop_answer(req: PopAnswerRequest) -> dict[str, Any]:
    try:
        return _teach.answer_pop(req.session_id, req.selected_index)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/studio/teach/summary-quiz")
def teach_summary_quiz(req: TeachSessionRequest) -> dict[str, Any]:
    try:
        quiz = _teach.summary_quiz(req.session_id)
        return {
            "quiz_id": quiz.quiz_id,
            "kind": quiz.kind,
            "questions": [q.model_dump(mode="json") for q in quiz.questions],
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc


@app.post("/api/studio/teach/summary-grade")
def teach_summary_grade(req: SummaryGradeRequest) -> dict[str, Any]:
    try:
        return _teach.grade_summary(req.session_id, req.answers).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/studio/teach/game")
def teach_game(req: TeachSessionRequest) -> dict[str, Any]:
    try:
        return _teach.game_for_current(req.session_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc


@app.post("/api/studio/teach/game-grade")
def teach_game_grade(req: GameGradeRequest) -> dict[str, Any]:
    try:
        return _teach.grade_game_response(
            req.session_id, req.challenge, req.response
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc
    except (ValueError, TypeError) as exc:
        # Malformed challenge/response payloads (e.g. missing fields, null or
        # non-numeric selected_index) are client errors, not 500s.
        raise HTTPException(status_code=422, detail=f"invalid game grade request: {exc}") from exc
