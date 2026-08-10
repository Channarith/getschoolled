"""Wire models for realtime audio translation sessions."""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .languages import normalize_language


class AudienceRole(str, Enum):
    SPEAKER = "speaker"
    THEODORE = "theodore"
    TEACHER = "teacher"
    CUSTOMER = "customer"
    VIEWER = "viewer"


class SessionConfig(BaseModel):
    session_id: str = Field(default_factory=lambda: f"audio-{uuid.uuid4().hex[:10]}")
    source_language: str = "en"
    target_languages: list[str] = Field(default_factory=lambda: ["en"])
    translate_interim: bool = False
    max_history: int = Field(default=200, ge=10, le=2000)

    def normalized(self) -> "SessionConfig":
        source = normalize_language(self.source_language)
        if not source:
            raise ValueError(f"unsupported source language: {self.source_language}")
        targets: list[str] = []
        for raw in self.target_languages:
            code = normalize_language(raw)
            if not code:
                raise ValueError(f"unsupported target language: {raw}")
            if code not in targets:
                targets.append(code)
        if not targets:
            raise ValueError("at least one target language is required")
        return self.model_copy(update={"source_language": source, "target_languages": targets})


class TranscriptInput(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    source_language: str = ""
    is_final: bool = True
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    asr_provider: str = "browser-speech-recognition"
    speaker_id: str = "learner"
    timestamp_ms: int = Field(default_factory=lambda: int(time.time() * 1000))


class TranslationResult(BaseModel):
    text: str
    source_language: str
    target_language: str
    provider: str
    translated: bool
    warning: str = ""
    latency_ms: int = 0


class TranslationEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    session_id: str
    sequence: int
    speaker_id: str = "learner"
    source_text: str
    source_language: str
    target_language: str
    translated_text: str
    is_final: bool = True
    confidence: float = 0.0
    asr_provider: str = ""
    translation_provider: str = ""
    warning: str = ""
    created_at_ms: int = Field(default_factory=lambda: int(time.time() * 1000))
    latency_ms: int = 0


class SessionSnapshot(BaseModel):
    config: SessionConfig
    connected: dict[str, int] = Field(default_factory=dict)
    history: list[TranslationEvent] = Field(default_factory=list)
    sequence: int = 0
    created_at_ms: int = Field(default_factory=lambda: int(time.time() * 1000))


class ProviderStatus(BaseModel):
    browser_asr: bool = True
    remote_asr_configured: bool = False
    remote_asr_url: str = ""
    translation_gateway_configured: bool = False
    translation_gateway_url: str = ""
    xai_translation_configured: bool = False
    offline_phrasebook: bool = True
    notes: list[str] = Field(default_factory=list)


class AudioTranscription(BaseModel):
    text: str
    language: str
    confidence: float = 0.0
    provider: str
    duration_ms: int = 0
    raw: dict[str, Any] = Field(default_factory=dict)
