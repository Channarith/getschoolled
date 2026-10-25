import wave

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from tts_bakeoff.adapters.cosyvoice2 import load_prompt_wav


def _write(path, sr, seconds=0.5, channels=1):
    t = np.arange(int(sr * seconds)) / sr
    mono = (0.3 * np.sin(2 * np.pi * 220 * t) * 32767).astype("<i2")
    data = np.repeat(mono[:, None], channels, axis=1).reshape(-1) if channels > 1 else mono
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())


@pytest.mark.parametrize("sr,channels", [(24000, 1), (16000, 1), (48000, 2)])
def test_load_prompt_wav_is_mono_16k_tensor(tmp_path, sr, channels):
    p = tmp_path / "ref.wav"
    _write(p, sr, channels=channels)
    out = load_prompt_wav(str(p), 16000)
    assert out.shape[0] == 1
    assert abs(out.shape[1] - 8000) <= 4  # 0.5 s at 16 kHz
    assert float(out.abs().max()) > 0.2


def test_load_prompt_wav_works_without_torchaudio_load(tmp_path, monkeypatch):
    torchaudio = pytest.importorskip("torchaudio")
    monkeypatch.setattr(torchaudio, "load", lambda *a, **k: (_ for _ in ()).throw(ImportError("TorchCodec is required")))
    p = tmp_path / "ref.wav"
    _write(p, 24000)
    assert load_prompt_wav(str(p), 16000).shape[0] == 1
