from __future__ import annotations

import html
import json
import os
import signal as _signal
import threading
import time

from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from .demo_seed import DEFAULT_SESSION_ID, DemoScenario, build_demo_payload
from .imaging import analyze_luminance_grid
from .games import WebcamLearningGameEngine
from .lesson_actions import LessonActionLog
from .live_metrics import LiveMetricsStore
from .monitor_page import MONITOR_PAGE_TEMPLATE as _MONITOR_PAGE_TEMPLATE
from .types import (
    AudioAnswerAssessment,
    ClassEvaluation,
    ClassMode,
    LiveSessionMetricsResponse,
    SupportedLanguage,
    VoiceResponse,
    VoiceQuestion,
    WebcamGameResult,
    WebcamGameType,
    WebcamLearningChallenge,
    WebcamSignal,
)
from .vision_tuning import PRESETS, VisionTuning
from .voice_tuning import PRESETS as VOICE_PRESETS
from .voice_tuning import VoiceTuning
from .responsiveness_tuning import PRESETS as RESP_PRESETS
from .responsiveness_tuning import ResponsivenessTuning
from .voice_agents import XaiVoiceAgent

app = FastAPI(
    title="Theodore Webcam Lab",
    version="0.1.0",
    description=(
        "Private-ready sandbox for Theodore webcam image recognition "
        "and xAI-backed natural responses."
    ),
)

# Self-hosted face-mesh assets. When this directory exists the live monitor loads
# the landmark model from here instead of the public CDN, so eye/gaze/expression
# tracking keeps working offline or behind a proxy. Populate it with:
#   tasks-vision.mjs, wasm/, face_landmarker.task
# See README.txt "Offline face mesh". Override the location with
# AOEP_VISION_ASSET_DIR; when it is absent the page falls back to the CDN.
VISION_ASSET_DIR = os.environ.get("AOEP_VISION_ASSET_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vendor", "vision"
)
if os.path.isdir(VISION_ASSET_DIR):
    from fastapi.staticfiles import StaticFiles

    app.mount(
        "/vendor/vision",
        StaticFiles(directory=VISION_ASSET_DIR),
        name="vision-assets",
    )

_analyzer = WebcamSessionAnalyzer(
    policy=AnalyzerPolicy.from_env(), tuning=VisionTuning.from_env()
)
_game_engine = WebcamLearningGameEngine(_analyzer)
_live_metrics_store = LiveMetricsStore()
_lesson_actions = LessonActionLog()
_voice_agent = XaiVoiceAgent.from_env()
_responsiveness = ResponsivenessTuning.from_env()
_responsiveness_preset_name: str | None = None
_demo_roll_stop: dict[str, threading.Event] = {}
_demo_roll_lock = threading.Lock()


class WebcamEvaluationRequest(BaseModel):
    session_id: str = Field(min_length=1)
    mode: ClassMode = ClassMode.SOLO
    signals: list[WebcamSignal] = Field(default_factory=list)
    expected_participant_ids: list[str] = Field(default_factory=list)
    # Camera/tuning samples on the monitor must not replace the group demo session.
    persist_live_metrics: bool = True


class DemoSeedRequest(BaseModel):
    session_id: str = Field(default=DEFAULT_SESSION_ID, min_length=1)
    frames: int = Field(default=12, ge=3, le=120)
    degraded: bool = False
    # group = 3 simulated students (healthy/cheating/silhouette). solo = 1 learner.
    scenario: DemoScenario = "group"


class DemoRollRequest(BaseModel):
    session_id: str = Field(default=DEFAULT_SESSION_ID, min_length=1)
    degraded: bool = False
    interval_s: float = Field(default=1.0, ge=0.2, le=5.0)
    scenario: DemoScenario = "group"


class BootParticipantRequest(BaseModel):
    session_id: str = Field(min_length=1)
    participant_id: str = Field(min_length=1)


class AlertAckRequest(BaseModel):
    session_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    participant_id: str = ""


class AlertActionRequest(BaseModel):
    session_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    action: str = ""
    participant_id: str = ""
    message: str = ""


class VoiceRequest(BaseModel):
    class_mode: ClassMode = ClassMode.SOLO
    learner_message: str = Field(min_length=1)
    language_code: str = Field(default="en", min_length=2, max_length=8)
    session_id: str = ""
    fast_mode: bool = True
    context: str = ""


class VoiceQuestionRequest(BaseModel):
    class_mode: ClassMode = ClassMode.SOLO
    language_code: str = Field(default="en", min_length=2, max_length=8)
    topic: str = Field(min_length=1)
    difficulty: str = Field(default="medium")
    context: str = ""


class AudioAnswerRequest(BaseModel):
    class_mode: ClassMode = ClassMode.SOLO
    language_code: str = Field(default="en", min_length=2, max_length=8)
    question: str = Field(min_length=1)
    audio_transcript: str = Field(min_length=1)
    expected_answer: str = ""
    context: str = ""


class ChallengeRequest(BaseModel):
    session_id: str = Field(min_length=1)
    mode: ClassMode = ClassMode.SOLO
    learning_prompt: str = Field(min_length=1)
    participant_ids: list[str] = Field(default_factory=list)
    preferred_game_type: WebcamGameType | None = None


class ChallengeAttemptRequest(BaseModel):
    challenge_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    mode: ClassMode = ClassMode.SOLO
    signals: list[WebcamSignal] = Field(default_factory=list)
    expected_participant_ids: list[str] = Field(default_factory=list)


def _js_string_literal(value: str) -> str:
    """Render a Python string as a JS literal that cannot break out of a <script> block."""
    encoded = json.dumps(value)
    for char, escape in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
        encoded = encoded.replace(char, escape)
    return encoded


class TuningPatchRequest(BaseModel):
    """Partial tuning update; omitted knobs keep their current value."""

    knobs: dict[str, float] = Field(default_factory=dict)


class ImagingAnalyzeRequest(BaseModel):
    luminance_grid: list[list[float]] = Field(min_length=3)


def _record_evaluation(
    *,
    session_id: str,
    evaluation: ClassEvaluation,
    updated_at_ms: int,
    mode: ClassMode,
    signals: list[WebcamSignal],
    expected_participant_ids: list[str],
    replace_latest: bool = False,
) -> None:
    _live_metrics_store.record(
        session_id=session_id,
        evaluation=evaluation,
        updated_at_ms=updated_at_ms,
        mode=mode,
        signals=signals,
        expected_participant_ids=expected_participant_ids,
        replace_latest=replace_latest,
    )


def _rescore_stored_sessions() -> dict[str, object]:
    """Re-run the last frame batch for every session under the active tuning.

    Without this, applying a room preset only moves the sliders — student windows
    and class gates stay frozen until the next evaluate post.
    """
    rescored: list[str] = []
    flag_counts: dict[str, int] = {}
    distance_samples: dict[str, float | None] = {}
    live_camera: dict[str, object] | None = None
    for session_id in list(_live_metrics_store.sessions_with_inputs()):
        batch = _live_metrics_store.stored_inputs(session_id)
        if batch is None:
            continue
        evaluation = _analyzer.evaluate(
            session_id=session_id,
            mode=batch.mode,
            signals=batch.signals,
            expected_participant_ids=batch.expected_participant_ids,
        )
        # Re-score updates charts only when this session already has a displayed
        # evaluation (demo / persisted live). Input-only camera caches still get
        # a fresh evaluation payload back to the monitor.
        if _live_metrics_store.has_evaluation(session_id):
            _record_evaluation(
                session_id=session_id,
                evaluation=evaluation,
                updated_at_ms=batch.updated_at_ms,
                mode=batch.mode,
                signals=batch.signals,
                expected_participant_ids=batch.expected_participant_ids,
                replace_latest=True,
            )
        else:
            _live_metrics_store.remember_inputs(
                session_id=session_id,
                mode=batch.mode,
                signals=batch.signals,
                expected_participant_ids=batch.expected_participant_ids,
                updated_at_ms=batch.updated_at_ms,
            )
        rescored.append(session_id)
        for key, count in evaluation.quality_summary.quality_flag_counts.items():
            flag_counts[key] = flag_counts.get(key, 0) + count
        for participant in evaluation.participants:
            distance_samples[f"{session_id}:{participant.participant_id}"] = (
                participant.distance_from_camera_m
            )
            if participant.participant_id == "camera-local" or session_id.endswith(
                "__livecam"
            ):
                live_camera = {
                    "session_id": session_id,
                    "participant_id": participant.participant_id,
                    "quality_flags": list(participant.quality_flags),
                    "light_quality_score": participant.light_quality_score,
                    "image_detection_quality_score": participant.image_detection_quality_score,
                    "sharpness_score": participant.sharpness_score,
                    "distance_from_camera_m": participant.distance_from_camera_m,
                    "distance_source": participant.distance_source,
                    "expression_behavior_score": participant.expression_behavior_score,
                    "microphone_quality_score": participant.microphone_quality_score,
                    "noise_filter_effectiveness_score": participant.noise_filter_effectiveness_score,
                    "dominant_expression": participant.dominant_expression,
                }
    return {
        "rescored_sessions": rescored,
        "quality_flag_counts": flag_counts,
        "distance_samples": distance_samples,
        "live_camera": live_camera,
        "active_tuning": _analyzer.tuning.to_dict(),
    }


def _knob_diff(before: dict[str, object], after: dict[str, object]) -> dict[str, list[object]]:
    changed: dict[str, list[object]] = {}
    for key, new_value in after.items():
        old_value = before.get(key)
        if old_value != new_value:
            changed[key] = [old_value, new_value]
    return changed


@app.get("/api/theodore/vision/tuning")
def get_vision_tuning() -> dict[str, object]:
    return {
        "knobs": _analyzer.tuning.to_dict(),
        "presets": sorted(PRESETS),
        "active_preset": getattr(_analyzer, "_active_preset_name", None),
        "env_prefix": "AOEP_VISION_",
    }


@app.patch("/api/theodore/vision/tuning")
def patch_vision_tuning(req: TuningPatchRequest) -> dict[str, object]:
    """Adjust recognition knobs live, without restarting the service."""
    before = _analyzer.tuning.to_dict()
    try:
        updated = _analyzer.tuning.patched(req.knobs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _analyzer.tuning = updated
    setattr(_analyzer, "_active_preset_name", None)
    rescore = _rescore_stored_sessions()
    return {
        "knobs": updated.to_dict(),
        "applied": sorted(req.knobs),
        "changed_knobs": _knob_diff(before, updated.to_dict()),
        **rescore,
    }


@app.post("/api/theodore/vision/tuning/preset/{name}")
def apply_vision_preset(name: str) -> dict[str, object]:
    before = _analyzer.tuning.to_dict()
    try:
        preset = VisionTuning.preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _analyzer.tuning = preset
    preset_name = name.strip().lower()
    setattr(_analyzer, "_active_preset_name", preset_name)
    rescore = _rescore_stored_sessions()
    return {
        "preset": preset_name,
        "knobs": preset.to_dict(),
        "changed_knobs": _knob_diff(before, preset.to_dict()),
        **rescore,
    }


@app.get("/api/theodore/vision/policy")
def get_vision_policy() -> dict[str, object]:
    from dataclasses import asdict

    return {
        "knobs": asdict(_analyzer.policy),
        "env_prefix": "AOEP_VISION_",
        "note": "Timing/session caps only. Detection thresholds live under Vision tuning.",
    }


@app.patch("/api/theodore/vision/policy")
def patch_vision_policy(req: TuningPatchRequest) -> dict[str, object]:
    """Adjust analyzer timing knobs (grace windows, session caps) live."""
    from dataclasses import asdict, fields, replace

    before = asdict(_analyzer.policy)
    allowed = {item.name for item in fields(AnalyzerPolicy)}
    unknown = sorted(set(req.knobs) - allowed)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown policy knobs: {unknown}")
    coerced = {key: int(round(float(value))) for key, value in req.knobs.items()}
    try:
        updated = replace(_analyzer.policy, **coerced)
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _analyzer.policy = updated
    rescore = _rescore_stored_sessions()
    after = asdict(updated)
    return {
        "knobs": after,
        "applied": sorted(req.knobs),
        "changed_knobs": _knob_diff(before, after),
        **rescore,
    }


@app.get("/api/theodore/voice/tuning")
def get_voice_tuning() -> dict[str, object]:
    return {
        "knobs": _voice_agent.tuning.to_dict(),
        "presets": sorted(VOICE_PRESETS),
        "env_prefix": "XAI_TUNE_",
        "model": {"fast": _voice_agent.fast_model, "full": _voice_agent.model},
    }


@app.patch("/api/theodore/voice/tuning")
def patch_voice_tuning(req: TuningPatchRequest) -> dict[str, object]:
    """Adjust xAI generation/latency knobs live, without restarting the service."""
    try:
        updated = _voice_agent.tuning.patched(req.knobs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _voice_agent.tuning = updated
    return {"knobs": updated.to_dict(), "applied": sorted(req.knobs)}


@app.post("/api/theodore/voice/tuning/preset/{name}")
def apply_voice_preset(name: str) -> dict[str, object]:
    try:
        preset = VoiceTuning.preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _voice_agent.tuning = preset
    return {"preset": name.strip().lower(), "knobs": preset.to_dict()}


@app.get("/api/theodore/responsiveness/tuning")
def get_responsiveness_tuning() -> dict[str, object]:
    return {
        "knobs": _responsiveness.to_dict(),
        "presets": sorted(RESP_PRESETS),
        "active_preset": _responsiveness_preset_name,
        "env_prefix": "AOEP_RESP_",
        "knob_count": len(_responsiveness.to_dict()),
    }


@app.patch("/api/theodore/responsiveness/tuning")
def patch_responsiveness_tuning(req: TuningPatchRequest) -> dict[str, object]:
    global _responsiveness, _responsiveness_preset_name
    before = _responsiveness.to_dict()
    try:
        updated = _responsiveness.patched(req.knobs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _responsiveness = updated
    _responsiveness_preset_name = None
    return {
        "knobs": updated.to_dict(),
        "applied": sorted(req.knobs),
        "changed_knobs": _knob_diff(before, updated.to_dict()),
        "knob_count": len(updated.to_dict()),
    }


@app.post("/api/theodore/responsiveness/tuning/preset/{name}")
def apply_responsiveness_preset(name: str) -> dict[str, object]:
    global _responsiveness, _responsiveness_preset_name
    before = _responsiveness.to_dict()
    try:
        preset = ResponsivenessTuning.preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _responsiveness = preset
    _responsiveness_preset_name = name.strip().lower()
    return {
        "preset": _responsiveness_preset_name,
        "knobs": preset.to_dict(),
        "changed_knobs": _knob_diff(before, preset.to_dict()),
        "knob_count": len(preset.to_dict()),
    }


@app.get("/api/theodore/quality/inventory")
def quality_inventory() -> dict[str, object]:
    """Catalog of knobs + telemetry surfaces for world-class lab QA."""
    vision = _analyzer.tuning.to_dict()
    voice = _voice_agent.tuning.to_dict()
    resp = _responsiveness.to_dict()
    return {
        "vision_knob_count": len(vision),
        "voice_knob_count": len(voice),
        "responsiveness_knob_count": len(resp),
        "total_knob_count": len(vision) + len(voice) + len(resp),
        "vision_knobs": sorted(vision),
        "voice_knobs": sorted(voice),
        "responsiveness_knobs": sorted(resp),
        "telemetry_surfaces": [
            "live_session_metrics.observatory_summary",
            "live_session_metrics.quality_summary",
            "live_session_metrics.participant_series",
            "class_evaluation.quality_summary",
            "advanced_behavior_snapshot",
        ],
    }


@app.post("/api/theodore/vision/imaging/analyze")
def analyze_imaging(req: ImagingAnalyzeRequest) -> dict[str, object]:
    """Run Sobel edge + exposure analysis on a luminance grid using active tuning."""
    try:
        analysis = analyze_luminance_grid(req.luminance_grid, tuning=_analyzer.tuning)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "width": analysis.width,
        "height": analysis.height,
        "backend": analysis.backend,
        "mean_luminance": analysis.mean_luminance,
        "underexposed_ratio": analysis.underexposed_ratio,
        "overexposed_ratio": analysis.overexposed_ratio,
        "mean_gradient": analysis.mean_gradient,
        "percentile_gradient": analysis.percentile_gradient,
        "edge_density": analysis.edge_density,
        "sharpness_score": analysis.sharpness_score,
        "light_quality_score": analysis.light_quality_score,
        "blurry": analysis.blurry,
        "low_edge_detail": analysis.low_edge_detail,
        "underexposed": analysis.underexposed,
        "overexposed": analysis.overexposed,
        "flags": analysis.flags,
        "signal_fields": analysis.to_signal_fields(),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "theodore-webcam-lab", "status": "ok"}


@app.post("/admin/shutdown")
def shutdown() -> dict[str, str]:
    """Gracefully stop the server so the port is freed. Useful when closing the lab."""
    threading.Thread(target=lambda: (time.sleep(0.15), os.kill(os.getpid(), _signal.SIGTERM)), daemon=True).start()
    return {"status": "shutting_down"}


@app.post("/api/theodore/webcam/session/boot-participant")
def boot_participant(req: BootParticipantRequest) -> dict[str, object]:
    """Remove a participant from the session. Future signals from them are ignored."""
    _analyzer.boot_participant(session_id=req.session_id, participant_id=req.participant_id)
    _live_metrics_store.boot_participant(session_id=req.session_id, participant_id=req.participant_id)
    return {"session_id": req.session_id, "participant_id": req.participant_id, "booted": True}


@app.get("/api/theodore/voice/languages", response_model=list[SupportedLanguage])
def voice_languages() -> list[SupportedLanguage]:
    return _voice_agent.supported_languages()


@app.get("/api/theodore/voice/status")
def voice_status() -> dict[str, object]:
    """Show whether xAI is wired and how many teaching languages are available."""
    has_key = bool(getattr(_voice_agent, "_api_key", "") or "")
    return {
        "service": "theodore-voice-agent",
        "provider": "xai" if has_key else "local-fallback",
        "xai_api_key_configured": has_key,
        "model": _voice_agent.model,
        "fast_model": _voice_agent.fast_model,
        "languages": len(_voice_agent.supported_languages()),
        "tts_engine_chain": ["elevenlabs", "edge-tts", "device"],
        "note": (
            "xAI Grok generates the reply text; spoken audio uses the browser/device "
            "voice (or a speech gateway when configured). Set XAI_API_KEY for live xAI."
            if not has_key
            else "xAI Grok is live for replies; spoken audio uses device/edge/ElevenLabs TTS."
        ),
    }


@app.post("/api/theodore/webcam/evaluate", response_model=ClassEvaluation)
def evaluate_webcam(req: WebcamEvaluationRequest) -> ClassEvaluation:
    evaluation = _analyzer.evaluate(
        session_id=req.session_id,
        mode=req.mode,
        signals=req.signals,
        expected_participant_ids=req.expected_participant_ids,
    )
    updated_at_ms = max([item.timestamp_ms for item in req.signals], default=0)
    # Always keep the last frame for tuning re-score — even when the live camera
    # path opts out of overwriting the group-demo student windows.
    _live_metrics_store.remember_inputs(
        session_id=req.session_id,
        mode=req.mode,
        signals=req.signals,
        expected_participant_ids=req.expected_participant_ids,
        updated_at_ms=updated_at_ms,
    )
    if req.persist_live_metrics:
        _record_evaluation(
            session_id=req.session_id,
            evaluation=evaluation,
            updated_at_ms=updated_at_ms,
            mode=req.mode,
            signals=req.signals,
            expected_participant_ids=req.expected_participant_ids,
        )
    return evaluation


def _apply_demo_frame(
    *, session_id: str, step: int, degraded: bool, scenario: DemoScenario = "group"
) -> ClassEvaluation:
    payload = build_demo_payload(
        session_id=session_id, step=step, degraded=degraded, scenario=scenario
    )
    signals = [WebcamSignal.model_validate(item) for item in payload["signals"]]
    expected = list(payload["expected_participant_ids"])
    mode = ClassMode.SOLO if payload.get("mode") == "solo" else ClassMode.GROUP
    evaluation = _analyzer.evaluate(
        session_id=session_id,
        mode=mode,
        signals=signals,
        expected_participant_ids=expected,
    )
    updated_at_ms = max((item.timestamp_ms for item in signals), default=0)
    _record_evaluation(
        session_id=session_id,
        evaluation=evaluation,
        updated_at_ms=updated_at_ms,
        mode=mode,
        signals=signals,
        expected_participant_ids=expected,
    )
    return evaluation


@app.post("/api/theodore/webcam/demo/seed")
def seed_demo_session(req: DemoSeedRequest) -> dict[str, object]:
    """Populate the live monitor with solo (1) or group (3) demo windows."""
    evaluation = None
    for step in range(req.frames):
        evaluation = _apply_demo_frame(
            session_id=req.session_id,
            step=step,
            degraded=req.degraded,
            scenario=req.scenario,
        )
    assert evaluation is not None
    return {
        "session_id": req.session_id,
        "frames": req.frames,
        "scenario": req.scenario,
        "mode": evaluation.mode.value,
        "participant_ids": [p.participant_id for p in evaluation.participants],
        "cheating_participant_ids": evaluation.suspected_cheating_participant_ids,
        "silhouette_participant_ids": evaluation.silhouette_participant_ids,
        "lesson_alert_codes": [alert.code for alert in evaluation.lesson_alerts],
        "monitor_path": f"/theodore/webcam/live-monitor/{req.session_id}",
    }


def _demo_roll_worker(
    session_id: str,
    degraded: bool,
    interval_s: float,
    stop: threading.Event,
    scenario: DemoScenario = "group",
) -> None:
    step = 0
    while not stop.is_set():
        try:
            _apply_demo_frame(
                session_id=session_id, step=step, degraded=degraded, scenario=scenario
            )
        except Exception:  # noqa: BLE001 - keep the roller alive across transient errors
            pass
        step += 1
        stop.wait(interval_s)


@app.post("/api/theodore/webcam/demo/roll/start")
def start_demo_roll(req: DemoRollRequest) -> dict[str, object]:
    with _demo_roll_lock:
        existing = _demo_roll_stop.get(req.session_id)
        if existing is not None and not existing.is_set():
            return {"session_id": req.session_id, "rolling": True, "already_running": True}
        stop = threading.Event()
        _demo_roll_stop[req.session_id] = stop
        thread = threading.Thread(
            target=_demo_roll_worker,
            args=(req.session_id, req.degraded, req.interval_s, stop, req.scenario),
            name=f"demo-roll-{req.session_id}",
            daemon=True,
        )
        thread.start()
    return {
        "session_id": req.session_id,
        "rolling": True,
        "already_running": False,
        "scenario": req.scenario,
    }


@app.post("/api/theodore/webcam/demo/roll/stop")
def stop_demo_roll(req: DemoRollRequest) -> dict[str, object]:
    with _demo_roll_lock:
        stop = _demo_roll_stop.get(req.session_id)
        if stop is not None:
            stop.set()
    return {"session_id": req.session_id, "rolling": False}


@app.post("/api/theodore/webcam/alerts/acknowledge")
def acknowledge_lesson_alert(req: AlertAckRequest) -> dict[str, object]:
    keys = _live_metrics_store.acknowledge_alert(
        session_id=req.session_id,
        code=req.code,
        participant_id=req.participant_id,
    )
    return {
        "session_id": req.session_id,
        "acknowledged_alert_keys": keys,
        "action_taken": True,
    }


@app.post("/api/theodore/webcam/alerts/action")
def run_lesson_alert_action(req: AlertActionRequest) -> dict[str, object]:
    """Execute the lesson alert action (private message, rejoin, game, watchlist)."""
    result = _lesson_actions.execute(
        session_id=req.session_id,
        code=req.code,
        action=req.action,
        participant_id=req.participant_id,
        message=req.message,
        game_engine=_game_engine,
    )
    keys = _live_metrics_store.acknowledge_alert(
        session_id=req.session_id,
        code=req.code,
        participant_id=req.participant_id,
    )
    return {
        "ok": result.ok,
        "summary": result.summary,
        "action": result.action,
        "code": result.code,
        "participant_id": result.participant_id,
        "details": result.details,
        "acknowledged_alert_keys": keys,
    }


@app.get(
    "/api/theodore/webcam/live-metrics/{session_id}",
    response_model=LiveSessionMetricsResponse,
)
def live_metrics(session_id: str) -> LiveSessionMetricsResponse:
    try:
        snap = _live_metrics_store.snapshot(session_id)
    except KeyError:
        # The monitor polls this every second from page load, before any frame
        # exists. An empty snapshot keeps that idle state out of the error log.
        return LiveSessionMetricsResponse(
            session_id=session_id,
            updated_at_ms=0,
            mode=ClassMode.SOLO,
        )
    return snap.model_copy(
        update={
            "action_log": _lesson_actions.events(session_id),
            "private_messages": _lesson_actions.private_messages(session_id),
            "watchlist": _lesson_actions.watchlist(session_id),
            "rejoin_requests": _lesson_actions.rejoin_requests(session_id),
        }
    )


@app.get("/theodore/webcam/live-monitor/{session_id}", response_class=HTMLResponse)
def live_monitor_page(
    session_id: str = Path(min_length=1, max_length=256),
) -> HTMLResponse:
    safe_title = html.escape(session_id)
    # Tell the page whether /vendor/vision is actually mounted. When it is not,
    # the client must not try the self-hosted path first (it would 404 and delay
    # the CDN load of the face mesh, blanking the contours and mood cards).
    local_assets = "true" if os.path.isdir(VISION_ASSET_DIR) else "false"
    return HTMLResponse(
        _MONITOR_PAGE_TEMPLATE.replace("__SESSION_TITLE__", safe_title)
        .replace("__SESSION_ID_JSON__", _js_string_literal(session_id))
        .replace("__VISION_LOCAL_ASSETS__", local_assets)
    )


@app.post(
    "/api/theodore/webcam/games/challenge",
    response_model=WebcamLearningChallenge,
)
def create_challenge(req: ChallengeRequest) -> WebcamLearningChallenge:
    return _game_engine.create_challenge(
        session_id=req.session_id,
        mode=req.mode,
        learning_prompt=req.learning_prompt,
        participant_ids=req.participant_ids,
        preferred_game_type=req.preferred_game_type,
    )


@app.post(
    "/api/theodore/webcam/games/attempt",
    response_model=WebcamGameResult,
)
def attempt_challenge(req: ChallengeAttemptRequest) -> WebcamGameResult:
    try:
        return _game_engine.score_attempt(
            challenge_id=req.challenge_id,
            session_id=req.session_id,
            mode=req.mode,
            signals=req.signals,
            expected_participant_ids=req.expected_participant_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/theodore/voice/respond", response_model=VoiceResponse)
def voice_respond(req: VoiceRequest) -> VoiceResponse:
    try:
        return _voice_agent.respond(
            learner_message=req.learner_message,
            class_mode=req.class_mode,
            language_code=req.language_code,
            session_id=req.session_id,
            fast_mode=req.fast_mode,
            context=req.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/theodore/voice/ask-question", response_model=VoiceQuestion)
def voice_ask_question(req: VoiceQuestionRequest) -> VoiceQuestion:
    try:
        return _voice_agent.ask_question(
            class_mode=req.class_mode,
            language_code=req.language_code,
            topic=req.topic,
            difficulty=req.difficulty,
            context=req.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/api/theodore/voice/absorb-audio-answer",
    response_model=AudioAnswerAssessment,
)
def voice_absorb_audio_answer(req: AudioAnswerRequest) -> AudioAnswerAssessment:
    try:
        return _voice_agent.absorb_audio_answer(
            class_mode=req.class_mode,
            language_code=req.language_code,
            question=req.question,
            audio_transcript=req.audio_transcript,
            expected_answer=req.expected_answer,
            context=req.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
