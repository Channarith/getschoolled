"""Speech gateway FastAPI app.

Exposes language coverage and the TTS engine-routing decision (native XTTS vs
cloud-TTS fallback). Actual ASR/MT/TTS inference is delegated to the
SpeechProvider, which requires loaded models and is therefore not exercised by
the offline tests.
"""

from __future__ import annotations

from aoep_shared.languages import SUPPORTED_LANGUAGES
from aoep_shared.service import create_service
from aoep_shared.translation import is_pair_supported, plan_delivery
from fastapi import HTTPException
from pydantic import BaseModel

app = create_service("speech")


class LanguagesResponse(BaseModel):
    languages: list[str]
    count: int


class TtsEngineResponse(BaseModel):
    language: str
    engine: str


@app.get("/languages", response_model=LanguagesResponse)
def languages() -> LanguagesResponse:
    return LanguagesResponse(
        languages=list(SUPPORTED_LANGUAGES), count=len(SUPPORTED_LANGUAGES)
    )


@app.get("/tts/engine", response_model=TtsEngineResponse)
def tts_engine(language: str) -> TtsEngineResponse:
    provider = app.state.factory.speech()
    return TtsEngineResponse(language=language, engine=provider.tts_engine(language))


# --------------------------------------------------------------------------- #
# Phase 2 - multilingual delivery routing + translation
# --------------------------------------------------------------------------- #
class StudentLang(BaseModel):
    student_id: str
    language: str


class DeliveryPlanRequest(BaseModel):
    lesson_language: str = "en"
    students: list[StudentLang] = []


class DeliveryPlanItem(BaseModel):
    student_id: str
    language: str
    supported: bool
    translate: bool
    translation_supported: bool
    tts_engine: str


class DeliveryPlanResponse(BaseModel):
    lesson_language: str
    plans: list[DeliveryPlanItem]


@app.post("/delivery/plan", response_model=DeliveryPlanResponse)
def delivery_plan(req: DeliveryPlanRequest) -> DeliveryPlanResponse:
    try:
        plans = plan_delivery(
            req.lesson_language, [(s.student_id, s.language) for s in req.students]
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return DeliveryPlanResponse(
        lesson_language=req.lesson_language,
        plans=[DeliveryPlanItem(**p.__dict__) for p in plans],
    )


class TranslateRequest(BaseModel):
    text: str
    source: str
    target: str


@app.post("/translate")
def translate(req: TranslateRequest) -> dict:
    if not is_pair_supported(req.source, req.target):
        raise HTTPException(
            status_code=422,
            detail=f"unsupported language pair {req.source}->{req.target}",
        )
    provider = app.state.factory.speech()
    try:
        translated = provider.translate(req.text, source=req.source, target=req.target)
    except NotImplementedError as exc:
        # Pair is valid; the NLLB model just isn't loaded in this environment.
        raise HTTPException(status_code=503, detail=str(exc))
    return {"source": req.source, "target": req.target, "text": translated}
