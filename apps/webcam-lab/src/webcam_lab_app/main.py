"""Private webcam-lab FastAPI app.

Build/test harness for webcam recognition (face + silhouette + absence) and
xAI Grok Voice Agents for Theodore teaching and self-teach coaching.
"""

from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from aoep_shared.config import load_config
from aoep_shared.xai_realtime import (
    XaiVoiceError,
    build_voice_session,
    mint_ephemeral_token,
    xai_configured,
)

from .analyzer import analyze_frame_bytes, analyze_reported
from .session import MODE_GROUP, MODE_SELF_TEACH, MODE_SOLO, LabSessionStore

STORE = LabSessionStore()

app = FastAPI(
    title="AOEP Webcam Lab (PRIVATE)",
    version="0.1.0",
    description=(
        "Private sub-package for building and testing webcam image recognition, "
        "silhouette/absence detection, and xAI voice agents for Theodore + self-teach."
    ),
)


class CreateSessionBody(BaseModel):
    mode: str = Field(
        default=MODE_SOLO,
        description="solo | group | self_teach",
    )
    title: str = ""
    lesson_context: str = ""
    host_name: str = "Learner"
    learner_names: List[str] = Field(default_factory=list)


class AddParticipantBody(BaseModel):
    display_name: str
    role: str = "learner"


class PresenceReportBody(BaseModel):
    face_count: int = 0
    attention: float = 0.0
    gaze_frontal: float = 0.0
    silhouette_present: bool = False
    silhouette_confidence: float = 0.8
    liveness_ok: bool = True
    reason: str = ""
    expression: str = "unknown"


class VoiceTokenBody(BaseModel):
    mode: str = MODE_SOLO
    lesson_context: str = ""
    learner_names: List[str] = Field(default_factory=list)
    expires_seconds: int = 300
    session_id: Optional[str] = None


@app.get("/health")
def health():
    cfg = load_config()
    return {
        "status": "ok",
        "service": "webcam-lab",
        "private": True,
        "xai_configured": xai_configured(cfg.xai_api_key),
        "xai_voice_model": cfg.xai_voice_model,
        "modes": [MODE_SOLO, MODE_GROUP, MODE_SELF_TEACH],
        "capabilities": [
            "webcam_frame_analyze",
            "silhouette_detection",
            "user_absence",
            "xai_voice_ephemeral_token",
            "theodore_solo",
            "theodore_group",
            "self_teach",
        ],
    }


@app.get("/", response_class=HTMLResponse)
def demo_page():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "..", "static", "demo.html")
    path = os.path.normpath(path)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(
        "<h1>Webcam Lab</h1><p>static/demo.html missing. Use /health and /docs.</p>"
    )


@app.post("/sessions")
def create_session(body: CreateSessionBody):
    cfg = load_config()
    try:
        session = STORE.create(
            body.mode,
            title=body.title,
            lesson_context=body.lesson_context,
            host_name=body.host_name,
            learner_names=body.learner_names,
            voice_id=cfg.xai_voice_id,
            voice_model=cfg.xai_voice_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@app.get("/sessions")
def list_sessions():
    return {"sessions": [s.to_dict() for s in STORE.list_sessions()]}


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    session = STORE.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session.to_dict()


@app.post("/sessions/{session_id}/participants")
def add_participant(session_id: str, body: AddParticipantBody):
    try:
        part = STORE.add_participant(session_id, body.display_name, role=body.role)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "participant_id": part.participant_id,
        "display_name": part.display_name,
        "role": part.role,
    }


@app.post("/sessions/{session_id}/participants/{participant_id}/presence")
def report_presence(session_id: str, participant_id: str, body: PresenceReportBody):
    try:
        decision = STORE.report_presence(
            session_id,
            participant_id,
            face_count=body.face_count,
            attention=body.attention,
            silhouette_present=body.silhouette_present,
            silhouette_confidence=body.silhouette_confidence,
            liveness_ok=body.liveness_ok,
            reason=body.reason,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="session or participant not found") from None
    session = STORE.get(session_id)
    return {
        "decision": {
            "state": decision.state,
            "present": decision.present,
            "hold": decision.hold,
            "face_count": decision.face_count,
            "silhouette_present": decision.silhouette_present,
            "attention": decision.attention,
            "absent_for_seconds": decision.absent_for_seconds,
            "reason": decision.reason,
            "should_reengage": decision.should_reengage,
        },
        "session_hold": bool(session and session.hold),
        "session_status": session.status if session else "unknown",
    }


@app.get("/sessions/{session_id}/participants/{participant_id}/presence")
def get_presence(session_id: str, participant_id: str):
    """Tool-callable snapshot (xAI function get_learner_presence)."""
    try:
        return STORE.presence_snapshot(session_id, participant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session or participant not found") from None


@app.post("/sessions/{session_id}/close")
def close_session(session_id: str):
    try:
        STORE.close(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found") from None
    return {"closed": True, "session_id": session_id}


@app.post("/analyze/frame")
async def analyze_frame(file: UploadFile = File(...)):
    """Upload a webcam still; returns face + silhouette signals."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    result = analyze_frame_bytes(data)
    return result.to_dict()


@app.post("/analyze/report")
def analyze_report(body: PresenceReportBody):
    """Hybrid path: client already ran on-device detect; server scores presence."""
    result = analyze_reported(
        face_count=body.face_count,
        attention=body.attention,
        gaze_frontal=body.gaze_frontal,
        expression=body.expression,
        silhouette_present=body.silhouette_present,
        silhouette_confidence=body.silhouette_confidence,
    )
    return result.to_dict()


@app.post("/voice/token")
def voice_token(body: VoiceTokenBody):
    """Mint an xAI ephemeral client secret + Theodore/self-teach session.update."""
    cfg = load_config()
    lesson = body.lesson_context
    names = list(body.learner_names)
    if body.session_id:
        session = STORE.get(body.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
        lesson = lesson or session.lesson_context
        if not names:
            names = [p.display_name for p in session.participants.values()]
        mode = session.mode
        voice_cfg = session.voice_config or build_voice_session(
            mode,
            voice=cfg.xai_voice_id,
            model=cfg.xai_voice_model,
            lesson_context=lesson,
            learner_names=names,
        )
    else:
        mode = body.mode
        voice_cfg = build_voice_session(
            mode,
            voice=cfg.xai_voice_id,
            model=cfg.xai_voice_model,
            lesson_context=lesson,
            learner_names=names,
        )
    try:
        token = mint_ephemeral_token(
            api_key=cfg.xai_api_key or None,
            expires_seconds=body.expires_seconds,
            model=cfg.xai_voice_model,
            allow_mock=True,
        )
    except XaiVoiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "token": token.to_dict(),
        "session_update": voice_cfg.session_update_event(),
        "mode": mode,
        "xai_configured": xai_configured(cfg.xai_api_key),
    }


def run() -> None:
    import uvicorn

    port = int(os.environ.get("WEBCAM_LAB_PORT", "8011"))
    uvicorn.run(
        "webcam_lab_app.main:app",
        host=os.environ.get("WEBCAM_LAB_HOST", "0.0.0.0"),
        port=port,
        reload=os.environ.get("WEBCAM_LAB_RELOAD", "").lower() in ("1", "true", "yes"),
    )


if __name__ == "__main__":
    run()
