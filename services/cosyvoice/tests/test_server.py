"""Contract tests for the CosyVoice 2 server wrapper (no GPU/model needed).

We inject a fake CosyVoice model so we can assert the HTTP contract + mode
dispatch + WAV encoding without torch/vllm/weights.
"""

from __future__ import annotations

import base64
import io
import struct
import sys
import wave
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server  # noqa: E402


class FakeModel:
    sample_rate = 24000

    def __init__(self):
        self.calls = []

    def _yield(self):
        # 0.05s of a quiet ramp as float samples (like CosyVoice's tts_speech).
        yield {"tts_speech": [i / 40000.0 for i in range(1200)]}

    def inference_sft(self, text, spk, stream=False):
        self.calls.append(("sft", text, spk))
        return self._yield()

    def inference_instruct2(self, text, instruct, prompt, stream=False):
        self.calls.append(("instruct2", text, instruct))
        return self._yield()

    def inference_zero_shot(self, text, prompt_text, prompt, stream=False):
        self.calls.append(("zero_shot", text, prompt_text))
        return self._yield()

    def inference_cross_lingual(self, text, prompt, stream=False):
        self.calls.append(("cross_lingual", text))
        return self._yield()


def _client():
    model = FakeModel()
    return TestClient(server.build_app(model=model)), model


def _wav_ok(content: bytes) -> int:
    with wave.open(io.BytesIO(content), "rb") as w:
        assert w.getframerate() == 24000
        assert w.getnchannels() == 1
        return w.getnframes()


def test_health():
    client, _ = _client()
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ready"] is True


def test_sft_when_no_reference():
    client, model = _client()
    r = client.post("/tts", json={"text": "Hola clase", "language": "es", "mode": "sft"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert r.headers["x-tts-engine"] == "cosyvoice"
    assert _wav_ok(r.content) > 0
    assert model.calls[0][0] == "sft"


def test_instruct2_with_reference():
    client, model = _client()
    ref = base64.b64encode(b"RIFF" + b"\x00" * 2000).decode()
    # Avoid the real load_wav (needs torchaudio): patch the prompt loader.
    server._load_prompt_speech = lambda req: object()  # type: ignore
    r = client.post("/tts", json={
        "text": "Welcome to class", "instruct": "Speak cheerfully.",
        "mode": "instruct2", "reference_audio_b64": ref,
    })
    assert r.status_code == 200
    assert _wav_ok(r.content) > 0
    assert model.calls[0][0] == "instruct2"


def test_zero_shot_with_reference():
    client, model = _client()
    server._load_prompt_speech = lambda req: object()  # type: ignore
    ref = base64.b64encode(b"RIFF" + b"\x00" * 2000).decode()
    r = client.post("/tts", json={"text": "hi", "mode": "zero_shot", "reference_audio_b64": ref})
    assert r.status_code == 200
    assert model.calls[0][0] == "zero_shot"


def test_empty_text_400():
    client, _ = _client()
    r = client.post("/tts", json={"text": "  "})
    assert r.status_code == 400


def test_wav_encoder_roundtrip():
    data = server._wav_bytes([0, 16000, -16000, 32767, -32768], 24000)
    with wave.open(io.BytesIO(data), "rb") as w:
        frames = w.readframes(w.getnframes())
    assert struct.unpack("<5h", frames) == (0, 16000, -16000, 32767, -32768)


def test_to_int16_clamps_and_flattens():
    assert server._to_int16([[1.5], [-2.0], [0.0]]) == [32767, -32767, 0]
