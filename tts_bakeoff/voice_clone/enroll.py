"""Prepare a clean reference sample: mono 24 kHz wav, trimmed, loudness normalized, length and SNR checked.

Needs ffmpeg and numpy. Recording is done with any recorder (phone voice memo, QuickTime); this imports the file.
"""
from __future__ import annotations

import subprocess
import tempfile
import wave
from pathlib import Path

MIN_S, MAX_S, MIN_SNR_DB = 20.0, 90.0, 20.0
RATE = 24000


class SampleError(RuntimeError):
    pass


def read_wav(path: Path):
    import numpy as np

    with wave.open(str(path), "rb") as w:
        rate, n = w.getframerate(), w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype="<i2").astype("float32") / 32768.0
    return data, rate


def trim_silence(x, rate: int, thresh_db: float = -45.0, pad_s: float = 0.15):
    import numpy as np

    frame = int(rate * 0.02)
    k = len(x) // frame
    if k == 0:
        return x
    rms = np.sqrt((x[: k * frame].reshape(k, frame) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    loud = np.where(db > thresh_db)[0]
    if len(loud) == 0:
        return x[:0]
    a = max(0, (loud[0] * frame) - int(pad_s * rate))
    b = min(len(x), (loud[-1] + 1) * frame + int(pad_s * rate))
    return x[a:b]


def snr_db(x, rate: int) -> float:
    """Crude: speech frames (top decile of energy) over the quietest decile."""
    import numpy as np

    frame = int(rate * 0.03)
    k = len(x) // frame
    if k < 10:
        return 0.0
    e = np.sort((x[: k * frame].reshape(k, frame) ** 2).mean(axis=1) + 1e-12)
    d = max(1, k // 10)
    return float(10 * np.log10(e[-d:].mean() / e[:d].mean()))


def prepare(src: Path | str, dest: Path | str, target_dbfs: float = -20.0, clean: bool | None = None) -> dict:
    import numpy as np

    from tts_bakeoff.adapters.base import write_wav

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t) / "in.wav"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", str(RATE),
                            "-sample_fmt", "s16", str(tmp)], capture_output=True, text=True)
        if r.returncode != 0:
            raise SampleError(f"ffmpeg could not read {src}: {r.stderr[:200]}")
        x, rate = read_wav(tmp)
    x = trim_silence(x, rate)
    secs = len(x) / rate
    if secs < MIN_S:
        raise SampleError(f"only {secs:.0f}s of speech after trimming; need {MIN_S:.0f}-{MAX_S:.0f}s of clean speech")
    if secs > MAX_S:
        x, secs = x[: int(MAX_S * rate)], MAX_S
    snr = snr_db(x, rate)
    if snr < MIN_SNR_DB:
        raise SampleError(f"too noisy (about {snr:.0f} dB SNR, need {MIN_SNR_DB:.0f}+): re-record in a quiet room")
    from . import clean as audio_clean

    info: dict = {}
    warnings = []
    if (audio_clean.enabled() if clean is None else clean):
        raw = audio_clean.raw_path(Path(dest))
        write_wav(raw, x, rate)
        y, rep = audio_clean.clean_reference(x, rate)
        info.update({"cleaned": rep["kept_cleaned"], "snr_db_clean": rep["after"]["snr_db"], "clicks_fixed": max(0, rep["before"]["clicks"] - rep["after"]["clicks"])})
        if rep["kept_cleaned"]:
            x = y
        else:
            warnings.append("kept the recording as it was (cleaning would have changed the voice): " + "; ".join(rep["reasons"]))
        if rep["before"]["clip_pct"] > 0.1:
            warnings.append(f"{rep['before']['clip_pct']}% of samples clipped: record again a little further from the microphone")
    if snr < MIN_SNR_DB + 5:
        warnings.append(f"about {snr:.0f} dB SNR is usable but not great: a quieter room gives a cleaner clone")
    rms = float(np.sqrt((x**2).mean()) + 1e-9)
    x = np.clip(x * (10 ** (target_dbfs / 20) / rms), -0.99, 0.99)
    write_wav(dest, x, rate)
    return {"seconds": round(secs, 1), "snr_db": round(snr, 1), "sample_rate": rate, **info, "warnings": warnings}
