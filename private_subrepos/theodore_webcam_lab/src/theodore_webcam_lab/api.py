from __future__ import annotations

from fastapi import FastAPI

from .models import (
    MonitoringDecision,
    VoiceAgentRequest,
    VoiceAgentResponse,
    WebcamFrameInput,
)
from .monitor import WebcamSessionMonitor
from .voice import XaiVoiceAgent, XaiVoiceConfig


def create_app(
    *,
    monitor: WebcamSessionMonitor | None = None,
    voice_agent: XaiVoiceAgent | None = None,
) -> FastAPI:
    monitor_impl = monitor or WebcamSessionMonitor()
    voice_impl = voice_agent or XaiVoiceAgent(XaiVoiceConfig.from_env())

    app = FastAPI(
        title="Theodore Webcam Lab",
        version="0.1.0",
        description=(
            "Private lab API for webcam recognition experiments in solo/group classes."
        ),
    )

    @app.post("/lab/session/analyze", response_model=MonitoringDecision)
    def analyze_session(frame: WebcamFrameInput) -> MonitoringDecision:
        decision = monitor_impl.analyze(frame)
        codes = [event.code for event in decision.events]
        if codes:
            voice = voice_impl.respond(
                VoiceAgentRequest(
                    session_id=frame.session_id,
                    class_mode=frame.class_mode,
                    recent_event_codes=codes,
                    student_message="Respond as Theodore for the current webcam event state.",
                )
            )
            decision.teacher_prompt = voice.text
            decision.voice_engine = voice.engine
            decision.voice_fallback = voice.used_fallback
        return decision

    @app.post("/lab/voice/respond", response_model=VoiceAgentResponse)
    def voice_respond(request: VoiceAgentRequest) -> VoiceAgentResponse:
        return voice_impl.respond(request)

    @app.get("/lab/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
