"""Orchestrator FastAPI app.

Owns class-session lifecycle and exposes the Director decision endpoint. It
issues LiveKit join tokens via the MediaProvider so the same flow works against a
local LiveKit container or a cloud cluster.
"""

from __future__ import annotations

import uuid

from aoep_shared.schemas import ClassType
from aoep_shared.service import create_service
from pydantic import BaseModel

from .director import ClassContext, Director, LessonState

app = create_service("orchestrator")


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
