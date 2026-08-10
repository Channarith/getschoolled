"""FastAPI entrypoint for Theodore Audio Translation Lab."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from .audio_policy import AudioPolicy
from .languages import (
    AUTO_LANGUAGE,
    SOURCE,
    language_rows,
    normalize_input_language,
)
from .models import AudienceRole, SessionConfig, SessionUpdate, TranscriptInput
from .providers import ASREngine, ProviderUnavailable, provider_status
from .sessions import TranslationHub
from .studio_page import render_lab_page

app = FastAPI(
    title="Theodore Audio Translation Lab",
    description=(
        "Realtime webcam/microphone speech transcription and translation for "
        "Theodore, teachers, and customer viewers."
    ),
    version="0.1.0",
)

hub = TranslationHub()
asr = ASREngine()


@app.get("/health")
def health() -> dict[str, Any]:
    status = provider_status()
    return {
        "service": "theodore-audio-translation-lab",
        "status": "ok",
        "languages": len(language_rows()),
        "language_source": SOURCE,
        "providers": status.model_dump(mode="json"),
        "privacy": "ephemeral audio; raw microphone chunks are not persisted",
    }


@app.get("/", response_class=HTMLResponse)
@app.get("/lab", response_class=HTMLResponse)
def lab() -> HTMLResponse:
    return HTMLResponse(render_lab_page())


@app.get("/api/languages")
def languages() -> dict[str, Any]:
    rows = language_rows()
    return {"count": len(rows), "languages": rows, "source": SOURCE}


@app.get("/api/providers")
def providers() -> dict[str, Any]:
    return provider_status().model_dump(mode="json")


@app.get("/api/audio-policy")
def audio_policy() -> dict[str, Any]:
    return AudioPolicy.from_env().public_dict()


@app.post("/api/sessions")
async def create_session(config: SessionConfig) -> dict[str, Any]:
    try:
        snapshot = await hub.create(config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return snapshot.model_dump(mode="json")


@app.patch("/api/sessions/{session_id}")
async def update_session(session_id: str, update: SessionUpdate) -> dict[str, Any]:
    try:
        snapshot = await hub.configure(session_id, update)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="translation session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return snapshot.model_dump(mode="json")


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    snapshot = await hub.snapshot(session_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="translation session not found")
    return snapshot.model_dump(mode="json")


@app.post("/api/sessions/{session_id}/transcript")
async def submit_transcript(
    session_id: str,
    item: TranscriptInput,
) -> dict[str, Any]:
    try:
        events = await hub.process_transcript(session_id, item)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"events": [event.model_dump(mode="json") for event in events]}


@app.post("/api/sessions/{session_id}/audio")
async def submit_audio(
    session_id: str,
    audio: Annotated[UploadFile, File()],
    source_language: Annotated[str, Form()] = "en",
    speaker_id: Annotated[str, Form()] = "learner",
) -> dict[str, Any]:
    source = normalize_input_language(source_language)
    if not source:
        raise HTTPException(status_code=422, detail="unsupported source language")
    if source == AUTO_LANGUAGE and not asr.configured:
        raise HTTPException(
            status_code=503,
            detail="Auto-detect requires server Whisper; configure ASR_BASE_URL.",
        )
    payload = await audio.read()
    try:
        transcript = await __import__("asyncio").to_thread(
            asr.transcribe,
            payload,
            filename=audio.filename or "audio.webm",
            content_type=audio.content_type or "audio/webm",
            language=source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — provider/network boundary
        raise HTTPException(status_code=502, detail=f"ASR failed: {exc}") from exc

    item = TranscriptInput(
        text=transcript.text,
        source_language=transcript.language,
        is_final=True,
        confidence=transcript.confidence,
        asr_provider=transcript.provider,
        speaker_id=speaker_id,
    )
    events = await hub.process_transcript(session_id, item)
    return {
        "transcript": transcript.model_dump(mode="json"),
        "events": [event.model_dump(mode="json") for event in events],
    }


@app.websocket("/ws/sessions/{session_id}")
async def session_socket(
    websocket: WebSocket,
    session_id: str,
) -> None:
    await websocket.accept()
    raw_role = websocket.query_params.get("role", "viewer")
    target = websocket.query_params.get("target", "en")
    source = websocket.query_params.get("source", "en")
    participant_id = websocket.query_params.get("participant", "guest")
    try:
        role = AudienceRole(raw_role)
        conn = await hub.register(
            session_id,
            websocket,
            role=role,
            target_language=target,
            participant_id=participant_id,
            source_language=source,
        )
    except (ValueError, ValidationError) as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})
        await websocket.close(code=1008)
        return

    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type", "transcript")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if msg_type != "transcript":
                await websocket.send_json(
                    {"type": "error", "detail": f"unsupported message type: {msg_type}"}
                )
                continue
            try:
                item = TranscriptInput.model_validate(
                    {
                        **message,
                        "source_language": message.get("source_language") or source,
                        "speaker_id": message.get("speaker_id") or participant_id,
                    }
                )
                await hub.process_transcript(session_id, item)
            except (ValueError, ValidationError) as exc:
                await websocket.send_json({"type": "error", "detail": str(exc)})
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unregister(session_id, conn)
