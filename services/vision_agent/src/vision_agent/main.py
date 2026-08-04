"""Vision Agent — webcam image recognition and XAI Grok voice agent service.

This service is the private sub-module for building and testing webcam-based
presence, silhouette detection, and the xAI Grok voice agent for Theodore AI
teaching (solo and group class modes).

Architecture
------------
One FastAPI app (port 8006 local) with four capability groups:

1. Session management — create/read/end per-student or per-group webcam sessions.
2. Frame processing — POST raw webcam frames; get back face + silhouette analysis
   + presence state (PRESENT_FACE / PRESENT_SILHOUETTE / ABSENT / WARMING_UP).
3. Voice interaction — POST text or image queries; get Theodore's Grok response.
4. Server-Sent Events (SSE) stream — real-time presence/absence events per session.

Class types
-----------
  solo    — single student with Theodore teaching or self-study.
  group   — multiple students; each tracked independently; group events aggregated.

Presence + absence
------------------
  ``WebcamPresenceTracker`` debounces raw signals.  On absence:
  - The SSE stream emits an ``absence_start`` event.
  - Theodore (GrokVoiceAgent) generates a gentle invitation to return.
  - On return: ``absence_end`` + Theodore's welcome-back message.

XAI Grok voice agent
-------------------
  POST /sessions/{id}/voice      — student query → Theodore's Grok text response.
  POST /sessions/{id}/frame-chat — webcam frame → Grok Vision → Theodore reaction.
  When XAI_API_KEY is absent the endpoints return a 503 with a clear message.

Offline / CI mode
-----------------
  Without OpenCV or XAI_API_KEY the service still starts and returns graceful
  degradation responses (silhouette = absent, voice = 503).  Tests bypass both
  heavy deps using the lightweight stubs in conftest.py.

Endpoints (summary)
-------------------
  POST   /sessions                  create session
  GET    /sessions/{id}             session status + metrics
  DELETE /sessions/{id}             end session
  POST   /sessions/{id}/frame       process webcam frame
  POST   /sessions/{id}/voice       text query to Theodore (xAI Grok)
  POST   /sessions/{id}/frame-chat  frame analysis by Theodore (Grok Vision)
  GET    /sessions/{id}/events      SSE stream of presence events
  GET    /health                    service health (from create_service)
  GET    /version                   version
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from aoep_shared.service import create_service
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

app = create_service("vision_agent")

# ---------------------------------------------------------------------------
# Session store (in-memory; swap for Redis via aoep_shared Redis helpers
# when horizontal scaling is needed)
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    session_id: str
    class_type: str          # "solo" | "group"
    student_ids: List[str]   # enrolled student IDs (may be empty for self-study)
    lesson_title: str
    created_at: float
    ended: bool = False
    last_frame_at: Optional[float] = None
    # Presence tracking (lazy-initialised on first frame).
    _tracker: Optional[Any] = field(default=None, repr=False)
    _silhouette: Optional[Any] = field(default=None, repr=False)
    _voice_agent: Optional[Any] = field(default=None, repr=False)
    # SSE event queue (asyncio).
    _event_queue: Optional[asyncio.Queue] = field(default=None, repr=False)

    def get_tracker(self, cfg):
        if self._tracker is None:
            from aoep_shared.vision.webcam_presence import WebcamPresenceTracker
            def _on_absent(metrics):
                self._push_event("absence_start", {
                    "absence_events": metrics.absence_events,
                    "engagement_fraction": metrics.engagement_fraction,
                    "session_id": self.session_id,
                })
            def _on_return(metrics):
                self._push_event("absence_end", {
                    "return_events": metrics.return_events,
                    "session_id": self.session_id,
                })
            self._tracker = WebcamPresenceTracker(
                absence_threshold_s=cfg.vision_agent_absence_threshold_s,
                return_threshold_s=cfg.vision_agent_return_threshold_s,
                on_absent=_on_absent,
                on_return=_on_return,
            )
        return self._tracker

    def get_silhouette(self):
        if self._silhouette is None:
            try:
                from aoep_shared.vision.silhouette import SilhouetteDetector
                self._silhouette = SilhouetteDetector()
            except ImportError:
                self._silhouette = _NullSilhouette()
        return self._silhouette

    def get_voice_agent(self, cfg):
        if self._voice_agent is None:
            from aoep_shared.xai_voice import GrokVoiceAgent, xai_available
            if not xai_available(cfg.xai_api_key):
                return None
            self._voice_agent = GrokVoiceAgent(
                api_key=cfg.xai_api_key,
                base_url=cfg.xai_base_url,
                model=cfg.xai_model,
                vision_model=cfg.xai_vision_model,
                session_context={
                    "class_type": self.class_type,
                    "lesson_title": self.lesson_title,
                },
            )
        return self._voice_agent

    def get_event_queue(self) -> asyncio.Queue:
        if self._event_queue is None:
            self._event_queue = asyncio.Queue(maxsize=100)
        return self._event_queue

    def _push_event(self, kind: str, data: Dict[str, Any]) -> None:
        q = self.get_event_queue()
        try:
            q.put_nowait({"kind": kind, "data": data, "ts": time.time()})
        except asyncio.QueueFull:
            pass  # Drop if consumer not keeping up.


class _NullSilhouette:
    """Fallback when OpenCV is not installed."""
    _frames_seen: int = 0

    def process_frame(self, _: bytes):
        from aoep_shared.vision.silhouette import SilhouetteResult
        self._frames_seen += 1
        return SilhouetteResult(
            silhouette_present=False,
            num_blobs=0,
            largest_blob_area=0.0,
            largest_blob_bbox=None,
            confidence=0.0,
        )


_sessions: Dict[str, SessionState] = {}


def _get_session(session_id: str) -> SessionState:
    s = _sessions.get(session_id)
    if s is None or s.ended:
        raise HTTPException(status_code=404, detail="session not found or ended")
    return s


def _cfg():
    return app.state.config


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    class_type: str = "solo"          # "solo" | "group"
    student_ids: List[str] = []       # empty ok for anonymous self-study
    lesson_title: str = ""


class SessionResponse(BaseModel):
    session_id: str
    class_type: str
    student_ids: List[str]
    lesson_title: str
    created_at: float
    ended: bool
    last_frame_at: Optional[float]


class FrameAnalysisResponse(BaseModel):
    session_id: str
    presence_state: str              # PRESENT_FACE | PRESENT_SILHOUETTE | ABSENT | WARMING_UP
    face_count: int
    attention: float
    expression: Optional[str]
    silhouette_present: bool
    silhouette_confidence: float
    num_blobs: int
    largest_blob_area: float
    absence_events: int
    engagement_fraction: float
    processed_at: float


class VoiceRequest(BaseModel):
    text: str
    language: str = "en"


class VoiceResponse(BaseModel):
    session_id: str
    text: str                        # Theodore's response
    model: str
    latency_ms: float
    xai_available: bool


class FrameChatResponse(BaseModel):
    session_id: str
    text: str
    model: str
    latency_ms: float
    xai_available: bool
    presence_state: str


class MetricsResponse(BaseModel):
    session_id: str
    total_frames: int
    frames_face: int
    frames_silhouette: int
    frames_absent: int
    absence_events: int
    return_events: int
    engagement_fraction: float
    presence_fraction: float
    session_duration_s: float


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

@app.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(req: CreateSessionRequest) -> SessionResponse:
    """Create a new webcam teaching session.

    Parameters
    ----------
    class_type:
        ``"solo"`` (one student + Theodore AI) or ``"group"`` (multiple students).
    student_ids:
        Optional list of enrolled student IDs (for consent tracking).
    lesson_title:
        Current lesson name (used by Theodore's persona).
    """
    cfg = _cfg()
    active = sum(1 for s in _sessions.values() if not s.ended)
    if active >= cfg.vision_agent_max_sessions:
        raise HTTPException(status_code=429, detail="max concurrent sessions reached")
    if req.class_type not in ("solo", "group"):
        raise HTTPException(status_code=422, detail="class_type must be solo or group")

    sid = str(uuid.uuid4())
    session = SessionState(
        session_id=sid,
        class_type=req.class_type,
        student_ids=req.student_ids,
        lesson_title=req.lesson_title,
        created_at=time.time(),
    )
    _sessions[sid] = session
    return _session_to_response(session)


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    """Get session metadata and status."""
    return _session_to_response(_get_session(session_id))


@app.delete("/sessions/{session_id}", response_model=SessionResponse)
def end_session(session_id: str) -> SessionResponse:
    """End a webcam session. The session record is retained for metrics."""
    session = _get_session(session_id)
    session.ended = True
    session._push_event("session_ended", {"session_id": session_id})
    return _session_to_response(session)


@app.get("/sessions/{session_id}/metrics", response_model=MetricsResponse)
def get_metrics(session_id: str) -> MetricsResponse:
    """Return cumulative engagement metrics for the session."""
    session = _get_session(session_id)
    tracker = session._tracker
    if tracker is None:
        return MetricsResponse(
            session_id=session_id,
            total_frames=0, frames_face=0, frames_silhouette=0,
            frames_absent=0, absence_events=0, return_events=0,
            engagement_fraction=0.0, presence_fraction=0.0,
            session_duration_s=time.time() - session.created_at,
        )
    m = tracker.metrics
    return MetricsResponse(
        session_id=session_id,
        total_frames=m.total_frames,
        frames_face=m.frames_face,
        frames_silhouette=m.frames_silhouette,
        frames_absent=m.frames_absent,
        absence_events=m.absence_events,
        return_events=m.return_events,
        engagement_fraction=m.engagement_fraction,
        presence_fraction=m.presence_fraction,
        session_duration_s=m.session_duration_s,
    )


# ---------------------------------------------------------------------------
# Frame processing (core webcam analysis)
# ---------------------------------------------------------------------------

@app.post("/sessions/{session_id}/frame", response_model=FrameAnalysisResponse)
async def process_frame(
    session_id: str,
    file: UploadFile = File(...),
    consented_student_ids: str = Form(""),
) -> FrameAnalysisResponse:
    """Process a webcam frame: face detection + silhouette + presence tracking.

    Accepts a JPEG or PNG frame upload.  The face analysis calls the perception
    service's VisionProvider (via ``app.state.factory.vision()``); silhouette
    detection runs locally in this service via MOG2.

    Parameters
    ----------
    file:
        Raw JPEG or PNG bytes of the current webcam frame.
    consented_student_ids:
        Comma-separated student IDs who have given biometric consent (forwarded
        to the vision provider's consent gate).
    """
    session = _get_session(session_id)
    cfg = _cfg()
    frame_bytes = await file.read()
    session.last_frame_at = time.time()

    # ---- Silhouette detection (local MOG2) ---- #
    sil_detector = session.get_silhouette()
    sil_result = sil_detector.process_frame(frame_bytes)

    # ---- Face detection via vision provider ---- #
    face_count = 0
    attention = 0.0
    expression: Optional[str] = None
    try:
        vision = app.state.factory.vision()
        consented = [s.strip() for s in consented_student_ids.split(",") if s.strip()]
        observations = vision.analyze_image(frame_bytes, consented_student_ids=consented)
        face_count = len(observations)
        if observations:
            attention = sum(o.attention_score for o in observations) / face_count
            # Use the most common expression among detected faces.
            exprs = [o.expression for o in observations if o.expression]
            if exprs:
                expression = max(set(exprs), key=exprs.count)
    except NotImplementedError:
        # Vision provider unavailable (e.g. models not downloaded in CI).
        pass
    except Exception:
        pass

    # ---- Presence tracker ---- #
    tracker = session.get_tracker(cfg)
    warming_up = (
        hasattr(sil_detector, "_frames_seen") and sil_detector._frames_seen < 15
    )
    pf = tracker.update(
        face_count=face_count,
        silhouette_confidence=sil_result.confidence,
        attention=attention,
        expression=expression,
        warming_up=warming_up,
    )

    # ---- Absence prompt (async, fire-and-forget) ---- #
    if pf.state.value == "absent" and tracker.metrics.absence_events == 1:
        _schedule_absence_prompt(session, cfg)

    m = tracker.metrics
    return FrameAnalysisResponse(
        session_id=session_id,
        presence_state=pf.state.value,
        face_count=face_count,
        attention=round(attention, 4),
        expression=expression,
        silhouette_present=sil_result.silhouette_present,
        silhouette_confidence=sil_result.confidence,
        num_blobs=sil_result.num_blobs,
        largest_blob_area=sil_result.largest_blob_area,
        absence_events=m.absence_events,
        engagement_fraction=m.engagement_fraction,
        processed_at=session.last_frame_at,
    )


def _schedule_absence_prompt(session: SessionState, cfg) -> None:
    """Fire-and-forget: ask Theodore to generate an absence prompt."""
    async def _task():
        agent = session.get_voice_agent(cfg)
        if agent is None:
            return
        try:
            elapsed = time.time() - (session.last_frame_at or session.created_at)
            resp = agent.generate_absence_prompt(
                elapsed, lesson_title=session.lesson_title
            )
            session._push_event("theodore_absence_prompt", {
                "text": resp.text,
                "model": resp.model,
            })
        except Exception:
            pass
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_task())
    except RuntimeError:
        pass


# ---------------------------------------------------------------------------
# Voice interaction
# ---------------------------------------------------------------------------

@app.post("/sessions/{session_id}/voice", response_model=VoiceResponse)
def voice_query(session_id: str, req: VoiceRequest) -> VoiceResponse:
    """Send a text or voice query to Theodore (xAI Grok).

    The student's text (transcribed speech or typed) is sent to Grok with the
    Theodore persona.  The conversation history is maintained within the session
    for context.

    Returns 503 when XAI_API_KEY is not configured.
    """
    session = _get_session(session_id)
    cfg = _cfg()
    agent = session.get_voice_agent(cfg)
    if agent is None:
        return VoiceResponse(
            session_id=session_id,
            text="Theodore voice agent is not configured (XAI_API_KEY missing).",
            model="none",
            latency_ms=0.0,
            xai_available=False,
        )
    try:
        resp = agent.respond_to_query(req.text, language=req.language)
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"xAI API error: {exc}")
    session._push_event("voice_response", {"text": resp.text, "session_id": session_id})
    return VoiceResponse(
        session_id=session_id,
        text=resp.text,
        model=resp.model,
        latency_ms=resp.latency_ms,
        xai_available=True,
    )


@app.post("/sessions/{session_id}/frame-chat", response_model=FrameChatResponse)
async def frame_chat(
    session_id: str,
    file: UploadFile = File(...),
) -> FrameChatResponse:
    """Send a webcam frame to Theodore for engagement-aware analysis (Grok Vision).

    Theodore will describe the student's engagement and suggest an
    encouragement in 1-2 sentences.  Returns 503 when XAI_API_KEY is not set
    or the vision model is unavailable.
    """
    session = _get_session(session_id)
    cfg = _cfg()
    frame_bytes = await file.read()

    tracker = session._tracker
    presence_state = tracker.state.value if tracker else "unknown"
    face_count = 0
    attention = 0.0
    if tracker and tracker.history:
        last = tracker.history[-1]
        face_count = last.face_count
        attention = last.attention

    agent = session.get_voice_agent(cfg)
    if agent is None:
        return FrameChatResponse(
            session_id=session_id,
            text="Theodore voice agent is not configured (XAI_API_KEY missing).",
            model="none",
            latency_ms=0.0,
            xai_available=False,
            presence_state=presence_state,
        )
    try:
        resp = agent.respond_to_frame(
            frame_bytes,
            presence_state=presence_state,
            face_count=face_count,
            attention=attention,
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"xAI API error: {exc}")

    return FrameChatResponse(
        session_id=session_id,
        text=resp.text,
        model=resp.model,
        latency_ms=resp.latency_ms,
        xai_available=True,
        presence_state=presence_state,
    )


# ---------------------------------------------------------------------------
# Server-Sent Events stream
# ---------------------------------------------------------------------------

@app.get("/sessions/{session_id}/events")
async def events_stream(session_id: str, request: Request) -> StreamingResponse:
    """Server-Sent Events stream for real-time presence events.

    Events emitted (kind field):
      absence_start          — user went absent (includes absence_events count)
      absence_end            — user returned
      theodore_absence_prompt — Theodore's generated invite-back text
      voice_response         — Theodore's reply to a student query
      session_ended          — session was ended via DELETE

    Each SSE message is JSON under the ``data:`` field.
    """
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    q = session.get_event_queue()

    async def _generator() -> AsyncIterator[str]:
        yield f"data: {{'kind': 'connected', 'session_id': '{session_id}'}}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(q.get(), timeout=15.0)
                import json as _json
                yield f"data: {_json.dumps(event)}\n\n"
                if event.get("kind") == "session_ended":
                    break
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Capability probe
# ---------------------------------------------------------------------------

class CapabilityResponse(BaseModel):
    silhouette_detection: bool
    face_recognition: bool
    xai_voice_agent: bool
    xai_model: str
    xai_vision_model: str


@app.get("/capabilities", response_model=CapabilityResponse)
def capabilities() -> CapabilityResponse:
    """Report which capabilities are available in this environment."""
    cfg = _cfg()
    silhouette_ok = False
    try:
        import cv2  # noqa: F401
        silhouette_ok = True
    except ImportError:
        pass

    face_ok = False
    try:
        vision = app.state.factory.vision()
        face_ok = vision.ready()
    except Exception:
        pass

    from aoep_shared.xai_voice import xai_available
    return CapabilityResponse(
        silhouette_detection=silhouette_ok,
        face_recognition=face_ok,
        xai_voice_agent=xai_available(cfg.xai_api_key),
        xai_model=cfg.xai_model,
        xai_vision_model=cfg.xai_vision_model,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_to_response(s: SessionState) -> SessionResponse:
    return SessionResponse(
        session_id=s.session_id,
        class_type=s.class_type,
        student_ids=s.student_ids,
        lesson_title=s.lesson_title,
        created_at=s.created_at,
        ended=s.ended,
        last_frame_at=s.last_frame_at,
    )
