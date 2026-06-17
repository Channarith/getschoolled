"""Speech gateway service.

Phase2 adds streaming ASR, language ID, NLLB translation, and multilingual TTS.
This skeleton exposes /health and a TTS stub routed through the SpeechProvider
selected by config (local = Whisper/XTTS, cloud = GPU pods).
"""

from __future__ import annotations

from pydantic import BaseModel

from eduplatform_shared.factory import get_provider_factory
from eduplatform_shared.service import create_service_app

app = create_service_app("speech")


class SynthRequest(BaseModel):
    text: str
    language: str = "en"
    voice: str = "default"


class SynthResponse(BaseModel):
    bytes_len: int
    language: str


@app.post("/api/tts", response_model=SynthResponse)
def tts(req: SynthRequest) -> SynthResponse:
    provider = get_provider_factory().speech()
    audio = provider.synthesize(req.text, language=req.language, voice=req.voice)
    return SynthResponse(bytes_len=len(audio), language=req.language)
