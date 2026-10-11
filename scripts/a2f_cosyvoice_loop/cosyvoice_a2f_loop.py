#!/usr/bin/env python3
"""Orchestrated loop: CosyVoice TTS → PCM frames → Audio2Face-3D gRPC stream.

Env:
  COSYVOICE_URL          default http://127.0.0.1:9880
  COSYVOICE_DEFAULT_SPK  default 英文女
  A2F_GRPC_URL           default 127.0.0.1:52000

Examples:
  python3 cosyvoice_a2f_loop.py --text "Hello from CosyVoice into Audio2Face."
  python3 cosyvoice_a2f_loop.py --once --text "Smoke test."
  python3 cosyvoice_a2f_loop.py --loop --interval 8   # keep feeding phrases
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import sys
import time
import wave
from pathlib import Path
from typing import List, Optional, Tuple

import grpc
import httpx
import numpy as np
from nvidia_ace.a2f.v1_pb2 import AudioWithEmotion, EmotionParameters, FaceParameters
from nvidia_ace.audio.v1_pb2 import AudioHeader
from nvidia_ace.controller.v1_pb2 import AudioStream, AudioStreamHeader
from nvidia_ace.health_pb2 import HealthCheckRequest, HealthCheckResponse
from nvidia_ace.health_pb2_grpc import HealthStub
from nvidia_ace.services.a2f_controller.v1_pb2_grpc import A2FControllerServiceStub
from scipy import signal

LOG = logging.getLogger("cosyvoice_a2f_loop")

TARGET_SR = 16000
CHUNK_SAMPLES = 16000  # 1s chunks


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def cosyvoice_tts(
    text: str,
    *,
    url: str,
    speaker: str,
    language: str = "en",
    mode: str = "sft",
    timeout: float = 120.0,
) -> bytes:
    """POST /tts → WAV bytes (AOEP CosyVoice sidecar contract)."""
    endpoint = url.rstrip("/") + "/tts"
    payload = {
        "text": text,
        "language": language,
        "speaker": speaker,
        "mode": mode,
        "sample_rate": 24000,
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(endpoint, json=payload)
        r.raise_for_status()
        return r.content


def wav_to_pcm16_mono(wav_bytes: bytes, target_sr: int = TARGET_SR) -> Tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw != 2:
        raise ValueError(f"expected 16-bit PCM, got sampwidth={sw}")
    pcm = np.frombuffer(raw, dtype=np.int16)
    if ch > 1:
        pcm = pcm.reshape(-1, ch).mean(axis=1).astype(np.int16)
    if sr != target_sr:
        # resample float → int16
        n_out = int(round(len(pcm) * float(target_sr) / float(sr)))
        flo = pcm.astype(np.float32) / 32768.0
        flo = signal.resample(flo, n_out)
        pcm = np.clip(flo * 32768.0, -32768, 32767).astype(np.int16)
        sr = target_sr
    return pcm, sr


async def a2f_health(url: str) -> bool:
    async with grpc.aio.insecure_channel(url) as ch:
        stub = HealthStub(ch)
        try:
            resp = await stub.Check(HealthCheckRequest(), timeout=5.0)
            return resp.status == HealthCheckResponse.SERVING
        except grpc.RpcError as exc:
            LOG.error("A2F health failed: %s", exc.details() if hasattr(exc, "details") else exc)
            return False


async def push_pcm_to_a2f(
    url: str,
    pcm: np.ndarray,
    sample_rate: int,
    *,
    out_dir: Optional[Path] = None,
) -> dict:
    """Stream PCM into ProcessAudioStream; return metrics (frames, status)."""
    metrics = {
        "blendshape_frames": 0,
        "status_code": None,
        "status_message": "",
        "blend_names": [],
        "first_weights": None,
    }
    async with grpc.aio.insecure_channel(url) as ch:
        stub = A2FControllerServiceStub(ch)
        stream = stub.ProcessAudioStream()

        async def writer() -> None:
            await stream.write(
                AudioStream(
                    audio_stream_header=AudioStreamHeader(
                        audio_header=AudioHeader(
                            samples_per_second=sample_rate,
                            bits_per_sample=16,
                            channel_count=1,
                            audio_format=AudioHeader.AUDIO_FORMAT_PCM,
                        ),
                        face_params=FaceParameters(float_params={}),
                        emotion_params=EmotionParameters(live_transition_time=0.5),
                    )
                )
            )
            for i in range(0, len(pcm), CHUNK_SAMPLES):
                chunk = pcm[i : i + CHUNK_SAMPLES]
                await stream.write(
                    AudioStream(
                        audio_with_emotion=AudioWithEmotion(
                            audio_buffer=chunk.astype(np.int16).tobytes()
                        )
                    )
                )
            await stream.write(AudioStream(end_of_audio=AudioStream.EndOfAudio()))

        async def reader() -> None:
            while True:
                msg = await stream.read()
                if msg == grpc.aio.EOF:
                    break
                which = msg.WhichOneof("stream_part")
                if which == "animation_data_stream_header":
                    hdr = msg.animation_data_stream_header
                    metrics["blend_names"] = list(hdr.skel_animation_header.blend_shapes)
                    LOG.info("A2F header blendshapes=%s", len(metrics["blend_names"]))
                elif which == "animation_data":
                    weights = msg.animation_data.skel_animation.blend_shape_weights
                    metrics["blendshape_frames"] += len(weights)
                    if metrics["first_weights"] is None and weights:
                        metrics["first_weights"] = list(weights[0].values)
                    print(".", end="", flush=True)
                elif which == "status":
                    metrics["status_code"] = int(msg.status.code)
                    metrics["status_message"] = msg.status.message
                    LOG.info("A2F status code=%s msg=%s", msg.status.code, msg.status.message)

        write_task = asyncio.create_task(writer())
        read_task = asyncio.create_task(reader())
        await write_task
        await read_task
        print()

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    return metrics


async def run_once(args: argparse.Namespace) -> int:
    cosy_url = args.cosyvoice_url or _env("COSYVOICE_URL", "http://127.0.0.1:9880")
    spk = args.speaker or _env("COSYVOICE_DEFAULT_SPK", "英文女")
    a2f_url = args.a2f_url or _env("A2F_GRPC_URL", "127.0.0.1:52000")

    if not await a2f_health(a2f_url):
        LOG.error("A2F not SERVING at %s — start stub or NIM first", a2f_url)
        return 2

    LOG.info("CosyVoice TTS: %r via %s spk=%s", args.text, cosy_url, spk)
    t0 = time.time()
    wav = await asyncio.to_thread(
        cosyvoice_tts, args.text, url=cosy_url, speaker=spk, language=args.language
    )
    pcm, sr = wav_to_pcm16_mono(wav, TARGET_SR)
    LOG.info(
        "CosyVoice ok bytes=%s samples=%s sr=%s (%.2fs)",
        len(wav),
        len(pcm),
        sr,
        time.time() - t0,
    )

    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cosyvoice.wav").write_bytes(wav)

    t1 = time.time()
    metrics = await push_pcm_to_a2f(a2f_url, pcm, sr, out_dir=out_dir)
    LOG.info(
        "A2F push done frames=%s status=%s (%.2fs)",
        metrics["blendshape_frames"],
        metrics["status_code"],
        time.time() - t1,
    )
    ok = (
        metrics["blendshape_frames"] > 0
        and metrics["status_code"] in (0, 1, None)  # SUCCESS/INFO or header-only
    )
    # Prefer explicit SUCCESS
    if metrics["status_code"] not in (0, 1):
        ok = False
    if ok:
        LOG.info("SMOKE_OK blendshape_frames=%s", metrics["blendshape_frames"])
        return 0
    LOG.error("SMOKE_FAIL metrics=%s", metrics)
    return 1


PHRASES = [
    "Hello from CosyVoice into Audio2Face.",
    "Welcome to the Salareen teaching loop.",
    "This audio drives facial blendshapes.",
]


async def run_loop(args: argparse.Namespace) -> int:
    i = 0
    while True:
        args.text = PHRASES[i % len(PHRASES)]
        code = await run_once(args)
        if code != 0 and not args.keep_going:
            return code
        i += 1
        if args.once:
            return code
        await asyncio.sleep(args.interval)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--text", default="Hello from CosyVoice into Audio2Face.")
    p.add_argument("--language", default="en")
    p.add_argument("--speaker", default="")
    p.add_argument("--cosyvoice-url", default="")
    p.add_argument("--a2f-url", default="")
    p.add_argument("--out-dir", default="/tmp/a2f_cosyvoice_smoke")
    p.add_argument("--once", action="store_true", help="Single utterance then exit")
    p.add_argument("--loop", action="store_true", help="Repeat phrases")
    p.add_argument("--interval", type=float, default=8.0)
    p.add_argument("--keep-going", action="store_true", help="Continue loop after failures")
    args = p.parse_args()
    if args.loop:
        args.once = False
        raise SystemExit(asyncio.run(run_loop(args)))
    args.once = True
    raise SystemExit(asyncio.run(run_once(args)))


if __name__ == "__main__":
    main()
