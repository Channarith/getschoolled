from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from .games import WebcamLearningGameEngine
from .types import (
    ClassEvaluation,
    ClassMode,
    VoiceResponse,
    WebcamGameResult,
    WebcamGameType,
    WebcamLearningChallenge,
    WebcamSignal,
)
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
_game_engine = WebcamLearningGameEngine(_analyzer)
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
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/theodore/voice/respond", response_model=VoiceResponse)
def voice_respond(req: VoiceRequest) -> VoiceResponse:
    return _voice_agent.respond(
        learner_message=req.learner_message,
        class_mode=req.class_mode,
        context=req.context,
    )
