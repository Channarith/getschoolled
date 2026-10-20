"""FastAPI console for 3D cameras and grounded object questions."""

from __future__ import annotations

try:
    from aoep_shared.env_bootstrap import ensure_lab_env

    ensure_lab_env()
except Exception:  # noqa: BLE001 — the lab still boots offline
    pass

import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from aoep_shared.live_audio_agents import inject_client, install_live_audio_routes
from aoep_shared.object3d.ask import answer_about
from aoep_shared.object3d.capture import capture
from aoep_shared.object3d.gallery import ObjectGallery
from aoep_shared.object3d.pipeline import crop_rgb, observe, observe_for_camera
from aoep_shared.object3d.sensors import HeatReading, SensorBundle, SmellReading, TouchReading
from aoep_shared.object3d.train import train_samples_blocking
from aoep_shared.object3d.types import Frame, TrainSample

from .bench import run_bench, synthetic_frame
from .devices import TOOLS, connected_cameras, sdk_status
from .live import LiveHub
from .page import render_page

app = FastAPI(title="Sala Object3D Lab", version="0.1.0")
install_live_audio_routes(
    app,
    lab_name="Sala Object3D Lab",
    default_provider="salane",
    instructions=(
        "You are Sala, looking through the live object-recognition camera. "
        "Answer from the objects, distances, and signs in view. Keep each turn short."
    ),
)
_HUB_LOCK = threading.Lock()
_HUB: Optional[LiveHub] = None


def _gallery() -> ObjectGallery:
    gallery = getattr(app.state, "gallery", None)
    if gallery is None:
        gallery = ObjectGallery()
        app.state.gallery = gallery
        app.state.last = []
    return gallery


def _live() -> LiveHub:
    global _HUB
    with _HUB_LOCK:
        if _HUB is None:
            _HUB = LiveHub()
        hub = _HUB
    app.state.live = hub

    def _observe(frame: Frame):
        return observe_for_camera(frame, _gallery(), detector=hub.controls.detector)

    hub.observe = _observe
    return hub


def _frame_for(camera: str) -> Frame:
    if not camera:
        return synthetic_frame()
    hub = _live()
    if hub.running and hub.controls.camera == camera:
        frame = hub.frame_copy()
        if frame is not None:
            return frame
    return capture(camera)


def _bundle(celsius: Optional[float], smell: str, texture: str) -> SensorBundle:
    heat = HeatReading(float(celsius)) if celsius is not None else None
    smell_reading = SmellReading(smell.strip()) if smell.strip() else None
    touch = TouchReading(texture.strip()) if texture.strip() else None
    return SensorBundle(touch=touch, smell=smell_reading, heat=heat)


class LiveStart(BaseModel):
    camera: str = "realsense"
    quality: str = "clear"


class CaptureRequest(BaseModel):
    camera: str = "realsense"
    detector: str = "depth"
    question: str = ""


class AskRequest(BaseModel):
    question: str = "how far is it?"
    sign: str = ""
    target: str = "en"
    index: Optional[int] = None


class VoiceSay(BaseModel):
    text: str = ""
    language: str = "en"


class FreezeRequest(BaseModel):
    frozen: bool = True


class PickRequest(BaseModel):
    x: float
    y: float


class SelectRequest(BaseModel):
    index: int


class LabelCapture(BaseModel):
    label: str = Field(min_length=1)
    index: Optional[int] = None
    maker: str = ""
    year: int = 0
    celsius: Optional[float] = None
    smell: str = ""
    texture: str = ""


class EnrollRequest(BaseModel):
    label: str = Field(min_length=1)
    maker: str = ""
    year: int = 0
    celsius: Optional[float] = None
    smell: str = ""
    texture: str = ""
    camera: str = ""
    detector: str = "depth"


@app.get("/", response_class=HTMLResponse)
@app.get("/lab", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(inject_client(render_page()))


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "theodore-object3d-lab",
        "sdk": sdk_status(),
        "enrolled": len(_gallery()),
    }


@app.get("/api/object3d/tools")
def tools() -> dict[str, Any]:
    return {"tools": list(TOOLS)}


@app.get("/api/object3d/devices")
def devices() -> dict[str, Any]:
    return {"sdk": sdk_status(), "cameras": connected_cameras()}


@app.post("/api/object3d/bench")
def bench() -> dict[str, Any]:
    report = run_bench()
    return report


@app.get("/api/object3d/live/status")
def live_status() -> dict[str, Any]:
    return _live().status()


@app.get("/api/object3d/live/frame.jpg")
def live_frame(view: str = "color") -> Response:
    blob = _live().jpeg("depth" if view == "depth" else "color")
    return Response(content=blob, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/object3d/live/start")
def live_start(req: LiveStart) -> dict[str, Any]:
    try:
        info = _live().start(req.camera, req.quality)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **info}


@app.post("/api/object3d/live/stop")
def live_stop() -> dict[str, Any]:
    return {"ok": True, **_live().stop()}


@app.post("/api/object3d/live/controls")
def live_controls(body: dict[str, Any]) -> dict[str, Any]:
    hub = _live()
    hub.update(body)
    return {"ok": True, "controls": hub.controls_dict()}


@app.post("/api/object3d/live/reset")
def live_reset() -> dict[str, Any]:
    hub = _live()
    hub.reset_controls()
    return {"ok": True, "controls": hub.controls_dict()}


@app.post("/api/object3d/live/freeze")
def live_freeze(req: FreezeRequest) -> dict[str, Any]:
    body = _live().set_frozen(req.frozen)
    body["ok"] = True
    return body


@app.post("/api/object3d/live/pick")
def live_pick(req: PickRequest) -> dict[str, Any]:
    return _live().pick(req.x, req.y)


@app.post("/api/object3d/live/select")
def live_select(req: SelectRequest) -> dict[str, Any]:
    return _live().select_index(req.index)


@app.post("/api/object3d/live/label")
def live_label(req: LabelCapture) -> dict[str, Any]:
    return _live().label_and_capture(
        req.label,
        index=req.index,
        maker=req.maker,
        year=req.year,
        celsius=req.celsius,
        smell=req.smell,
        texture=req.texture,
    )


@app.post("/api/object3d/live/capture/stop")
def live_capture_stop() -> dict[str, Any]:
    return _live().stop_capture()


@app.post("/api/object3d/capture")
def capture_once(req: CaptureRequest) -> dict[str, Any]:
    try:
        frame = _frame_for(req.camera)
    except Exception as exc:
        return {"ok": False, "camera": req.camera, "error": str(exc)}
    frame.sensors = SensorBundle()
    found = observe_for_camera(frame, _gallery(), detector=req.detector)
    app.state.last = found
    answer = answer_about(req.question, found).text if req.question.strip() else ""
    return {
        "ok": True,
        "camera": frame.camera,
        "detector": req.detector,
        "answer": answer,
        "observations": [obs.to_dict() for obs in found],
    }


@app.post("/api/object3d/voice/say")
def voice_say(req: VoiceSay):
    text = req.text.strip()
    language = (req.language or "en").strip() or "en"
    browser = {"ok": False, "engine": "browser", "text": text, "language": language}
    if not text or not os.environ.get("COSYVOICE_URL", "").strip():
        return JSONResponse(browser)
    from aoep_shared.meeting.clone_tts import synthesize_cosyvoice

    folder = Path(tempfile.mkdtemp(prefix="object3d-voice-"))
    wav = folder / "say.wav"
    ok = synthesize_cosyvoice(text, wav, language=language)
    audio = wav if wav.is_file() else wav.with_suffix(".mp3")
    if not ok or not audio.is_file():
        return JSONResponse(browser)
    media = "audio/wav" if audio.suffix.lower() == ".wav" else "audio/mpeg"
    return Response(content=audio.read_bytes(), media_type=media)


@app.post("/api/object3d/ask")
def ask(req: AskRequest) -> dict[str, Any]:
    hub = _live()
    found = hub.observations() if hub.running or hub.frozen else []
    if hub.running and not found:
        frame = hub.frame_copy()
        if frame is not None:
            found = observe_for_camera(frame, _gallery(), detector=hub.controls.detector)
    from_camera = bool(found)
    if not found:
        found = list(getattr(app.state, "last", []) or [])
    if not found:
        found = observe(synthetic_frame(), _gallery(), detector="depth")
    app.state.last = found
    focus = req.index if req.index is not None else hub.selected
    if not from_camera or focus is None or focus < 0 or focus >= len(found):
        focus = None
    answer = answer_about(
        req.question,
        found,
        ocr_text=req.sign,
        target_language=req.target or "en",
        focus=focus,
    )
    return {
        "ok": True,
        "answer": answer.text,
        "intent": answer.intent,
        "index": focus,
        "observations": [obs.to_dict() for obs in found],
    }


@app.post("/api/object3d/enroll")
def enroll(req: EnrollRequest) -> dict[str, Any]:
    try:
        frame = _frame_for(req.camera)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    frame.sensors = _bundle(req.celsius, req.smell, req.texture)
    seen = observe_for_camera(frame, ObjectGallery(), detector=req.detector)
    if not seen:
        return {"ok": False, "error": "no object to enroll"}
    crop = crop_rgb(frame.rgb, seen[0].bbox)
    sample = TrainSample(
        label=req.label.strip(),
        image=crop,
        maker=req.maker,
        year=req.year or None,
        kind=seen[0].kind,
        heat_c=req.celsius,
        smell=req.smell.strip(),
        texture=req.texture.strip(),
    )
    report = train_samples_blocking(_gallery(), [sample], workers=1)
    found = observe_for_camera(frame, _gallery(), detector=req.detector)
    app.state.last = found
    return {
        "ok": True,
        "trained_views": report.views,
        "labels": report.labels,
        "observations": [obs.to_dict() for obs in found],
    }


def main() -> None:
    import uvicorn

    uvicorn.run("theodore_object3d_lab.main:app", host="127.0.0.1", port=8020, reload=False)


if __name__ == "__main__":
    main()
