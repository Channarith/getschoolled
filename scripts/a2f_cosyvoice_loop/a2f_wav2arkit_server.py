#!/usr/bin/env python3
"""A2F-compatible gRPC server powered by Wav2ARKit ONNX (native aarch64).

Speaks Health + A2FControllerService.ProcessAudioStream so CosyVoice → A2F
clients keep working without NVIDIA's amd64-only Audio2Face-3D NIM.

  python3 a2f_wav2arkit_server.py --host 0.0.0.0 --port 52000
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import AsyncIterator, List

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

from wav2arkit import TARGET_SR, Wav2ARKit

LOG = logging.getLogger("a2f_wav2arkit")


def _pcm16_mono(buf: bytes) -> np.ndarray:
    if not buf:
        return np.zeros(0, dtype=np.int16)
    n = len(buf) // 2
    return np.frombuffer(buf[: n * 2], dtype=np.int16)


class _Health(HealthServicer):
    async def Check(self, request: HealthCheckRequest, context) -> HealthCheckResponse:  # noqa: N802
        return HealthCheckResponse(status=HealthCheckResponse.SERVING)


class _A2F(A2FControllerServiceServicer):
    def __init__(self, engine: Wav2ARKit) -> None:
        self.engine = engine

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

        sr = int(header.samples_per_second or TARGET_SR)
        yield AnimationDataStream(
            animation_data_stream_header=AnimationDataStreamHeader(
                audio_header=header,
                skel_animation_header=SkelAnimationHeader(
                    blend_shapes=list(self.engine.blend_names)
                ),
            )
        )

        pcm = _pcm16_mono(b"".join(pcm_chunks))
        try:
            weights = await asyncio.to_thread(self.engine.infer_pcm16, pcm, sr)
        except Exception as exc:  # noqa: BLE001
            LOG.exception("wav2arkit inference failed")
            yield AnimationDataStream(
                status=Status(code=Status.ERROR, message=f"wav2arkit: {exc}")
            )
            return

        frames = int(weights.shape[0])
        for i in range(frames):
            t = i / 30.0
            values = [float(x) for x in weights[i].tolist()]
            # Echo a short audio window for clients that mux A/V
            hop = max(1, sr // 30)
            start = int(i * hop * sr / TARGET_SR) if sr != TARGET_SR else i * hop
            window = pcm[start : start + hop]
            anim = AnimationData(
                skel_animation=SkelAnimation(
                    blend_shape_weights=[
                        FloatArrayWithTimeCode(time_code=t, values=values)
                    ]
                ),
            )
            if len(window):
                anim.audio.time_code = t
                anim.audio.audio_buffer = window.astype(np.int16).tobytes()
            yield AnimationDataStream(animation_data=anim)

        LOG.info("emitted_frames=%s samples=%s", frames, len(pcm))
        yield AnimationDataStream(
            status=Status(
                code=Status.SUCCESS,
                message=f"wav2arkit ok frames={frames} bytes_in={bytes_in}",
            )
        )


async def serve(host: str, port: int) -> None:
    LOG.info("Loading Wav2ARKit ONNX (CPU / aarch64)…")
    engine = await asyncio.to_thread(Wav2ARKit)
    LOG.info("model=%s blendshapes=%s", engine.model_path, len(engine.blend_names))
    server = grpc.aio.server(
        options=[
            ("grpc.max_send_message_length", 64 * 1024 * 1024),
            ("grpc.max_receive_message_length", 64 * 1024 * 1024),
        ]
    )
    add_HealthServicer_to_server(_Health(), server)
    add_A2FControllerServiceServicer_to_server(_A2F(engine), server)
    listen = f"{host}:{port}"
    server.add_insecure_port(listen)
    await server.start()
    LOG.info("A2F Wav2ARKit SERVING on %s (native ARM, not NVIDIA NIM)", listen)
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
