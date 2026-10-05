"""FastAPI entrypoint for Theodore Audio Translation Lab."""

from __future__ import annotations


# Load config/local.env so XAI_API_KEY / ELEVENLABS_API_KEY / SPEECH_BASE_URL
# work without a manual `set -a; . config/local.env` in every shell.
try:
    from aoep_shared.env_bootstrap import ensure_lab_env

    ensure_lab_env()
except Exception:  # noqa: BLE001 — labs must still boot offline / without shared
    pass


from typing import Annotated, Any

from aoep_shared.live_audio_agents import inject_client, install_live_audio_routes
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError

from .audio_policy import get_policy, patch_policy, reset_policy
from .languages import (
    AUTO_LANGUAGE,
    SOURCE,
    language_rows,
    normalize_input_language,
)
from .models import (
    AudienceRole,
    SessionConfig,
    SessionUpdate,
    TheodoreMode,
    TheodoreReplyRequest,
    TranscriptInput,
)
from .providers import ASREngine, ProviderUnavailable, provider_status
from .quality_telemetry import get_store
from .sessions import TranslationHub
from .studio_page import render_lab_page
from . import tts as tts_module

app = FastAPI(
    title="Theodore Audio Translation Lab",
    description=(
        "Realtime webcam/microphone speech transcription and translation for "
        "Theodore, teachers, and customer viewers."
    ),
    version="0.1.0",
)
install_live_audio_routes(app, lab_name="Theodore Audio Translation Lab")

hub = TranslationHub()
asr = ASREngine()


@app.get("/health")
def health() -> dict[str, Any]:
    status = provider_status()
    readiness: dict[str, Any] = {}
    try:
        from aoep_shared.env_bootstrap import speech_readiness

        readiness = speech_readiness()
    except Exception:  # noqa: BLE001
        pass
    return {
        "service": "theodore-audio-translation-lab",
        "status": "ok",
        "languages": len(language_rows()),
        "language_source": SOURCE,
        "providers": status.model_dump(mode="json"),
        "privacy": "ephemeral audio; raw microphone chunks are not persisted",
        "speech": tts_module.tts_status(),
        **readiness,
    }


@app.get("/", response_class=HTMLResponse)
@app.get("/lab", response_class=HTMLResponse)
def lab() -> HTMLResponse:
    return HTMLResponse(inject_client(render_lab_page()))


@app.get("/api/languages")
def languages() -> dict[str, Any]:
    rows = language_rows()
    return {"count": len(rows), "languages": rows, "source": SOURCE}


@app.get("/api/providers")
def providers() -> dict[str, Any]:
    return provider_status().model_dump(mode="json")


@app.get("/api/theodore/status")
def theodore_status() -> dict[str, Any]:
    return {
        "live_xai_configured": hub.theodore.live_configured,
        # Naming the model matters: a retired slug is the most common cause of a
        # blanket xAI 400, and the operator cannot see XAI_MODEL from the browser.
        "xai_model": hub.theodore.model,
        "languages": len(language_rows()),
        "modes": [mode.value for mode in TheodoreMode],
        "speech": tts_module.tts_status(),
        "fallback": (
            "English teaching template translated by NLLB/xAI when available; "
            "otherwise honest English fallback"
        ),
    }


@app.get("/api/tts/status")
def speech_status() -> dict[str, Any]:
    """Probed once by the page so it knows whether to expect server audio."""
    return tts_module.tts_status()


@app.get("/api/tts")
@app.post("/api/tts")
def speak(text: str = "", language: str = "en", style: str = "warm") -> Response:
    """Render Theodore's words to audio.

    GET as well as POST because ``<audio src=...>`` and mobile players can only
    load a URI. Returns 501 (not 500) when nothing is configured so the client can
    tell "speak it yourself" apart from a real failure.
    """
    try:
        audio, mime, engine = tts_module.synthesize(text, language=language, style=style)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except tts_module.ProviderUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return Response(
        content=audio,
        media_type=mime,
        headers={
            "X-TTS-Engine": engine,
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/audio-policy")
def audio_policy() -> dict[str, Any]:
    return get_policy().public_dict()


@app.patch("/api/audio-policy")
def update_audio_policy(overrides: dict[str, Any]) -> dict[str, Any]:
    """Live-tune capture/gate/latency knobs. Unknown keys are ignored.

    Send `{"reset": true}` (or an empty body) semantics: an explicit reset flag
    reloads defaults from the environment before applying any other overrides.
    """
    body = dict(overrides or {})
    if body.pop("reset", False):
        reset_policy()
    if body:
        patch_policy(body)
    return get_policy().public_dict()


@app.get("/api/telemetry/overview")
def telemetry_overview() -> dict[str, Any]:
    return get_store().overview()


@app.get("/api/sessions/{session_id}/telemetry")
def session_telemetry(session_id: str) -> dict[str, Any]:
    return get_store().snapshot(session_id)


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


@app.post("/api/sessions/{session_id}/theodore/reply")
async def request_theodore_reply(
    session_id: str, request: TheodoreReplyRequest
) -> dict[str, Any]:
    try:
        reply = await hub.reply_to_learner(session_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="translation session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return reply.model_dump(mode="json")


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

    # A server-Whisper chunk is a completed, silence-ended capture window, so it
    # is the end of a learner turn — this drives Theodore's auto-reply. (Browser
    # streaming ASR sets end_of_turn itself.)
    item = TranscriptInput(
        text=transcript.text,
        source_language=transcript.language,
        is_final=True,
        end_of_turn=True,
        confidence=transcript.confidence,
        asr_provider=transcript.provider,
        speaker_id=speaker_id,
    )
    store = get_store()
    store.record_asr(
        session_id, latency_ms=transcript.duration_ms, language=transcript.language
    )
    store.record_upload(session_id, accepted=True, bytes_size=len(payload))
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
