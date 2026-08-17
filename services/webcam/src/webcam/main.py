"""Webcam Vision Service — presence, silhouette, face engagement, xAI voice.

This service is the dedicated hub for all webcam-based sensing during Salareen
teaching sessions. It combines three orthogonal signals:

1. Face recognition + engagement  (via the existing VisionProvider / perception).
2. Silhouette / body presence      (HOG person detector, background subtraction).
3. xAI Grok voice agent            (natural responses, audio synthesis).

It serves both solo and group-class scenarios:
- Solo:  one student + Theodore (AI teacher). Real-time presence events trigger
         automatic Theodore voice responses (pause on absence, re-engage on low
         attention).
- Group: per-participant presence tracking, quorum management, group summaries
         that the orchestrator uses to decide whether to continue or wait.

Session model
-------------
A webcam session is created with POST /sessions and keyed by ``session_id``.
Frames are submitted via POST /sessions/{id}/frame (REST) or streamed over
WS /sessions/{id}/ws (WebSocket).

The session stores a per-participant PresenceTracker and a SilhouetteDetector.
Every frame analysis returns a FrameAnalysis containing the combined signals.

Endpoints
---------
POST   /sessions                      Create a new webcam session.
DELETE /sessions/{id}                 End a session and clean up state.
GET    /sessions/{id}                 Current session state.
POST   /sessions/{id}/frame           Submit a single JPEG/PNG frame.
GET    /sessions/{id}/presence        Presence summary (solo or group roll-call).
POST   /sessions/{id}/voice           Ask the xAI voice agent a question.
POST   /sessions/{id}/voice/stream    Stream a voice agent reply (SSE).
WS     /sessions/{id}/ws              Real-time frame submission + event stream.
GET    /health                        Service health.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from aoep_shared.presence import (
    GroupPresenceTracker,
    GroupPresenceSummary,
    PresenceFrame,
    PresenceStatus,
    PresenceTracker,
)
from aoep_shared.service import create_service
from aoep_shared.silhouette import SilhouetteDetector, SilhouetteResult
from fastapi import (
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = create_service("webcam")


# --------------------------------------------------------------------------- #
# Session registry
# --------------------------------------------------------------------------- #

@dataclass
class WebcamSession:
    """In-memory state for one active webcam session."""

    session_id: str
    class_type: str          # "solo" | "group"
    lesson_context: str      # passed to Theodore's voice agent
    student_ids: List[str]   # enrolled participant IDs
    created_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)

    # Per-participant presence trackers.
    trackers: Dict[str, PresenceTracker] = field(default_factory=dict)
    group_tracker: Optional[GroupPresenceTracker] = None

    # Per-participant silhouette detectors (reset_background on session start).
    detectors: Dict[str, SilhouetteDetector] = field(default_factory=dict)

    # Running frame count (used for rate-limiting + debug).
    frame_count: int = 0

    def tracker_for(self, participant_id: str) -> PresenceTracker:
        if participant_id not in self.trackers:
            self.trackers[participant_id] = PresenceTracker(
                participant_id,
                away_grace_s=5.0,
                absent_confirm_s=30.0,
            )
        return self.trackers[participant_id]

    def detector_for(self, participant_id: str) -> SilhouetteDetector:
        if participant_id not in self.detectors:
            self.detectors[participant_id] = SilhouetteDetector()
        return self.detectors[participant_id]


_sessions: Dict[str, WebcamSession] = {}

# Sessions idle longer than this are reaped (each session pins per-participant
# SilhouetteDetectors with OpenCV background models, so leaking them grows
# memory without bound). Override with WEBCAM_SESSION_TTL_S.
_SESSION_TTL_S = float(os.environ.get("WEBCAM_SESSION_TTL_S", "7200"))
# Bound on distinct participants per session — participant_id comes from the
# client, and each new id allocates a MOG2 background model.
_MAX_PARTICIPANTS_PER_SESSION = int(
    os.environ.get("WEBCAM_MAX_PARTICIPANTS_PER_SESSION", "100")
)


def _reap_idle_sessions(now: Optional[float] = None) -> int:
    """Drop sessions with no activity for `_SESSION_TTL_S`. Returns count reaped."""
    now = time.monotonic() if now is None else now
    stale = [
        sid for sid, s in _sessions.items()
        if now - s.last_activity > _SESSION_TTL_S
    ]
    for sid in stale:
        _sessions.pop(sid, None)
    return len(stale)


def _get_session(session_id: str) -> WebcamSession:
    s = _sessions.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


def _check_participant(session: WebcamSession, participant_id: str) -> None:
    """Validate a client-supplied participant id before it allocates state."""
    pid = (participant_id or "").strip()
    if not pid or len(pid) > 128:
        raise HTTPException(status_code=422, detail="invalid participant_id")
    if session.student_ids and pid not in session.student_ids:
        raise HTTPException(status_code=403, detail="participant not in session roster")
    known = set(session.trackers) | set(session.detectors)
    if session.group_tracker is not None:
        known |= set(session.group_tracker.participant_ids)
    if pid not in known and len(known) >= _MAX_PARTICIPANTS_PER_SESSION:
        raise HTTPException(status_code=409, detail="session participant limit reached")


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #

class CreateSessionRequest(BaseModel):
    class_type: str = "solo"           # "solo" | "group"
    student_ids: List[str] = Field(default_factory=list)
    lesson_context: str = ""


class CreateSessionResponse(BaseModel):
    session_id: str
    class_type: str
    student_ids: List[str]


class SessionStateResponse(BaseModel):
    session_id: str
    class_type: str
    frame_count: int
    participant_count: int
    presence_states: Dict[str, str]  # participant_id -> PresenceState.value


class FrameAnalysisResponse(BaseModel):
    session_id: str
    participant_id: str
    face_present: bool
    silhouette_present: bool
    silhouette_method: str
    silhouette_absence_confidence: float
    largest_silhouette_coverage: float
    attention: Optional[float]
    presence_state: str
    presence_event: Optional[str]
    away_duration_s: float
    consecutive_absent_frames: int
    frame_count: int


class PresenceSummaryResponse(BaseModel):
    session_id: str
    class_type: str
    # Solo
    solo_status: Optional[Dict[str, Any]] = None
    # Group
    group_summary: Optional[Dict[str, Any]] = None
    participant_statuses: List[Dict[str, Any]] = Field(default_factory=list)


class VoiceRequest(BaseModel):
    participant_id: str = "student"
    text: str
    audio: bool = False          # request audio in response (requires XAI_AUDIO_MODEL)
    agent_type: str = "teacher"  # "teacher" | "self_teach"


class VoiceResponse(BaseModel):
    session_id: str
    participant_id: str
    text: str
    has_audio: bool
    audio_b64: Optional[str] = None
    model: str = ""
    fallback: bool = False  # True when xAI not available and we used the stub


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _xai_client():
    """Lazy-load the xAI client from app config."""
    from aoep_shared.xai_voice import make_client_from_config
    return make_client_from_config(app.state.config)


def _analyze_frame_data(
    session: WebcamSession,
    participant_id: str,
    image_data: bytes,
    face_attention: Optional[float],
    face_present: bool,
) -> FrameAnalysisResponse:
    """Run silhouette detection + presence update for one frame."""
    _check_participant(session, participant_id)
    detector = session.detector_for(participant_id)
    sil_result: SilhouetteResult = detector.analyze(image_data)

    # Build presence frame merging face + silhouette signals.
    pframe = PresenceFrame(
        face_present=face_present,
        silhouette_present=sil_result.present,
        attention=face_attention,
        silhouette_absence_confidence=sil_result.absence_confidence,
        face_absence_confidence=0.9 if not face_present else 0.0,
    )

    if session.group_tracker is not None:
        # Group sessions: route through the group tracker so roll-call and
        # quorum actually update (it was previously created but never fed, so
        # every group summary reported zero participants). Share its
        # per-participant tracker with session.trackers so the state/presence
        # endpoints keep working without double-pushing.
        status: PresenceStatus = session.group_tracker.push(participant_id, pframe)
        session.trackers[participant_id] = session.group_tracker.ensure_participant(
            participant_id
        )
    else:
        tracker = session.tracker_for(participant_id)
        status = tracker.push(pframe)
    session.frame_count += 1
    session.last_activity = time.monotonic()

    return FrameAnalysisResponse(
        session_id=session.session_id,
        participant_id=participant_id,
        face_present=face_present,
        silhouette_present=sil_result.present,
        silhouette_method=sil_result.method,
        silhouette_absence_confidence=sil_result.absence_confidence,
        largest_silhouette_coverage=sil_result.largest_coverage,
        attention=face_attention,
        presence_state=status.state.value,
        presence_event=status.event.value if status.event else None,
        away_duration_s=status.away_duration_s,
        consecutive_absent_frames=status.consecutive_absent_frames,
        frame_count=session.frame_count,
    )


# --------------------------------------------------------------------------- #
# Session management endpoints
# --------------------------------------------------------------------------- #

@app.post("/sessions", response_model=CreateSessionResponse)
def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    _reap_idle_sessions()
    session_id = str(uuid.uuid4())
    s = WebcamSession(
        session_id=session_id,
        class_type=req.class_type,
        lesson_context=req.lesson_context,
        student_ids=list(req.student_ids),
    )
    if req.class_type == "group":
        s.group_tracker = GroupPresenceTracker(quorum_ratio=0.5)
    _sessions[session_id] = s
    return CreateSessionResponse(
        session_id=session_id,
        class_type=req.class_type,
        student_ids=req.student_ids,
    )


@app.delete("/sessions/{session_id}", status_code=204)
def end_session(session_id: str) -> Response:
    _sessions.pop(session_id, None)
    return Response(status_code=204)


@app.get("/sessions/{session_id}", response_model=SessionStateResponse)
def get_session(session_id: str) -> SessionStateResponse:
    s = _get_session(session_id)
    return SessionStateResponse(
        session_id=s.session_id,
        class_type=s.class_type,
        frame_count=s.frame_count,
        participant_count=len(s.trackers),
        presence_states={
            pid: t.state.value for pid, t in s.trackers.items()
        },
    )


# --------------------------------------------------------------------------- #
# Frame submission
# --------------------------------------------------------------------------- #

@app.post("/sessions/{session_id}/frame", response_model=FrameAnalysisResponse)
async def submit_frame(
    session_id: str,
    file: UploadFile = File(...),
    participant_id: str = Form("student"),
    # Optional pre-computed face signals from the perception service or client.
    face_present: bool = Form(False),
    attention: float = Form(-1.0),  # -1 = not provided
) -> FrameAnalysisResponse:
    """Submit a webcam frame for analysis.

    The caller may optionally provide ``face_present`` and ``attention`` from
    a prior perception-service call (avoiding a double inference pass). When
    these are not provided the frame is analyzed purely on silhouette/HOG.
    """
    s = _get_session(session_id)
    _reap_idle_sessions()
    image_data = await file.read()
    face_att = attention if attention >= 0.0 else None
    return _analyze_frame_data(s, participant_id, image_data, face_att, face_present)


# --------------------------------------------------------------------------- #
# Presence summary
# --------------------------------------------------------------------------- #

@app.get("/sessions/{session_id}/presence", response_model=PresenceSummaryResponse)
def get_presence(session_id: str) -> PresenceSummaryResponse:
    s = _get_session(session_id)
    statuses = [t.status() for t in s.trackers.values()]
    statuses_dicts = [
        {
            "participant_id": st.participant_id,
            "state": st.state.value,
            "face_present": st.face_present,
            "silhouette_present": st.silhouette_present,
            "attention": st.attention,
            "away_duration_s": st.away_duration_s,
            "consecutive_absent_frames": st.consecutive_absent_frames,
        }
        for st in statuses
    ]

    if s.class_type == "solo":
        solo_st = statuses[0] if statuses else None
        solo_dict = (
            {
                "participant_id": solo_st.participant_id,
                "state": solo_st.state.value,
                "attention": solo_st.attention,
                "away_duration_s": solo_st.away_duration_s,
            }
            if solo_st
            else None
        )
        return PresenceSummaryResponse(
            session_id=session_id,
            class_type="solo",
            solo_status=solo_dict,
            participant_statuses=statuses_dicts,
        )

    # Group
    group_dict = None
    if s.group_tracker:
        summary: GroupPresenceSummary = s.group_tracker.summary()
        group_dict = {
            "total_participants": summary.total_participants,
            "present_count": summary.present_count,
            "away_count": summary.away_count,
            "absent_count": summary.absent_count,
            "unknown_count": summary.unknown_count,
            "quorum_met": summary.quorum_met,
            "average_attention": summary.average_attention,
            "present_ratio": summary.present_ratio,
            "absent_ids": summary.absent_ids,
            "away_ids": summary.away_ids,
        }
    return PresenceSummaryResponse(
        session_id=session_id,
        class_type="group",
        group_summary=group_dict,
        participant_statuses=statuses_dicts,
    )


# --------------------------------------------------------------------------- #
# xAI voice agent
# --------------------------------------------------------------------------- #

@app.post("/sessions/{session_id}/voice", response_model=VoiceResponse)
def voice_ask(session_id: str, req: VoiceRequest) -> VoiceResponse:
    """Send a text message to the xAI voice agent and get a response.

    When ``audio=True`` the response includes a base64-encoded MP3 segment
    (requires ``XAI_AUDIO_MODEL`` to be set and reachable). Falls back
    gracefully to a stub acknowledgement when xAI is not configured.
    """
    s = _get_session(session_id)
    client = _xai_client()

    if not client.available:
        # Polite fallback: acknowledge without a real Grok call.
        fallback_text = _stub_response(req.agent_type, req.text, s.lesson_context)
        return VoiceResponse(
            session_id=session_id,
            participant_id=req.participant_id,
            text=fallback_text,
            has_audio=False,
            fallback=True,
        )

    try:
        from aoep_shared.xai_voice import SelfTeachVoiceAgent, TeacherVoiceAgent

        if req.agent_type == "self_teach":
            agent = SelfTeachVoiceAgent(client, topic=s.lesson_context)
        else:
            agent = TeacherVoiceAgent(client, extra_context=s.lesson_context)

        resp = agent.speak(req.text, audio=req.audio)
        return VoiceResponse(
            session_id=session_id,
            participant_id=req.participant_id,
            text=resp.text,
            has_audio=resp.has_audio,
            audio_b64=resp.audio_b64,
            model=resp.model,
            fallback=False,
        )
    except NotImplementedError:
        fallback_text = _stub_response(req.agent_type, req.text, s.lesson_context)
        return VoiceResponse(
            session_id=session_id,
            participant_id=req.participant_id,
            text=fallback_text,
            has_audio=False,
            fallback=True,
        )
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=f"xAI API error: {exc}") from exc


@app.post("/sessions/{session_id}/voice/stream")
def voice_stream(session_id: str, req: VoiceRequest):  # type: ignore[return]
    """Stream an xAI voice agent reply as Server-Sent Events (text/event-stream).

    Each SSE event has ``data: <token>`` format. The stream ends with
    ``data: [DONE]``.
    """
    s = _get_session(session_id)
    client = _xai_client()

    if not client.available:
        stub = _stub_response(req.agent_type, req.text, s.lesson_context)

        def _stub_stream():
            for word in stub.split():
                yield f"data: {word} \n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_stub_stream(), media_type="text/event-stream")

    try:
        from aoep_shared.xai_voice import SelfTeachVoiceAgent, TeacherVoiceAgent

        if req.agent_type == "self_teach":
            agent = SelfTeachVoiceAgent(client, topic=s.lesson_context)
        else:
            agent = TeacherVoiceAgent(client, extra_context=s.lesson_context)

        def _gen():
            try:
                for token in agent.stream_speak(req.text):
                    yield f"data: {json.dumps(token)}\n\n"
            except Exception:  # noqa: BLE001
                pass
            yield "data: [DONE]\n\n"

        return StreamingResponse(_gen(), media_type="text/event-stream")

    except NotImplementedError:
        stub = _stub_response(req.agent_type, req.text, s.lesson_context)

        def _fallback_stream():
            for word in stub.split():
                yield f"data: {word} \n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_fallback_stream(), media_type="text/event-stream")


# --------------------------------------------------------------------------- #
# WebSocket — real-time bidirectional frame stream
# --------------------------------------------------------------------------- #

@app.websocket("/sessions/{session_id}/ws")
async def websocket_session(websocket: WebSocket, session_id: str) -> None:
    """Real-time webcam frame stream over WebSocket.

    Client → server messages (JSON):
      {"type": "frame", "participant_id": "...", "face_present": bool,
       "attention": float|null}
    followed by the binary JPEG/PNG frame payload in the next message.

    Server → client events (JSON):
      {"type": "analysis", ...FrameAnalysisResponse fields...}
      {"type": "presence_event", "event": "away"|"returned"|"absent", ...}
      {"type": "voice", "text": "...", "has_audio": bool, "audio_b64": "..."}
      {"type": "error", "detail": "..."}
    """
    await websocket.accept()
    s = _sessions.get(session_id)
    if s is None:
        await websocket.send_json({"type": "error", "detail": "Session not found"})
        await websocket.close(code=1008)
        return

    try:
        meta: Dict[str, Any] = {}
        async for message in websocket.iter_bytes():
            if not message:
                continue

            # JSON control frame?
            if message[0] == ord("{"):
                try:
                    meta = json.loads(message.decode("utf-8", errors="replace"))
                    if meta.get("type") == "close":
                        break
                except json.JSONDecodeError:
                    pass
                continue

            # Binary frame (JPEG/PNG).
            participant_id = str(meta.get("participant_id", "student"))
            face_present = bool(meta.get("face_present", False))
            att_raw = meta.get("attention")
            face_att = float(att_raw) if att_raw is not None else None

            try:
                result = _analyze_frame_data(
                    s, participant_id, message, face_att, face_present
                )
                payload = {
                    "type": "analysis",
                    **result.model_dump(),
                }
                await websocket.send_json(payload)

                # Emit a distinct presence_event if one was triggered.
                if result.presence_event:
                    await websocket.send_json({
                        "type": "presence_event",
                        "event": result.presence_event,
                        "participant_id": participant_id,
                        "state": result.presence_state,
                        "away_duration_s": result.away_duration_s,
                    })

            except Exception as exc:  # noqa: BLE001
                await websocket.send_json({"type": "error", "detail": str(exc)})

    except WebSocketDisconnect:
        pass


# --------------------------------------------------------------------------- #
# Stub / offline fallback
# --------------------------------------------------------------------------- #

def _stub_response(agent_type: str, user_text: str, context: str) -> str:
    """Generate a simple rule-based fallback when xAI is not configured."""
    text_lower = user_text.lower()
    if any(w in text_lower for w in ("hello", "hi ", "hey")):
        if agent_type == "teacher":
            return "Hello! I'm Theodore, your AI teacher. Ready to get started?"
        return "Hi! I'm your learning assistant. What would you like to explore?"

    if any(w in text_lower for w in ("absent", "away", "stepped away")):
        return "I noticed you stepped away — take your time, I'll be here when you're ready."

    if any(w in text_lower for w in ("returned", "back", "i'm back")):
        return "Welcome back! Let's pick up right where we left off."

    if any(w in text_lower for w in ("confus", "don't understand", "explain")):
        if agent_type == "self_teach":
            return "Let's think about this step by step. What part feels unclear?"
        return "Great question! Let me break that down for you."

    if agent_type == "teacher":
        return "I'm here to help. What would you like to know about this lesson?"
    return "That's interesting. What do you think happens next?"
