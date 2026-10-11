#!/usr/bin/env python3
"""Protocol-compatible Audio2Face-3D gRPC stub for aarch64 Spark.

NVIDIA A2F-3D NIM is linux/amd64-only (no ARM / DGX Spark support). This stub
speaks the same Health + A2FControllerService.ProcessAudioStream API so the
CosyVoice → A2F loop can be developed and smoke-tested locally.

Bind: A2F_GRPC_HOST:A2F_GRPC_PORT (default 0.0.0.0:52000).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import math
import os
from typing import AsyncIterator, List, Sequence

import grpc
import numpy as np
from nvidia_ace.a2f.v1_pb2 import AudioWithEmotion
from nvidia_ace.animation_data.v1_pb2 import (
    AnimationData,
    FloatArrayWithTimeCode,
    SkelAnimation,
    SkelAnimationHeader,
)
from nvidia_ace.audio.v1_pb2 import AudioHeader
from nvidia_ace.controller.v1_pb2 import (
    AnimationDataStream,
    AnimationDataStreamHeader,
    AudioStream,
)
from nvidia_ace.health_pb2 import HealthCheckRequest, HealthCheckResponse
from nvidia_ace.health_pb2_grpc import HealthServicer, add_HealthServicer_to_server
from nvidia_ace.services.a2f_controller.v1_pb2_grpc import (
    A2FControllerServiceServicer,
    add_A2FControllerServiceServicer_to_server,
)
from nvidia_ace.status.v1_pb2 import Status

LOG = logging.getLogger("a2f_stub")

# Minimal ARKit-style names so clients can inspect blendshape CSV/metrics.
BLEND_SHAPES: Sequence[str] = (
    "EyeBlinkLeft",
    "EyeBlinkRight",
    "JawOpen",
    "MouthSmileLeft",
    "MouthSmileRight",
    "MouthFunnel",
    "BrowInnerUp",
    "CheekPuff",
)


def _pcm16_mono(buf: bytes) -> np.ndarray:
    if not buf:
        return np.zeros(0, dtype=np.int16)
    n = len(buf) // 2
    return np.frombuffer(buf[: n * 2], dtype=np.int16)


def _frame_weights(energy: float, t: float) -> List[float]:
    """Deterministic pseudo-blendshapes driven by audio energy + time."""
    e = max(0.0, min(1.0, energy))
    jaw = min(1.0, e * 1.4)
    smile = 0.15 + 0.25 * (0.5 + 0.5 * math.sin(t * 6.0))
    blink = 1.0 if (int(t * 3) % 17 == 0) else 0.0
    return [
        blink,
        blink,
        jaw,
        smile * e,
        smile * e,
        max(0.0, e - 0.4) * 0.6,
        0.1 + 0.2 * e,
        max(0.0, e - 0.6) * 0.3,
    ]


class _Health(HealthServicer):
    async def Check(self, request: HealthCheckRequest, context) -> HealthCheckResponse:  # noqa: N802
        return HealthCheckResponse(status=HealthCheckResponse.SERVING)


class _A2F(A2FControllerServiceServicer):
    async def ProcessAudioStream(  # noqa: N802
        self, request_iterator: AsyncIterator[AudioStream], context
    ) -> AsyncIterator[AnimationDataStream]:
        header: AudioHeader | None = None
        pcm_chunks: List[bytes] = []
        bytes_in = 0
        async for msg in request_iterator:
            which = msg.WhichOneof("stream_part")
            if which == "audio_stream_header":
                header = msg.audio_stream_header.audio_header
                LOG.info(
                    "header sr=%s bits=%s ch=%s",
                    header.samples_per_second,
                    header.bits_per_sample,
                    header.channel_count,
                )
            elif which == "audio_with_emotion":
                chunk: AudioWithEmotion = msg.audio_with_emotion
                pcm_chunks.append(bytes(chunk.audio_buffer))
                bytes_in += len(chunk.audio_buffer)
            elif which == "end_of_audio":
                LOG.info("end_of_audio bytes_in=%s", bytes_in)
                break

        if header is None:
            yield AnimationDataStream(
                status=Status(code=Status.ERROR, message="missing AudioStreamHeader")
            )
            return

        sr = int(header.samples_per_second or 16000)
        yield AnimationDataStream(
            animation_data_stream_header=AnimationDataStreamHeader(
                audio_header=header,
                skel_animation_header=SkelAnimationHeader(blend_shapes=list(BLEND_SHAPES)),
            )
        )

        pcm = b"".join(pcm_chunks)
        samples = _pcm16_mono(pcm)
        # ~30 FPS animation frames
        hop = max(1, sr // 30)
        frames = 0
        for i in range(0, max(len(samples), 1), hop):
            window = samples[i : i + hop]
            if len(window) == 0:
                rms = 0.0
            else:
                rms = float(np.sqrt(np.mean(window.astype(np.float32) ** 2))) / 32768.0
            t = i / float(sr)
            weights = _frame_weights(rms, t)
            anim = AnimationData(
                skel_animation=SkelAnimation(
                    blend_shape_weights=[
                        FloatArrayWithTimeCode(time_code=t, values=weights)
                    ]
                ),
            )
            if len(window):
                anim.audio.time_code = t
                anim.audio.audio_buffer = window.astype(np.int16).tobytes()
            yield AnimationDataStream(animation_data=anim)
            frames += 1

        LOG.info("emitted_frames=%s samples=%s", frames, len(samples))
        yield AnimationDataStream(
            status=Status(
                code=Status.SUCCESS,
                message=f"a2f_stub ok frames={frames} bytes_in={bytes_in}",
            )
        )


async def serve(host: str, port: int) -> None:
    server = grpc.aio.server(options=[("grpc.max_send_message_length", 64 * 1024 * 1024),
                                      ("grpc.max_receive_message_length", 64 * 1024 * 1024)])
    add_HealthServicer_to_server(_Health(), server)
    add_A2FControllerServiceServicer_to_server(_A2F(), server)
    listen = f"{host}:{port}"
    server.add_insecure_port(listen)
    await server.start()
    LOG.info("A2F stub SERVING on %s (protocol-compatible; not NVIDIA NIM)", listen)
    await server.wait_for_termination()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default=os.environ.get("A2F_GRPC_HOST", "0.0.0.0"))
    p.add_argument("--port", type=int, default=int(os.environ.get("A2F_GRPC_PORT", "52000")))
    args = p.parse_args()
    asyncio.run(serve(args.host, args.port))


if __name__ == "__main__":
    main()
