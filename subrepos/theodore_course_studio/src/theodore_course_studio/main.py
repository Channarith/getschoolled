"""FastAPI entrypoint for Theodore Course Studio experiments."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .corpus import default_corpus_root, load_corpus_index, scan_corpus, write_corpus_index
from .extract import extract_document
from .generate import CourseBuilder
from .review_store import ReviewStore
from .studio_page import render_studio_page
from .teach import TeachEngine
from .training_run import run_training_pass
from .types import CategoryId, LearnerProfileScores, QualityLabel

app = FastAPI(
    title="Theodore Course Studio",
    description="Labeled corpus training, review comments, course build, Theodore teach/present.",
    version="0.1.0",
)

_reviews = ReviewStore()
_builder = CourseBuilder()
_teach = TeachEngine(_builder)


class TrainingRunRequest(BaseModel):
    extract_text: bool = True
    seed_page_hints: bool = True
    max_docs: int | None = None


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
    max_slides: int = Field(default=20, ge=1, le=40)
    only_incorporate: bool = True


class TeachStartRequest(BaseModel):
    session_id: str = "studio-teach-1"
    course_id: str
    profile: LearnerProfileScores | None = None
    learner_id: str = "learner-demo"
    known_objective_ids: list[str] = Field(default_factory=list)
    focus_gaps: bool = True


class TeachSessionRequest(BaseModel):
    session_id: str = "studio-teach-1"


class TeachProfileRequest(BaseModel):
    session_id: str = "studio-teach-1"
    profile: LearnerProfileScores


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
    return {
        "service": "theodore-course-studio",
        "status": "ok",
        "corpus_root": str(default_corpus_root()),
    }


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


@app.post("/api/studio/pages/verdict")
def page_verdict(req: PageVerdictRequest) -> dict[str, Any]:
    review = _reviews.set_page_verdict(
        source_id=req.source_id,
        page_index=req.page_index,
        marked_reject=req.marked_reject,
        comment=req.comment,
    )
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
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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


@app.post("/api/studio/teach/profile")
def teach_profile(req: TeachProfileRequest) -> dict[str, Any]:
    try:
        return _teach.set_profile(req.session_id, req.profile)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"missing: {exc}") from exc


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
