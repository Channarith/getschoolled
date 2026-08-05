"""FastAPI app for the Theodore webcam lab.

Frames are analysed in memory and discarded; nothing about a learner's camera
is written to disk. Two ingest paths are offered on purpose: ``/frames`` (the
server runs OpenCV, easiest to iterate on) and ``/signals`` (the client ran
detection on-device and only reports a verdict), which is the shape a
production rollout should use.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .classroom import ParticipantNotFound, SessionNotFound, SessionRegistry
from .config import LabConfig, load_config
from .cues import ClassMode
from .frames import FrameDecodeError, decode_frame
from .xai_voice import XaiUnavailable, XaiVoiceAgent, execute_tool

WEB_DIR = Path(__file__).resolve().parent / "web"


class CreateSessionRequest(BaseModel):
    mode: str = Field(default="solo", pattern="^(solo|group)$")
    class_id: str = ""
    lesson_id: str = ""
    lesson_title: str = ""
    checkpoint: str = ""
    participants: List["ParticipantRequest"] = Field(default_factory=list)


class ParticipantRequest(BaseModel):
    participant_id: str
    display_name: str = ""
    role: str = "learner"


class FrameRequest(BaseModel):
    participant_id: str
    image: str = Field(description="base64 or data-URL encoded JPEG/PNG frame")


class SignalsRequest(BaseModel):
    participant_id: str
    detected: bool = False
    confidence: float = 0.0
    count: int = 0
    coverage: float = 0.0
    calibrating: bool = False


class RecalibrateRequest(BaseModel):
    participant_id: str = ""


class VoiceSessionRequest(BaseModel):
    session_id: str = ""
    participant_id: str = ""


class VoiceRespondRequest(BaseModel):
    transcript: str = ""
    session_id: str = ""
    participant_id: str = ""
    history: List[dict] = Field(default_factory=list)


class VoiceToolRequest(BaseModel):
    session_id: str
    name: str
    arguments: dict = Field(default_factory=dict)


CreateSessionRequest.model_rebuild()


def create_app(config: Optional[LabConfig] = None) -> FastAPI:
    cfg = config or load_config()
    app = FastAPI(
        title="Theodore Webcam Lab",
        version="0.1.0",
        description=(
            "Silhouette-based presence recognition for Theodore's solo and "
            "group classes, wired to xAI Grok voice agents."
        ),
    )
    app.state.config = cfg
    app.state.sessions = SessionRegistry(cfg)
    app.state.voice = XaiVoiceAgent(cfg.xai)

    origins = [o.strip() for o in cfg.allow_origins.split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _session(session_id: str):
        try:
            return app.state.sessions.get(session_id)
        except SessionNotFound:
            raise HTTPException(status_code=404, detail="session not found") from None

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": "theodore-webcam-lab",
            "sessions": len(app.state.sessions.list()),
            "voice": app.state.voice.status()["mode"],
        }

    @app.get("/v1/config")
    def get_config() -> dict:
        return cfg.public_dict()

    # -- sessions ------------------------------------------------------

    @app.post("/v1/sessions", status_code=201)
    def create_session(req: CreateSessionRequest) -> dict:
        session = app.state.sessions.create(
            mode=ClassMode(req.mode),
            class_id=req.class_id,
            lesson_id=req.lesson_id,
            lesson_title=req.lesson_title,
            checkpoint=req.checkpoint,
        )
        for participant in req.participants:
            session.add_participant(
                participant.participant_id,
                participant.display_name,
                participant.role,
            )
        return session.state()

    @app.get("/v1/sessions")
    def list_sessions() -> dict:
        return {"sessions": app.state.sessions.list()}

    @app.get("/v1/sessions/{session_id}")
    def get_session(session_id: str) -> dict:
        return _session(session_id).state()

    @app.delete("/v1/sessions/{session_id}")
    def end_session(session_id: str) -> dict:
        _session(session_id)
        return app.state.sessions.delete(session_id)

    @app.post("/v1/sessions/{session_id}/participants", status_code=201)
    def add_participant(session_id: str, req: ParticipantRequest) -> dict:
        session = _session(session_id)
        session.add_participant(req.participant_id, req.display_name, req.role)
        return session.state()

    @app.post("/v1/sessions/{session_id}/frames")
    def submit_frame(session_id: str, req: FrameRequest) -> dict:
        session = _session(session_id)
        try:
            frame = decode_frame(req.image, max_bytes=cfg.max_frame_bytes)
        except FrameDecodeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            result = session.observe_frame(req.participant_id, frame)
        except ParticipantNotFound:
            session.add_participant(req.participant_id)
            result = session.observe_frame(req.participant_id, frame)
        return result.as_dict()

    @app.post("/v1/sessions/{session_id}/signals")
    def submit_signals(session_id: str, req: SignalsRequest) -> dict:
        session = _session(session_id)
        try:
            session.participant(req.participant_id)
        except ParticipantNotFound:
            session.add_participant(req.participant_id)
        result = session.observe_signals(
            req.participant_id,
            detected=req.detected,
            confidence=req.confidence,
            count=req.count,
            coverage=req.coverage,
            calibrating=req.calibrating,
        )
        return result.as_dict()

    @app.post("/v1/sessions/{session_id}/tick")
    def tick_session(session_id: str) -> dict:
        session = _session(session_id)
        cues = session.tick()
        return {
            "cues": [c.as_dict() for c in cues],
            "state": session.state(),
        }

    @app.post("/v1/sessions/{session_id}/recalibrate")
    def recalibrate(session_id: str, req: RecalibrateRequest) -> dict:
        session = _session(session_id)
        try:
            reset = session.recalibrate(req.participant_id or None)
        except ParticipantNotFound:
            raise HTTPException(status_code=404, detail="participant not found") from None
        return {"recalibrated": reset}

    @app.get("/v1/sessions/{session_id}/report")
    def session_report(session_id: str) -> dict:
        return _session(session_id).report()

    # -- voice ---------------------------------------------------------

    @app.get("/v1/voice/status")
    def voice_status() -> dict:
        return app.state.voice.status()

    @app.get("/v1/voice/session-config")
    def voice_session_config(session_id: str = "", participant_id: str = "") -> dict:
        """The session.update payload, without minting a token to see it."""

        context = _voice_context(session_id, participant_id)
        return {
            "url": app.state.voice.realtime_url(),
            "session_update": app.state.voice.session_update(context),
            "context": context,
            "configured": app.state.voice.configured,
        }

    @app.post("/v1/voice/session")
    def voice_session(req: VoiceSessionRequest) -> dict:
        context = _voice_context(req.session_id, req.participant_id)
        try:
            session = app.state.voice.start_session(context)
        except XaiUnavailable as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        payload = session.as_dict()
        payload["context"] = context
        payload["fallback"] = not session.ephemeral
        return payload

    @app.post("/v1/voice/respond")
    def voice_respond(req: VoiceRespondRequest) -> dict:
        context = _voice_context(req.session_id, req.participant_id)
        reply = app.state.voice.respond(
            req.transcript, context=context, history=req.history
        )
        payload = reply.as_dict()
        payload["context"] = context
        return payload

    @app.post("/v1/voice/tool")
    def voice_tool(req: VoiceToolRequest) -> dict:
        session = _session(req.session_id)
        return {"name": req.name, "result": execute_tool(session, req.name, req.arguments)}

    def _voice_context(session_id: str, participant_id: str) -> dict:
        if not session_id:
            return {"mode": "solo"}
        try:
            session = app.state.sessions.get(session_id)
        except SessionNotFound:
            return {"mode": "solo"}
        context = {
            "mode": session.mode.value,
            "lesson_title": session.lesson_title,
            "checkpoint": session.checkpoint,
            "lesson_paused": session.lesson_paused,
            "class_held": session.class_held,
            "attendance": session.attendance(),
        }
        learners = session.learners()
        target = None
        if participant_id and participant_id in session.participants:
            target = session.participants[participant_id]
        elif learners:
            target = learners[0]
        if target is not None:
            snapshot = target.tracker.snapshot()
            context["participant_id"] = target.participant_id
            context["display_name"] = target.display_name
            context["presence"] = snapshot.state.value
            context["absent_seconds"] = round(snapshot.absent_seconds, 1)
        return context

    # -- demo ----------------------------------------------------------

    if cfg.demo_enabled and WEB_DIR.is_dir():
        app.mount("/demo", StaticFiles(directory=str(WEB_DIR), html=True), name="demo")

        @app.get("/", include_in_schema=False)
        def root() -> RedirectResponse:
            return RedirectResponse(url="/demo/")

    return app


app = create_app()
