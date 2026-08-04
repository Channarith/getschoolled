from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from .types import ClassEvaluation, ClassMode, VoiceResponse, WebcamSignal
from .voice_agents import XaiVoiceAgent

app = FastAPI(
    title="Theodore Webcam Lab",
    version="0.1.0",
    description=(
        "Private-ready sandbox for Theodore webcam image recognition "
        "and xAI-backed natural responses."
    ),
)

_analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy())
_voice_agent = XaiVoiceAgent.from_env()


class WebcamEvaluationRequest(BaseModel):
    session_id: str = Field(min_length=1)
    mode: ClassMode = ClassMode.SOLO
    signals: list[WebcamSignal] = Field(default_factory=list)
    expected_participant_ids: list[str] = Field(default_factory=list)


class VoiceRequest(BaseModel):
    class_mode: ClassMode = ClassMode.SOLO
    learner_message: str = Field(min_length=1)
    context: str = ""


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "theodore-webcam-lab", "status": "ok"}


@app.post("/api/theodore/webcam/evaluate", response_model=ClassEvaluation)
def evaluate_webcam(req: WebcamEvaluationRequest) -> ClassEvaluation:
    return _analyzer.evaluate(
        session_id=req.session_id,
        mode=req.mode,
        signals=req.signals,
        expected_participant_ids=req.expected_participant_ids,
    )


@app.post("/api/theodore/voice/respond", response_model=VoiceResponse)
def voice_respond(req: VoiceRequest) -> VoiceResponse:
    return _voice_agent.respond(
        learner_message=req.learner_message,
        class_mode=req.class_mode,
        context=req.context,
    )
