"""Orchestrator FastAPI app.

Owns class-session lifecycle and exposes the Director decision endpoint. It
issues LiveKit join tokens via the MediaProvider so the same flow works against a
local LiveKit container or a cloud cluster.
"""

from __future__ import annotations

import uuid

from aoep_shared.adaptive import AdaptivePolicy, Difficulty, LearnerSignals, Pacing
from aoep_shared.assessment import (
    GradeResult,
    QuizItem,
    definition_items_from_passages,
    grade,
)
from aoep_shared.schemas import ClassType
from aoep_shared.service import create_service
from fastapi import HTTPException
from pydantic import BaseModel

from .curriculum import Lesson, Slide
from .director import ClassContext, Director, LessonState
from .teaching import Answer, SessionView, TeachingSessions

app = create_service("orchestrator")

# Live-class teaching loop (web-facing). Built lazily so /health and the other
# endpoints don't pay curriculum/RAG load cost unless a class is used.
_sessions: TeachingSessions | None = None


def get_sessions() -> TeachingSessions:
    global _sessions
    if _sessions is None:
        _sessions = TeachingSessions(app.state.factory)
    return _sessions


class CreateClassRequest(BaseModel):
    title: str
    class_type: ClassType = ClassType.GROUP
    language: str = "en"
    persona: str = "friendly"


class CreateClassResponse(BaseModel):
    class_id: str
    room: str
    title: str
    class_type: ClassType
    language: str
    persona: str


class JoinResponse(BaseModel):
    room: str
    identity: str
    token: str
    url: str


class DirectorTickRequest(BaseModel):
    class_type: ClassType = ClassType.GROUP
    slides_total: int = 1
    slide_index: int = 0
    pending_questions: int = 0
    attention: float = 1.0
    slides_since_quiz: int = 0


class DirectorTickResponse(BaseModel):
    next_state: LessonState


@app.post("/classes", response_model=CreateClassResponse)
def create_class(req: CreateClassRequest) -> CreateClassResponse:
    class_id = uuid.uuid4().hex
    room = f"class-{class_id[:8]}"
    return CreateClassResponse(
        class_id=class_id,
        room=room,
        title=req.title,
        class_type=req.class_type,
        language=req.language,
        persona=req.persona,
    )


@app.get("/classes/{room}/join", response_model=JoinResponse)
def join_class(room: str, identity: str) -> JoinResponse:
    media = app.state.factory.media()
    token = media.issue_token(room=room, identity=identity)
    return JoinResponse(
        room=token.room, identity=token.identity, token=token.token, url=token.url
    )


# --------------------------------------------------------------------------- #
# Live-class teaching loop (consumed by apps/web)
# --------------------------------------------------------------------------- #
class StartSessionRequest(BaseModel):
    lesson_id: str
    class_type: ClassType = ClassType.GROUP


class AskRequest(BaseModel):
    text: str
    language: str = "en"


@app.get("/api/lessons", response_model=list[Lesson])
def api_lessons() -> list[Lesson]:
    return get_sessions().list_lessons()


@app.post("/api/sessions", response_model=SessionView)
def api_start_session(req: StartSessionRequest) -> SessionView:
    sessions = get_sessions()
    try:
        state = sessions.start_session(req.lesson_id, req.class_type.value)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown lesson {req.lesson_id}")
    return SessionView(
        session=state,
        lesson=sessions.lesson_for(state.session_id),
        slide=sessions.current_slide(state.session_id),
    )


@app.get("/api/sessions/{session_id}", response_model=SessionView)
def api_get_session(session_id: str) -> SessionView:
    sessions = get_sessions()
    try:
        state = sessions.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")
    return SessionView(
        session=state,
        lesson=sessions.lesson_for(session_id),
        slide=sessions.current_slide(session_id),
    )


@app.post("/api/sessions/{session_id}/advance", response_model=Slide)
def api_advance(session_id: str) -> Slide:
    try:
        return get_sessions().advance(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")


@app.post("/api/sessions/{session_id}/ask", response_model=Answer)
def api_ask(session_id: str, req: AskRequest) -> Answer:
    sessions = get_sessions()
    try:
        return sessions.ask(session_id, req.text, language=req.language)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")


@app.post("/director/tick", response_model=DirectorTickResponse)
def director_tick(req: DirectorTickRequest) -> DirectorTickResponse:
    director = Director()
    ctx = ClassContext(
        class_type=req.class_type,
        slides_total=req.slides_total,
        slide_index=req.slide_index,
        pending_questions=req.pending_questions,
        attention=req.attention,
        slides_since_quiz=req.slides_since_quiz,
    )
    return DirectorTickResponse(next_state=director.decide(ctx))


# --------------------------------------------------------------------------- #
# Phase 4 - adaptive pacing/difficulty plan
# --------------------------------------------------------------------------- #
class PlanRequest(DirectorTickRequest):
    topic_mastery: float = 0.5
    quiz_accuracy: float = 0.5
    avg_response_latency_s: float = 5.0
    attention_trend: float = 1.0
    question_rate: float = 0.0


class PlanResponse(BaseModel):
    next_state: LessonState
    pacing: Pacing
    difficulty: Difficulty
    reteach: bool
    reasons: list[str]


@app.post("/director/plan", response_model=PlanResponse)
def director_plan(req: PlanRequest) -> PlanResponse:
    director = Director()
    ctx = ClassContext(
        class_type=req.class_type,
        slides_total=req.slides_total,
        slide_index=req.slide_index,
        pending_questions=req.pending_questions,
        attention=req.attention,
        slides_since_quiz=req.slides_since_quiz,
    )
    signals = LearnerSignals(
        topic_mastery=req.topic_mastery,
        quiz_accuracy=req.quiz_accuracy,
        avg_response_latency_s=req.avg_response_latency_s,
        attention_trend=req.attention_trend,
        question_rate=req.question_rate,
    )
    state, plan = director.plan(ctx, signals)
    assert plan is not None
    return PlanResponse(
        next_state=state,
        pacing=plan.pacing,
        difficulty=plan.difficulty,
        reteach=plan.reteach,
        reasons=plan.reasons,
    )


# --------------------------------------------------------------------------- #
# Phase 5 - assessment (quizzes + grading)
# --------------------------------------------------------------------------- #
class QuizRequest(BaseModel):
    topic: str
    passages: list[str]
    max_items: int = 4


class QuizItemView(BaseModel):
    item_id: str
    topic: str
    prompt: str
    options: list[str]
    answer_index: int
    difficulty: Difficulty


class QuizResponse(BaseModel):
    items: list[QuizItemView]


class GradeRequest(BaseModel):
    item_id: str
    options: list[str]
    answer_index: int
    chosen_index: int
    difficulty: Difficulty = Difficulty.MEDIUM
    topic: str = ""


class GradeResponse(BaseModel):
    item_id: str
    correct: bool
    mastery_target: float
    difficulty: Difficulty


@app.post("/assessment/quiz", response_model=QuizResponse)
def assessment_quiz(req: QuizRequest) -> QuizResponse:
    items = definition_items_from_passages(
        req.passages, req.topic, max_items=req.max_items
    )
    return QuizResponse(
        items=[
            QuizItemView(
                item_id=i.item_id,
                topic=i.topic,
                prompt=i.prompt,
                options=i.options,
                answer_index=i.answer_index,
                difficulty=i.difficulty,
            )
            for i in items
        ]
    )


@app.post("/assessment/grade", response_model=GradeResponse)
def assessment_grade(req: GradeRequest) -> GradeResponse:
    item = QuizItem(
        item_id=req.item_id,
        topic=req.topic,
        prompt="",
        options=req.options,
        answer_index=req.answer_index,
        difficulty=req.difficulty,
    )
    result: GradeResult = grade(item, req.chosen_index)
    return GradeResponse(
        item_id=result.item_id,
        correct=result.correct,
        mastery_target=result.mastery_target,
        difficulty=result.difficulty,
    )
