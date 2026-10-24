"""Common adapter interface for every TTS model in the bake-off.

An adapter wraps one model behind:
    check()                         -> {"ok": bool, "problems": [...]}  without loading a model or a GPU
    synthesize(text, lang, out_wav) -> {"duration_s": float, "synth_s": float, "sample_rate": int}

Heavy dependencies (torch, transformers, vendor packages) are imported inside methods only, so this
package imports on a Mac with nothing installed. Adapters for real models were written against the
vendor documentation and have NOT been run against the real weights in this repository's CI; run
`python -m tts_bakeoff.run_bakeoff --model X --check` on the target machine first.
"""
from __future__ import annotations

import importlib
import time
import wave
from pathlib import Path


class AdapterError(RuntimeError):
    pass


def have(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except Exception:  # noqa: BLE001 - any import failure means "not usable here"
        return False


def write_wav(path: Path | str, samples, sample_rate: int) -> float:
    """Write mono float or int16 samples to a 16-bit PCM wav; return duration in seconds."""
    import numpy as np

    arr = np.asarray(samples)
    if arr.ndim > 1:
        arr = arr.reshape(-1) if arr.shape[0] == 1 else arr.mean(axis=0 if arr.shape[0] < arr.shape[-1] else 1)
    if arr.dtype.kind == "f":
        arr = np.clip(arr, -1.0, 1.0)
        arr = (arr * 32767.0).astype("<i2")
    else:
        arr = arr.astype("<i2")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sample_rate))
        w.writeframes(arr.tobytes())
    return len(arr) / float(sample_rate)


class Adapter:
    name = "base"
    languages: set[str] = set()
    requires: tuple[str, ...] = ()  # python modules that must import
    env: tuple[str, ...] = ()  # environment variables that must be set

    def __init__(self, **options):
        self.options = options
        self._model = None

    def supports(self, lang: str) -> bool:
        return lang in self.languages

    def check(self) -> dict:
        import os

        problems = [f"python module '{m}' is not importable" for m in self.requires if not have(m)]
        problems += [f"environment variable {e} is not set" for e in self.env if not os.environ.get(e)]
        return {"ok": not problems, "problems": problems, "languages": sorted(self.languages)}

    def load(self):  # pragma: no cover - needs real model
        raise NotImplementedError

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:  # pragma: no cover
        """Write out_wav and return the sample rate."""
        raise NotImplementedError

    def synthesize(self, text: str, lang: str, out_wav: Path | str) -> dict:
        if not self.supports(lang):
            raise AdapterError(f"{self.name} does not support language {lang!r}")
        out = Path(out_wav)
        out.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        sample_rate = self._synth(text, lang, out)
        synth_s = time.perf_counter() - started
        with wave.open(str(out), "rb") as w:
            duration = w.getnframes() / float(w.getframerate())
        return {"duration_s": duration, "synth_s": synth_s, "sample_rate": sample_rate, "rtf": synth_s / duration if duration else None}
