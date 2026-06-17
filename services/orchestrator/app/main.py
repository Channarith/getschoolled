"""Orchestrator FastAPI app: the teaching brain API consumed by apps/web."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from eduplatform_shared.config import get_settings
from eduplatform_shared.factory import get_provider_factory
from eduplatform_shared.schemas import (
    Answer,
    ClassType,
    HealthStatus,
    Lesson,
    Question,
    SessionState,
    Slide,
)

from app.curriculum import CurriculumStore
from app.director import Director

app = FastAPI(title="Orchestrator - Teaching Director", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_director: Director | None = None


def get_director() -> Director:
    global _director
    if _director is None:
        _director = Director(get_provider_factory(), CurriculumStore())
    return _director


class StartSessionRequest(BaseModel):
    lesson_id: str
    class_type: ClassType = ClassType.GROUP


class SessionView(BaseModel):
    session: SessionState
    lesson: Lesson
    slide: Slide


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(service="orchestrator", deploy_mode=get_settings().deploy_mode.value)


@app.get("/api/lessons", response_model=list[Lesson])
def lessons() -> list[Lesson]:
    return get_director().list_lessons()


@app.post("/api/sessions", response_model=SessionView)
def start_session(req: StartSessionRequest) -> SessionView:
    director = get_director()
    try:
        session = director.start_session(req.lesson_id, req.class_type)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown lesson {req.lesson_id}")
    return SessionView(
        session=session,
        lesson=director.lesson_for_session(session.session_id),
        slide=director.current_slide(session.session_id),
    )


@app.get("/api/sessions/{session_id}", response_model=SessionView)
def get_session(session_id: str) -> SessionView:
    director = get_director()
    try:
        session = director.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")
    return SessionView(
        session=session,
        lesson=director.lesson_for_session(session_id),
        slide=director.current_slide(session_id),
    )


@app.post("/api/sessions/{session_id}/advance", response_model=Slide)
def advance(session_id: str) -> Slide:
    try:
        return get_director().advance(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")


@app.post("/api/sessions/{session_id}/ask", response_model=Answer)
def ask(session_id: str, question: Question) -> Answer:
    director = get_director()
    try:
        return director.ask(session_id, question)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")
