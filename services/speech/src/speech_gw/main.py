"""Speech gateway FastAPI app.

Exposes language coverage and the TTS engine-routing decision (native XTTS vs
cloud-TTS fallback). Actual ASR/MT/TTS inference is delegated to the
SpeechProvider, which requires loaded models and is therefore not exercised by
the offline tests.
"""

from __future__ import annotations

from aoep_shared.languages import SUPPORTED_LANGUAGES
from aoep_shared.service import create_service
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
