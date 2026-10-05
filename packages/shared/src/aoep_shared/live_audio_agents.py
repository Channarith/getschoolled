"""Browser-safe realtime speech-to-speech agents for Theodore labs.

This is deliberately separate from ``lab_tts``. TTS renders a complete text
string and then plays a file; xAI Voice and Gemini Live stream microphone PCM
to a native-audio model and stream PCM back while the learner is still in the
conversation. That provides natural turn-taking and barge-in without stitching
sentence clips together.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .xai_realtime import (
    XaiVoiceError,
    build_voice_session,
    mint_ephemeral_token,
    xai_configured,
)

GEMINI_TOKEN_URL = "https://generativelanguage.googleapis.com/v1alpha/auth_tokens"
GEMINI_LIVE_WS = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1alpha.GenerativeService."
    "BidiGenerateContentConstrained"
)
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_GEMINI_VOICE = "Kore"
CLIENT_JS = Path(__file__).with_name("static") / "lab_live_audio.js"


class LiveAudioError(RuntimeError):
    """A realtime provider could not mint a browser credential."""


def _gemini_key() -> str:
    return (
        os.environ.get("GEMINI_API_KEY", "")
        or os.environ.get("GOOGLE_API_KEY", "")
    ).strip()


def provider_status() -> dict[str, Any]:
    """Configured native-audio providers; never reports ordinary TTS as live."""
    xai = xai_configured()
    gemini = bool(_gemini_key())
    return {
        "available": xai or gemini,
        "default": "xai" if xai else "gemini" if gemini else "",
        "providers": {
            "xai": {
                "available": xai,
                "label": "xAI Voice Agent",
                "model": os.environ.get("XAI_VOICE_MODEL", "grok-voice-latest"),
                "input_rate": 24000,
                "output_rate": 24000,
            },
            "gemini": {
                "available": gemini,
                "label": "Gemini Live",
                "model": os.environ.get(
                    "GEMINI_LIVE_MODEL", DEFAULT_GEMINI_MODEL
                ),
                "input_rate": 16000,
                "output_rate": 24000,
            },
        },
        "note": (
            "Native speech-to-speech is ready; no TTS clips are used."
            if xai or gemini
            else "Set XAI_API_KEY or GEMINI_API_KEY to enable a live audio agent."
        ),
    }


def _iso_after(seconds: int) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    return (now + dt.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    *,
    timeout: float = 15.0,
) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise LiveAudioError(f"provider HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LiveAudioError(f"provider unreachable: {exc.reason}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LiveAudioError("provider returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise LiveAudioError("provider response was not an object")
    return data


def mint_gemini_token(
    *,
    setup: dict[str, Any],
    expires_seconds: int = 1800,
) -> dict[str, Any]:
    """Mint a one-session v1alpha token for direct browser Gemini Live audio."""
    key = _gemini_key()
    if not key:
        raise LiveAudioError("GEMINI_API_KEY is not configured")
    expires = max(300, min(3600, int(expires_seconds)))
    data = _post_json(
        GEMINI_TOKEN_URL,
        {
            "uses": 1,
            "expireTime": _iso_after(expires),
            # Permission prompts can sit open for more than the API's 60s
            # default. The token is still one-use and message expiry remains
            # short, but a child/adult has time to approve the microphone.
            "newSessionExpireTime": _iso_after(min(600, expires)),
            # Lock model, system prompt, voice and especially tools. Without
            # this, a modified browser can turn a paid lab token into an
            # arbitrary Gemini Live session with code/search/function tools.
            "bidiGenerateContentSetup": setup,
        },
        {
            "x-goog-api-key": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise LiveAudioError("Gemini auth_tokens response missing name")
    model = os.environ.get("GEMINI_LIVE_MODEL", DEFAULT_GEMINI_MODEL)
    ws = f"{GEMINI_LIVE_WS}?access_token={urllib.parse.quote(name, safe='/')}"
    return {
        "provider": "gemini",
        "token": name,
        "websocket_url": ws,
        "input_rate": 16000,
        "output_rate": 24000,
        "model": model,
        # The first WebSocket frame is still required. Constrained tokens make
        # the server ignore conflicting client fields and use this locked copy.
        "setup": {"setup": setup},
    }


def mint_xai_token(
    *,
    mode: str,
    context: str,
    instructions: str,
    expires_seconds: int = 300,
) -> dict[str, Any]:
    """Mint an xAI browser token and its speech-to-speech session setup."""
    if not xai_configured():
        raise LiveAudioError("XAI_API_KEY is not configured")
    model = os.environ.get("XAI_VOICE_MODEL", "grok-voice-latest")
    voice = os.environ.get("XAI_VOICE_ID", "") or os.environ.get(
        "XAI_VOICE", "eve"
    )
    session = build_voice_session(
        mode,
        voice=voice,
        model=model,
        lesson_context=context,
        instructions=instructions,
    )
    locked_session = dict(session.session_update_event()["session"])
    locked_session.update({"model": model, "tools": []})
    try:
        token = mint_ephemeral_token(
            expires_seconds=expires_seconds,
            model=model,
            allow_mock=False,
            session=locked_session,
        )
    except XaiVoiceError as exc:
        raise LiveAudioError(str(exc)) from exc
    return {
        "provider": "xai",
        "token": token.value,
        "websocket_url": token.websocket_url,
        "websocket_protocol": token.websocket_protocol,
        "input_rate": 24000,
        "output_rate": 24000,
        "model": model,
        "setup": session.session_update_event(),
    }


def mint_provider_token(
    provider: str,
    *,
    mode: str = "solo",
    context: str = "",
    instructions: str = "",
    expires_seconds: int = 300,
) -> dict[str, Any]:
    provider = (provider or "").strip().lower()
    if provider == "xai":
        return mint_xai_token(
            mode=mode,
            context=context,
            instructions=instructions,
            expires_seconds=expires_seconds,
        )
    if provider == "gemini":
        system = instructions.strip() or (
            "You are Theodore, a warm, concise tutor. Listen naturally, allow "
            "the learner to interrupt, and answer in short spoken turns."
        )
        if context.strip():
            system += f"\n\nCurrent lab context:\n{context.strip()}"
        model = os.environ.get("GEMINI_LIVE_MODEL", DEFAULT_GEMINI_MODEL)
        voice = os.environ.get("GEMINI_LIVE_VOICE", DEFAULT_GEMINI_VOICE)
        setup = {
            "model": f"models/{model}",
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": voice}
                    }
                },
            },
            "systemInstruction": {"parts": [{"text": system}]},
            "tools": [],
            "inputAudioTranscription": {},
            "outputAudioTranscription": {},
            "sessionResumption": {},
        }
        return mint_gemini_token(
            setup=setup,
            expires_seconds=max(300, expires_seconds),
        )
    raise LiveAudioError(f"unsupported live audio provider: {provider or 'none'}")


def client_script_tag() -> str:
    return '<script src="/api/live-audio/client.js" defer></script>'


def inject_client(html: str) -> str:
    """Add the provider widget to a lab page exactly once."""
    if "/api/live-audio/client.js" in html:
        return html
    tag = client_script_tag()
    return html.replace("</body>", f"{tag}\n</body>") if "</body>" in html else html + tag


def install_live_audio_routes(app: Any, *, lab_name: str) -> None:
    """Install same-origin status/token/client routes on a FastAPI lab app."""
    from fastapi import Body, HTTPException, Request
    from fastapi.responses import Response
    # With postponed annotations FastAPI resolves endpoint types from module
    # globals, even though Request is imported lazily to keep FastAPI optional
    # for non-web consumers of aoep-shared.
    globals()["_LiveAudioRequest"] = Request

    @app.get("/api/live-audio/status", include_in_schema=False)
    def live_audio_status() -> dict[str, Any]:
        return provider_status()

    @app.post("/api/live-audio/token", include_in_schema=False)
    def live_audio_token(
        request: _LiveAudioRequest,  # type: ignore[name-defined]  # noqa: F821
        payload: dict[str, Any] = Body(default={}),
    ) -> dict[str, Any]:
        # Same-origin browser calls only. JSON also forces a CORS preflight,
        # but checking Origin here protects apps that later enable broad CORS.
        origin = request.headers.get("origin", "")
        host = request.headers.get("host", "")
        if origin and urllib.parse.urlparse(origin).netloc != host:
            raise HTTPException(status_code=403, detail="cross-origin token mint denied")
        provider = str(payload.get("provider") or "")
        try:
            return mint_provider_token(
                provider,
                # Do not let a browser choose tools, prompt, context, lifetime
                # or persona. The backend owns the constrained paid session.
                mode="solo",
                context=lab_name,
                instructions=(
                    "You are Theodore, a warm, concise tutor. Listen naturally, "
                    "let the learner interrupt, and never mention TTS."
                ),
                expires_seconds=300 if provider == "xai" else 1800,
            )
        except (LiveAudioError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/live-audio/client.js", include_in_schema=False)
    def live_audio_client() -> Response:
        return Response(
            CLIENT_JS.read_text(encoding="utf-8"),
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )
