"""Self-hosted speaker embedding and matching.

The model is operator supplied through ``VOICEPRINT_MODEL_PATH``. Audio is
decoded in a temporary directory and deleted immediately; callers persist only
the normalized embedding in their encrypted template store.
"""

from __future__ import annotations

import math
import os
import base64
import hashlib
import json
import subprocess
import tempfile
import wave
from dataclasses import dataclass


class VoiceIdentityUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class VoiceMatch:
    matched: bool
    score: float


def _decode_to_pcm(audio: bytes) -> tuple[list[float], int]:
    if not audio:
        raise ValueError("audio is empty")
    with tempfile.TemporaryDirectory(prefix="salareen-voice-") as directory:
        source = os.path.join(directory, "sample")
        target = os.path.join(directory, "sample.wav")
        with open(source, "wb") as stream:
            stream.write(audio)
        try:
            subprocess.run(
                [
                    "ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", source,
                    "-ac", "1", "-ar", "16000", "-f", "wav", target,
                ],
                check=True,
                timeout=20,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("audio could not be decoded") from exc
        with wave.open(target, "rb") as stream:
            sample_rate = stream.getframerate()
            width = stream.getsampwidth()
            frames = stream.readframes(stream.getnframes())
    if width != 2:
        raise ValueError("decoded audio must be 16-bit PCM")
    samples = [
        int.from_bytes(frames[i : i + 2], "little", signed=True) / 32768.0
        for i in range(0, len(frames), 2)
    ]
    _validate_signal(samples, sample_rate)
    return samples, sample_rate


def _validate_signal(samples: list[float], sample_rate: int) -> None:
    duration = len(samples) / max(1, sample_rate)
    if duration < 8 or duration > 15:
        raise ValueError("voice sample must be between 8 and 15 seconds")
    rms = math.sqrt(sum(value * value for value in samples) / max(1, len(samples)))
    if rms < 0.01:
        raise ValueError("voice sample is silent or too quiet")
    clipped = sum(1 for value in samples if abs(value) >= 0.98) / max(1, len(samples))
    if clipped > 0.03:
        raise ValueError("voice sample is clipped; move farther from the microphone")


class SherpaSpeakerProvider:
    """Pinned-model speaker embeddings through sherpa-onnx."""

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path or os.getenv("VOICEPRINT_MODEL_PATH", "")
        if not self.model_path:
            raise VoiceIdentityUnavailable("VOICEPRINT_MODEL_PATH is not configured")
        try:
            import sherpa_onnx  # type: ignore
        except ImportError as exc:
            raise VoiceIdentityUnavailable("sherpa-onnx is not installed") from exc
        config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=self.model_path,
            num_threads=2,
            debug=False,
            provider="cpu",
        )
        self._extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)

    def embedding(self, audio: bytes) -> list[float]:
        samples, sample_rate = _decode_to_pcm(audio)
        stream = self._extractor.create_stream()
        stream.accept_waveform(sample_rate=sample_rate, waveform=samples)
        if not self._extractor.is_ready(stream):
            raise ValueError("voice sample is too short for speaker enrollment")
        vector = [float(value) for value in self._extractor.compute(stream)]
        norm = math.sqrt(sum(value * value for value in vector))
        if not vector or norm <= 0:
            raise ValueError("speaker model returned an invalid embedding")
        return [value / norm for value in vector]

    @staticmethod
    def compare(enrolled: list[float], probe: list[float], threshold: float = 0.65) -> VoiceMatch:
        if not enrolled or len(enrolled) != len(probe):
            return VoiceMatch(matched=False, score=0.0)
        score = sum(a * b for a, b in zip(enrolled, probe))
        return VoiceMatch(matched=score >= threshold, score=score)


class EncryptedVoiceGallery:
    """Small encrypted-at-rest template gallery for the perception boundary."""

    def __init__(self, path: str, secret: str) -> None:
        self.path = path
        self._key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())

    def _fernet(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            raise VoiceIdentityUnavailable("cryptography is not installed") from exc
        return Fernet(self._key)

    def _read(self) -> dict[str, list[float]]:
        if not os.path.isfile(self.path):
            return {}
        with open(self.path, "rb") as stream:
            plaintext = self._fernet().decrypt(stream.read())
        data = json.loads(plaintext)
        return {str(key): [float(v) for v in value] for key, value in data.items()}

    def _write(self, data: dict[str, list[float]]) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        encrypted = self._fernet().encrypt(
            json.dumps(data, separators=(",", ":")).encode("utf-8")
        )
        fd, temporary = tempfile.mkstemp(prefix=".voiceprints-", dir=directory or None)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encrypted)
            os.replace(temporary, self.path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def enroll(self, student_id: str, embedding: list[float]) -> str:
        data = self._read()
        data[student_id] = embedding
        self._write(data)
        return hashlib.sha256(student_id.encode("utf-8")).hexdigest()[:24]

    def verify(self, student_id: str, probe: list[float], threshold: float = 0.65) -> VoiceMatch:
        enrolled = self._read().get(student_id, [])
        return SherpaSpeakerProvider.compare(enrolled, probe, threshold)

    def remove(self, student_id: str) -> None:
        data = self._read()
        if student_id in data:
            del data[student_id]
            self._write(data)
