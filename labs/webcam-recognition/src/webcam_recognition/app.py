"""FastAPI app to build & test the webcam-recognition feature end to end.

Endpoints:
- GET  /                      browser demo (webcam capture -> live presence + agent)
- GET  /health               liveness + which capabilities are available
- POST /analyze              recognize one frame (silhouette + optional face)
- POST /sessions             create a solo/group class session
- GET  /sessions/{id}        session status (presence, attendance, headcount)
- POST /sessions/{id}/frame  feed a frame/signal -> presence events + teaching action
- POST /sessions/{id}/say    talk to the agent (natural conversation)
- POST /agent/respond        stateless agent reply for a classroom context

Server-side silhouette detection uses OpenCV HOG (real, CPU-only); face
detection/engagement reuse ``aoep_shared.vision`` when importable. Both degrade
gracefully: if a model/dep is missing the endpoint still returns the parts it can
compute, and the whole session/agent loop works from client-provided signals.
"""

from __future__ import annotations

import os
import time
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import load_lab_config
from .session import ClassMode, GroupSession, SoloSession, TeachingMode
from .silhouette import FramePerception, summarize_frame
from .teaching import TeachingConductor
from .voice_agent import ClassroomContext, XAIVoiceAgent

app = FastAPI(title="AOEP Webcam Recognition Lab", version="0.1.0")

_CONFIG = load_lab_config()
_AGENT = XAIVoiceAgent(_CONFIG)
_SESSIONS: dict = {}
_CONDUCTORS: dict = {}

# Lazily-built, cached silhouette detector (None until first use / if cv2 absent).
_DETECTOR = None
_DETECTOR_TRIED = False

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def _now() -> float:
    return time.monotonic()


def _get_detector():
    global _DETECTOR, _DETECTOR_TRIED
    if _DETECTOR_TRIED:
        return _DETECTOR
    _DETECTOR_TRIED = True
    try:
        from .silhouette import SilhouetteDetector

        _DETECTOR = SilhouetteDetector(hit_threshold=_CONFIG.hog_hit_threshold)
    except Exception:
        _DETECTOR = None
    return _DETECTOR


def _face_analyze(data: bytes, consented_ids: List[str]):
    """Best-effort face detection + engagement via aoep_shared. Returns
    (face_count, best_attention, matched_ids) or (0, 0.0, []) if unavailable."""
    try:
        from aoep_shared.factory import build_factory  # type: ignore

        vision = build_factory().vision()
        obs = vision.analyze_image(data, consented_student_ids=consented_ids)
        matched = [o.matched_student_id for o in obs if o.matched_student_id]
        attention = max((o.attention_score for o in obs), default=0.0)
        return len(obs), attention, matched
    except Exception:
        return 0, 0.0, []


def _recognize(
    data: bytes, consented_ids: List[str]
) -> FramePerception:
    silhouettes = []
    detector = _get_detector()
    if detector is not None:
        try:
            silhouettes = detector.detect(data)
        except Exception:
            silhouettes = []
    face_count, attention, matched = _face_analyze(data, consented_ids)
    return summarize_frame(
        silhouettes,
        face_count=face_count,
        attention=attention,
        matched_student_ids=matched,
        min_coverage=_CONFIG.min_silhouette_coverage,
    )


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
@app.get("/health")
def health() -> dict:
    detector = _get_detector()
    return {
        "status": "ok",
        "silhouette_detector": detector is not None,
        "xai_agent_configured": _AGENT.configured,
        "agent_persona": _AGENT.persona,
        "sessions": len(_SESSIONS),
    }


# --------------------------------------------------------------------------- #
# Stateless frame analysis
# --------------------------------------------------------------------------- #
@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    consented_student_ids: str = Form(""),
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="empty frame")
    consented = [s.strip() for s in consented_student_ids.split(",") if s.strip()]
    perception = _recognize(data, consented)
    return perception.as_dict()


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #
class CreateSessionRequest(BaseModel):
    session_id: str
    mode: str = "solo"            # solo | group
    teaching_mode: str = "theodore"  # theodore | self
    topic: str = ""


@app.post("/sessions")
def create_session(req: CreateSessionRequest) -> dict:
    try:
        mode = ClassMode(req.mode)
        teaching = TeachingMode(req.teaching_mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if req.session_id in _SESSIONS:
        raise HTTPException(status_code=409, detail="session exists")
    if mode is ClassMode.SOLO:
        _SESSIONS[req.session_id] = SoloSession(
            req.session_id, teaching, _CONFIG
        )
    else:
        _SESSIONS[req.session_id] = GroupSession(
            req.session_id, teaching, _CONFIG
        )
    _CONDUCTORS[req.session_id] = TeachingConductor(
        _AGENT, class_mode=mode, teaching_mode=teaching, topic=req.topic
    )
    return _SESSIONS[req.session_id].status()


@app.get("/sessions/{session_id}")
def session_status(session_id: str) -> dict:
    sess = _SESSIONS.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return sess.status()


class FrameSignal(BaseModel):
    # Either supply a decoded signal directly (client-side / testing) ...
    person_present: Optional[bool] = None
    face_count: int = 0
    attention: float = 0.0
    # ... or, for a group class, the ids seen this frame.
    present_ids: List[str] = []
    learner_name: str = ""


@app.post("/sessions/{session_id}/frame")
def session_frame(session_id: str, sig: FrameSignal) -> dict:
    sess = _SESSIONS.get(session_id)
    conductor = _CONDUCTORS.get(session_id)
    if sess is None or conductor is None:
        raise HTTPException(status_code=404, detail="unknown session")
    now = _now()
    actions = []

    if isinstance(sess, SoloSession):
        present = (
            sig.person_present
            if sig.person_present is not None
            else (sig.face_count > 0)
        )
        perception = summarize_frame(
            [], face_count=sig.face_count, attention=sig.attention,
        )
        perception.person_present = bool(present)
        ev = sess.observe(perception, now)
        if ev is not None:
            actions.append(
                conductor.on_presence_event(
                    ev, learner_name=sig.learner_name,
                    away_seconds=sess.tracker.away_seconds_total,
                ).as_dict()
            )
        if sess.tracker.is_present and sig.face_count > 0:
            nudge = conductor.on_attention(
                sess.attention_ewma, learner_name=sig.learner_name
            )
            if nudge.reply is not None:
                actions.append(nudge.as_dict())
    else:  # group
        events = sess.observe(sig.present_ids, now)
        acts = conductor.handle_events(
            events,
            away_lookup=lambda pid: sess.participants[pid].tracker.away_seconds_total,
            name_lookup=lambda pid: sess.participants[pid].display_name,
            headcount=sess.headcount(),
        )
        actions.extend(a.as_dict() for a in acts)

    return {"status": sess.status(), "actions": actions}


class SayRequest(BaseModel):
    message: str
    learner_name: str = ""


@app.post("/sessions/{session_id}/say")
def session_say(session_id: str, req: SayRequest) -> dict:
    conductor = _CONDUCTORS.get(session_id)
    if conductor is None:
        raise HTTPException(status_code=404, detail="unknown session")
    action = conductor.answer(req.message, learner_name=req.learner_name)
    return action.as_dict()


# --------------------------------------------------------------------------- #
# Stateless agent
# --------------------------------------------------------------------------- #
class AgentRequest(BaseModel):
    class_mode: str = "solo"
    teaching_mode: str = "theodore"
    event: str = ""
    learner_name: str = ""
    topic: str = ""
    headcount: int = 0
    away_seconds: float = 0.0
    user_message: str = ""


@app.post("/agent/respond")
def agent_respond(req: AgentRequest) -> dict:
    ctx = ClassroomContext(
        class_mode=req.class_mode,
        teaching_mode=req.teaching_mode,
        event=req.event,
        learner_name=req.learner_name,
        topic=req.topic,
        headcount=req.headcount,
        away_seconds=req.away_seconds,
    )
    reply = _AGENT.respond(ctx, user_message=req.user_message)
    return reply.as_dict()


# --------------------------------------------------------------------------- #
# Browser demo
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
def index() -> str:
    path = os.path.join(_STATIC_DIR, "demo.html")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return "<h1>Webcam Recognition Lab</h1><p>demo.html not found</p>"
