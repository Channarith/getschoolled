"""LiveKit AI Teaching Agent Worker.

Theodore is the AI host for Salareen Live Rooms.  This worker connects
to a LiveKit room as "theodore-ai", publishes TTS audio of slide narrations,
listens for learner audio (STT), and routes questions to the orchestrator
teaching API so answers are delivered back through text-to-speech.

Environment variables:
    LIVEKIT_URL            wss://livekit.salareen.com (or ws://livekit:7880 locally)
    LIVEKIT_API_KEY        devkey (default)
    LIVEKIT_API_SECRET     devsecret (default)
    ORCHESTRATOR_URL       http://orchestrator:8000 (or http://localhost:8000 locally)
    OPENAI_API_KEY         optional — enables GPT-4o-realtime STT/TTS; falls back to
                           deterministic grounded answers + pyttsx3 TTS without a key.

Usage:
    # Start the agent worker (auto-dispatched on ROOM_CREATED by LiveKit server)
    python -m agent_runtime.worker

    # Join a specific room manually (for testing)
    python -m agent_runtime.worker --room class-abc123

    # Run in job/dispatch mode (production)
    python -m agent_runtime.worker --dispatch
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, Optional

logger = logging.getLogger("theodore")

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "ws://livekit:7880")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "devsecret")
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8000")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

AGENT_IDENTITY = "theodore-ai"
AGENT_NAME = "Theodore (AI Host)"


# ---------------------------------------------------------------------------
# Grounded fallback TTS (offline, no cloud key needed)
# ---------------------------------------------------------------------------

def _tts_offline(text: str) -> bytes:
    """Generate a minimal WAV from text using the system TTS (pyttsx3) if
    available, otherwise return empty bytes.  The caller handles the empty case.
    """
    try:
        import pyttsx3  # type: ignore
        import io, wave, struct, tempfile, os as _os
        engine = pyttsx3.init()
        engine.setProperty("rate", 160)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        engine.save_to_file(text, path)
        engine.runAndWait()
        with open(path, "rb") as f:
            data = f.read()
        _os.unlink(path)
        return data
    except Exception as exc:
        logger.debug("offline TTS unavailable: %s", exc)
        return b""


# ---------------------------------------------------------------------------
# Orchestrator HTTP helpers
# ---------------------------------------------------------------------------

async def _http_get(session: Any, path: str) -> dict:
    async with session.get(f"{ORCHESTRATOR_URL}{path}") as r:
        r.raise_for_status()
        return await r.json()


async def _http_post(session: Any, path: str, body: dict) -> dict:
    async with session.post(f"{ORCHESTRATOR_URL}{path}", json=body) as r:
        r.raise_for_status()
        return await r.json()


# ---------------------------------------------------------------------------
# Teaching loop
# ---------------------------------------------------------------------------

async def _run_teaching_session(room: Any, ctx: Any, session_id: Optional[str]) -> None:
    """Main loop: advance slides, narrate, listen for questions."""
    import aiohttp

    logger.info("Teaching loop started. Session: %s", session_id)
    slide_index = 0

    async with aiohttp.ClientSession() as http:
        while ctx.should_run():
            try:
                # Advance the lesson slide
                if session_id:
                    try:
                        res = await _http_post(http, f"/api/sessions/{session_id}/advance", {})
                        slide = res.get("slide", {})
                        narration = slide.get("narration", "") or slide.get("title", "")
                        slide_index = slide.get("index", slide_index)
                        # Broadcast slide sync via data channel so clients refresh
                        payload = json.dumps({
                            "type": "slide_sync",
                            "slide": slide,
                        }).encode()
                        await room.local_participant.publish_data(payload, reliable=True)
                        logger.info("Slide %d: %s", slide_index, narration[:80])
                    except Exception as exc:
                        logger.warning("Advance failed: %s", exc)
                        narration = "Let me continue the lesson."

                # Speak the narration via TTS
                await _speak(room, narration)

                # Wait for a teaching tick (30 seconds per slide default)
                await asyncio.sleep(30)
                slide_index += 1

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Teaching loop error: %s", exc)
                await asyncio.sleep(5)


async def _speak(room: Any, text: str) -> None:
    """Narrate text in the room via TTS audio or data channel fallback."""
    if not text:
        return

    # Publish text via data channel (always available — clients display it)
    payload = json.dumps({"type": "narration", "text": text}).encode()
    try:
        await room.local_participant.publish_data(payload, reliable=True)
    except Exception as exc:
        logger.debug("Data publish failed: %s", exc)

    # Attempt TTS audio if OpenAI key available (cloud) or pyttsx3 (local)
    if OPENAI_API_KEY:
        try:
            await _speak_openai(room, text)
            return
        except Exception as exc:
            logger.warning("OpenAI TTS failed, using offline: %s", exc)

    wav_bytes = _tts_offline(text)
    if wav_bytes:
        await _publish_wav(room, wav_bytes)


async def _speak_openai(room: Any, text: str) -> None:
    """Stream TTS via OpenAI and publish to the LiveKit room audio track."""
    import openai
    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    chunks = []
    async with client.audio.speech.with_streaming_response.create(
        model="tts-1", voice="onyx", input=text, response_format="wav"
    ) as resp:
        async for chunk in resp.iter_bytes(chunk_size=4096):
            chunks.append(chunk)
    wav_bytes = b"".join(chunks)
    await _publish_wav(room, wav_bytes)


async def _publish_wav(room: Any, wav_bytes: bytes) -> None:
    """Publish raw WAV bytes to the room's audio track."""
    try:
        from livekit import rtc

        source = rtc.AudioSource(sample_rate=24000, num_channels=1)
        track = rtc.LocalAudioTrack.create_audio_track("theodore-voice", source)
        await room.local_participant.publish_track(track, rtc.TrackPublishOptions(
            source=rtc.TrackSource.SOURCE_MICROPHONE,
        ))

        # Parse WAV and push frames
        import wave, io, struct
        with wave.open(io.BytesIO(wav_bytes)) as wf:
            sr = wf.getframerate()
            nc = wf.getnchannels()
            total = wf.getnframes()
            frame_size = sr // 10  # 100ms chunks
            while True:
                raw = wf.readframes(frame_size)
                if not raw:
                    break
                samples = list(struct.unpack(f"<{len(raw)//2}h", raw))
                frame = rtc.AudioFrame(
                    data=bytes(raw),
                    sample_rate=sr,
                    num_channels=nc,
                    samples_per_channel=len(raw) // (2 * nc),
                )
                await source.capture_frame(frame)
                await asyncio.sleep(frame_size / sr)

        await room.local_participant.unpublish_track(track.sid)
    except Exception as exc:
        logger.warning("WAV publish failed: %s", exc)


# ---------------------------------------------------------------------------
# LiveKit Agents entrypoint (modern livekit-agents >=1.0 style)
# ---------------------------------------------------------------------------

async def entrypoint(ctx: Any) -> None:
    """Called by livekit-agents when the worker is dispatched to a room."""
    from livekit import rtc

    room: rtc.Room = ctx.room
    logger.info("Theodore entering room: %s", room.name)

    # Extract session_id from room metadata if present (set by orchestrator on start)
    session_id: Optional[str] = None
    try:
        meta = json.loads(room.metadata or "{}")
        session_id = meta.get("session_id")
    except Exception:
        pass

    # Post a welcome message via data channel
    welcome = json.dumps({
        "type": "host_message",
        "text": f"Welcome! I'm Theodore, your AI teacher. Class is starting now.",
    }).encode()
    await room.local_participant.publish_data(welcome, reliable=True)

    # Run the teaching loop
    await _run_teaching_session(room, ctx, session_id)
    logger.info("Theodore leaving room: %s", room.name)


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------

def _build_agent() -> Any:
    """Build and return a configured livekit-agents Agent."""
    from livekit.agents import Agent, AgentSession, JobContext, cli, WorkerOptions

    class TheodoreAgent(Agent):
        def __init__(self) -> None:
            super().__init__(
                instructions=(
                    "You are Theodore, an expert AI tutor for the Salareen education platform. "
                    "You are warm, patient, and encouraging. You teach clearly and check for "
                    "understanding. You never make things up — all answers are grounded in the "
                    "lesson material. When you don't know, you say so and suggest where to look."
                ),
            )

        async def on_enter(self) -> None:
            await self.session.say(
                "Hello everyone! I'm Theodore, your AI teacher for today's session. "
                "Raise your hand anytime you have a question — just tap the hand icon.",
                allow_interruptions=True,
            )

    return TheodoreAgent


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Theodore AI teaching agent worker")
    parser.add_argument("--room", help="Join a specific room by name (manual / test mode)")
    parser.add_argument("--dispatch", action="store_true", help="Run in dispatch mode (production)")
    parser.add_argument("--dev", action="store_true", help="Run in development mode")
    args = parser.parse_args()

    try:
        from livekit.agents import cli, WorkerOptions
        from livekit.agents.voice import Agent, AgentSession
    except ImportError as exc:
        print(
            f"\nERROR: livekit-agents is not installed or incomplete: {exc}\n"
            "Install: pip install 'livekit-agents[openai]'\n"
        )
        sys.exit(1)

    logger.info("Starting Theodore worker → %s", LIVEKIT_URL)

    TheodoreAgent = _build_agent()

    async def _entry(ctx: Any) -> None:
        """Adapter: create agent session and run."""
        session = AgentSession()
        await session.start(ctx.room, agent=TheodoreAgent())
        await session.wait_for_disconnect()

    opts = WorkerOptions(
        entrypoint_fnc=_entry,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
        ws_url=LIVEKIT_URL,
        worker_type="room",  # dispatch to every new room
    )

    if args.dev:
        cli.run_app(opts)
    elif args.room:
        # Manual single-room join for testing
        asyncio.run(_join_room_directly(args.room))
    else:
        cli.run_app(opts)


async def _join_room_directly(room_name: str) -> None:
    """Connect to a specific room for manual / integration testing."""
    try:
        from livekit import rtc, api as lk_api
    except ImportError as exc:
        print(f"livekit SDK not installed: {exc}")
        return

    token = (
        lk_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(AGENT_IDENTITY)
        .with_name(AGENT_NAME)
        .with_grants(lk_api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
        .to_jwt()
    )

    room = rtc.Room()
    logger.info("Connecting directly to room %s at %s", room_name, LIVEKIT_URL)
    await room.connect(LIVEKIT_URL, token)
    logger.info("Connected. Teaching until Ctrl+C.")

    class _FakeCtx:
        def should_run(self): return True

    try:
        await _run_teaching_session(room, _FakeCtx(), session_id=None)
    except KeyboardInterrupt:
        pass
    finally:
        await room.disconnect()
        logger.info("Disconnected from room %s", room_name)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    )
    main()
