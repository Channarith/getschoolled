"""Wav2ARKit ONNX — native aarch64 audio → 52 ARKit blendshapes (CPU).

Model: https://huggingface.co/myned-ai/wav2arkit_cpu (Apache-2.0)
Downloads once into WAV2ARKIT_MODEL_DIR (default ~/.cache/aoep/wav2arkit).
"""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path
from typing import Optional

import numpy as np

from arkit_names import ARKIT_52

HF_BASE = "https://huggingface.co/myned-ai/wav2arkit_cpu/resolve/main"
MODEL_NAME = "wav2arkit_cpu.onnx"
# External weights blob referenced by the ONNX graph (~383 MiB).
MODEL_DATA_NAME = "wav2arkit_cpu.onnx.data"
TARGET_SR = 16000


def model_dir() -> Path:
    raw = os.environ.get("WAV2ARKIT_MODEL_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".cache" / "aoep" / "wav2arkit"


def _download(url: str, dest: Path, *, min_bytes: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size >= min_bytes:
        return
    tmp = dest.with_suffix(dest.suffix + ".partial")
    urllib.request.urlretrieve(url, tmp)
    if tmp.stat().st_size < min_bytes:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"download too small for {dest.name}: {tmp}")
    tmp.replace(dest)


def ensure_model(path: Optional[Path] = None) -> Path:
    """Download ONNX graph + external .data weights if missing."""
    dest = path or (model_dir() / MODEL_NAME)
    data = dest.parent / MODEL_DATA_NAME
    _download(f"{HF_BASE}/{MODEL_NAME}", dest, min_bytes=100_000)
    _download(f"{HF_BASE}/{MODEL_DATA_NAME}", data, min_bytes=50_000_000)
    return dest


class Wav2ARKit:
    """CPU ONNX session: float32 PCM @ 16 kHz → [frames, 52] blendshapes."""

    def __init__(self, model_path: Optional[Path] = None) -> None:
        import onnxruntime as ort

        self.model_path = ensure_model(model_path)
        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self.blend_names = list(ARKIT_52)

    def infer_pcm16(self, pcm: np.ndarray, sample_rate: int = TARGET_SR) -> np.ndarray:
        """Return float32 array shaped [frames, 52] in [0, 1]."""
        if pcm.dtype != np.int16:
            pcm = pcm.astype(np.int16)
        if sample_rate != TARGET_SR:
            from scipy import signal

            n_out = int(round(len(pcm) * float(TARGET_SR) / float(sample_rate)))
            flo = pcm.astype(np.float32) / 32768.0
            flo = signal.resample(flo, max(n_out, 1))
        else:
            flo = pcm.astype(np.float32) / 32768.0
        if flo.size == 0:
            flo = np.zeros(TARGET_SR // 30, dtype=np.float32)
        audio = flo.reshape(1, -1)
        out = self.session.run([self.output_name], {self.input_name: audio})[0]
        # Expected [batch, frames, 52]
        arr = np.asarray(out, dtype=np.float32)
        if arr.ndim == 3:
            arr = arr[0]
        return np.clip(arr, 0.0, 1.0)
