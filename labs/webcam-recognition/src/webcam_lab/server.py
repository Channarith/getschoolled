"""Optional FastAPI lab server for webcam recognition experiments."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from .presence import PresenceTracker
from .teaching import TeachingSession
from .vision_session import VisionSession, synthetic_person_frame

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Install server extras: pip install -e 'labs/webcam-recognition[server]'"
    ) from exc


WEB_DIR = Path(__file__).resolve().parents[2] / "web"

app = FastAPI(
    title="Webcam Recognition Lab",
    description="Private lab for Theodore solo/group webcam presence + xAI voice",
    version="0.1.0",
)

_sessions: Dict[str, TeachingSession] = {}
_vision: Dict[str, VisionSession] = {}


class CreateSessionBody(BaseModel):
    session_id: str = "demo"
    class_mode: str = "solo"
    teaching_mode: str = "theodore"
    topic: str = "general study"
    participant_id: str = "learner-1"
    participant_name: str = "Ada"
    use_xai: bool = False
    max_faces_allowed: int = 1
    require_liveness: bool = True


class PresenceBody(BaseModel):
    session_id: str
    participant_id: str
    face_count: int = 0
    silhouette_count: int = 0
    attention: float = 0.8
    gaze_frontal: float = 0.8


class SpeakBody(BaseModel):
    session_id: str
    text: str


class SyntheticBody(BaseModel):
    session_id: str = "demo"
    participant_id: str = "learner-1"
    with_body: bool = True
    with_face: bool = False
    absent_ticks: int = 0


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "webcam-lab",
        "xai_configured": bool(os.environ.get("XAI_API_KEY", "").strip()),
        "sessions": len(_sessions),
    }


@app.post("/sessions")
def create_session(body: CreateSessionBody) -> Dict[str, Any]:
    session = TeachingSession.create(
        class_mode=body.class_mode,
        teaching_mode=body.teaching_mode,
        topic=body.topic,
        use_xai=body.use_xai,
        max_faces_allowed=body.max_faces_allowed,
        require_liveness=body.require_liveness,
    )
    session.add_participant(
        body.participant_id,
        body.participant_name,
        max_faces_allowed=body.max_faces_allowed,
        require_liveness=body.require_liveness,
    )
    if body.class_mode.lower() == "group":
        # Seed a second optional seat so group mode is easy to exercise.
        if "learner-2" not in session.seats:
            session.add_participant("learner-2", "Bea", required=False)
    _sessions[body.session_id] = session
    _vision[body.session_id] = VisionSession(
        tracker=PresenceTracker(
            max_faces_allowed=body.max_faces_allowed,
            require_liveness=body.require_liveness,
        ),
        participant_id=body.participant_id,
    )
    return session.snapshot()


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> Dict[str, Any]:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "unknown session")
    return session.snapshot()


@app.post("/sessions/presence")
def post_presence(body: PresenceBody) -> Dict[str, Any]:
    session = _sessions.get(body.session_id)
    if not session:
        raise HTTPException(404, "unknown session")
    if body.participant_id not in session.seats:
        raise HTTPException(404, "unknown participant")
    report = session.report_presence(
        body.participant_id,
        face_count=body.face_count,
        silhouette_count=body.silhouette_count,
        attention=body.attention,
        gaze_frontal=body.gaze_frontal,
    )
    return {
        "report": report.as_dict(),
        "live_room_payload": report.to_live_room_payload(),
        "session": session.snapshot(),
    }


@app.post("/sessions/speak")
async def post_speak(body: SpeakBody) -> Dict[str, Any]:
    session = _sessions.get(body.session_id)
    if not session:
        raise HTTPException(404, "unknown session")
    result = await session.say(body.text)
    return {"result": result, "session": session.snapshot()}


@app.post("/sessions/synthetic-tick")
def synthetic_tick(body: SyntheticBody) -> Dict[str, Any]:
    """Run silhouette/face analysis on a synthetic frame (no camera needed)."""
    session = _sessions.get(body.session_id)
    if not session:
        raise HTTPException(404, "unknown session")
    vision = _vision.get(body.session_id) or VisionSession(participant_id=body.participant_id)
    _vision[body.session_id] = vision

    if body.absent_ticks > 0:
        reports = []
        for _ in range(body.absent_ticks):
            frame, _faces = synthetic_person_frame(with_body=False, with_face_box=False)
            analysis = vision.analyze_frame(frame)
            reports.append(analysis.report.as_dict())
            session.report_presence(
                body.participant_id,
                face_count=analysis.report.face_count,
                silhouette_count=analysis.report.silhouette_count,
            )
        return {"reports": reports, "session": session.snapshot()}

    frame, injected_faces = synthetic_person_frame(
        with_body=body.with_body,
        with_face_box=body.with_face,
    )
    if body.with_face and injected_faces:
        analysis = vision.analyze_detections(
            faces=injected_faces,
            silhouettes=vision.silhouette.detect(frame),
        )
    else:
        analysis = vision.analyze_frame(frame)
    session.report_presence(
        body.participant_id,
        face_count=analysis.report.face_count,
        silhouette_count=analysis.report.silhouette_count,
        attention=injected_faces[0].attention if injected_faces else 0.8,
        gaze_frontal=injected_faces[0].gaze_frontal if injected_faces else 0.8,
    )
    return {
        "analysis": {
            "face_count": len(analysis.faces),
            "silhouette_count": len(analysis.silhouettes),
            "report": analysis.report.as_dict(),
            "live_room_payload": analysis.report.to_live_room_payload(),
        },
        "session": session.snapshot(),
    }


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_path = WEB_DIR / "index.html"
    if index_path.is_file():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>webcam lab</h1><p>web/index.html missing</p>")


def main() -> None:
    import uvicorn

    port = int(os.environ.get("WEBCAM_LAB_PORT", "8093"))
    uvicorn.run("webcam_lab.server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
