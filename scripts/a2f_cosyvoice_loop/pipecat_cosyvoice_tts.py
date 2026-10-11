#!/usr/bin/env python3
"""CosyVoice TTS as a Pipecat-compatible frame processor (HTTP /tts → WAV → PCM).

Uses the AOEP CosyVoice sidecar contract (COSYVOICE_URL). Works as a plain
async helper without Pipecat installed; if pipecat is present, CosyVoiceTTSService
subclasses FrameProcessor for pipeline wiring.

Pinned optional: install pipecat-ai in the loop venv when building full pipelines.
Voice Agent Examples checkout: ~/code/voice-agent-examples
"""
from __future__ import annotations

import asyncio
import io
import os
import wave
from typing import AsyncIterator, Optional

import httpx
import numpy as np

try:
    from pipecat.frames.frames import (  # type: ignore
        AudioRawFrame,
        ErrorFrame,
        Frame,
        TextFrame,
        TTSAudioRawFrame,
        TTSStartedFrame,
        TTSStoppedFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor  # type: ignore

    _HAS_PIPECAT = True
except Exception:  # noqa: BLE001 — optional dependency
    _HAS_PIPECAT = False
    FrameProcessor = object  # type: ignore
    Frame = object  # type: ignore
    FrameDirection = object  # type: ignore


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


async def synthesize_wav(
    text: str,
    *,
    url: Optional[str] = None,
    speaker: Optional[str] = None,
    language: str = "en",
    mode: str = "sft",
    sample_rate: int = 24000,
) -> bytes:
    endpoint = (url or _env("COSYVOICE_URL", "http://127.0.0.1:9880")).rstrip("/") + "/tts"
    spk = speaker or _env("COSYVOICE_DEFAULT_SPK", "英文女")
    payload = {
        "text": text,
        "language": language,
        "speaker": spk,
        "mode": mode,
        "sample_rate": sample_rate,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(endpoint, json=payload)
        r.raise_for_status()
        return r.content


def wav_to_pcm16(wav_bytes: bytes) -> tuple[bytes, int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        raw = w.readframes(w.getnframes())
        sw = w.getsampwidth()
    if sw != 2:
        raise ValueError("CosyVoice WAV must be 16-bit PCM")
    if ch > 1:
        pcm = np.frombuffer(raw, dtype=np.int16).reshape(-1, ch).mean(axis=1).astype(np.int16)
        raw = pcm.tobytes()
    return raw, sr


async def iter_pcm_frames(
    text: str, *, chunk_samples: int = 3200, **kwargs
) -> AsyncIterator[tuple[bytes, int]]:
    """Yield (pcm_chunk, sample_rate) from CosyVoice for a text utterance."""
    wav = await synthesize_wav(text, **kwargs)
    pcm, sr = wav_to_pcm16(wav)
    samples = np.frombuffer(pcm, dtype=np.int16)
    for i in range(0, len(samples), chunk_samples):
        chunk = samples[i : i + chunk_samples].tobytes()
        yield chunk, sr


if _HAS_PIPECAT:

    class CosyVoiceTTSService(FrameProcessor):
        """Pipecat TTS service wrapping AOEP CosyVoice HTTP sidecar."""

        def __init__(
            self,
            *,
            url: Optional[str] = None,
            speaker: Optional[str] = None,
            language: str = "en",
            sample_rate: int = 24000,
            **kwargs,
        ):
            super().__init__(**kwargs)
            self._url = url or _env("COSYVOICE_URL", "http://127.0.0.1:9880")
            self._speaker = speaker or _env("COSYVOICE_DEFAULT_SPK", "英文女")
            self._language = language
            self._sample_rate = sample_rate

        async def process_frame(self, frame: Frame, direction: FrameDirection):
            await super().process_frame(frame, direction)
            if isinstance(frame, TextFrame):
                text = (frame.text or "").strip()
                if not text:
                    return
                await self.push_frame(TTSStartedFrame(), direction)
                try:
                    async for chunk, sr in iter_pcm_frames(
                        text,
                        url=self._url,
                        speaker=self._speaker,
                        language=self._language,
                        sample_rate=self._sample_rate,
                    ):
                        # Prefer TTSAudioRawFrame when available
                        try:
                            out = TTSAudioRawFrame(audio=chunk, sample_rate=sr, num_channels=1)
                        except Exception:  # noqa: BLE001
                            out = AudioRawFrame(audio=chunk, sample_rate=sr, num_channels=1)
                        await self.push_frame(out, direction)
                except Exception as exc:  # noqa: BLE001
                    await self.push_frame(ErrorFrame(error=str(exc)), direction)
                finally:
                    await self.push_frame(TTSStoppedFrame(), direction)
            else:
                await self.push_frame(frame, direction)

else:

    class CosyVoiceTTSService:  # type: ignore[no-redef]
        """Placeholder when pipecat-ai is not installed."""

        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "pipecat-ai not installed; use synthesize_wav/iter_pcm_frames "
                "or pip install pipecat-ai in the loop venv"
            )


async def _demo() -> None:
    text = os.environ.get("COSYVOICE_DEMO_TEXT", "Pipecat CosyVoice demo.")
    n = 0
    async for chunk, sr in iter_pcm_frames(text):
        n += len(chunk) // 2
    print(f"ok samples={n} last_sr={sr}")


if __name__ == "__main__":
    asyncio.run(_demo())
