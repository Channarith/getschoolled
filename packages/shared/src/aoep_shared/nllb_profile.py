"""NLLB translation profiles for GPUs with little memory (the iBuyPower's RTX 5060 Ti has 8 GB).

Select with NLLB_PROFILE=8gb or NLLB_PROFILE=8gb-ct2 (unset keeps the old behavior exactly: NLLB_MODEL, NLLB_DTYPE and
NLLB_BATCH_SIZE decide). Explicit NLLB_* variables always win over a profile.

The memory figures are ESTIMATES from parameter counts (weights only, plus a rough allowance for beam-search activations),
not measurements. scripts/nllb_profile_bench.py measures the real peak on the machine; pick with those numbers.

  profile    model                          backend  weights     est. peak at batch 16, 4 beams
  8gb        nllb-200-distilled-1.3B fp16   hf       ~2.6 GiB    ~4-5 GiB
  8gb-ct2    nllb-200-3.3B int8_float16     ct2      ~3.5 GiB    ~5-6 GiB (needs a one-time conversion, see docs)
  (not used) nllb-200-3.3B fp16             hf       ~6.2 GiB    does not leave room for activations on 8 GiB
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Profile:
    name: str
    backend: str  # hf | ct2
    model: str  # HF model id (also the tokenizer source for ct2)
    dtype: str = "fp16"  # hf only
    compute_type: str = ""  # ct2 only
    ct2_dir: str = ""  # ct2 only: converted model folder
    batch: int = 16
    budget_gb: float = 6.5  # keep the process peak under this so the display and CUDA context still fit in 8 GiB
    est_peak_gb: float = 5.0


PROFILES: dict[str, Profile] = {
    "8gb": Profile("8gb", "hf", "facebook/nllb-200-distilled-1.3B", dtype="fp16", batch=16, est_peak_gb=4.5),
    "8gb-ct2": Profile("8gb-ct2", "ct2", "facebook/nllb-200-3.3B", compute_type="int8_float16",
                       ct2_dir="~/models/nllb-200-3.3B-ct2-int8", batch=16, est_peak_gb=5.5),
}


def active() -> Optional[Profile]:
    """The profile named by NLLB_PROFILE, or None. An unknown name is an error, not a silent default."""
    name = (os.environ.get("NLLB_PROFILE") or "").strip().lower()
    if not name or name == "default":
        return None
    if name not in PROFILES:
        raise ValueError(f"unknown NLLB_PROFILE {name!r}; choose one of: {', '.join(sorted(PROFILES))}")
    return PROFILES[name]


def autotune_batch_size(peak_gb: Callable[[int], float], *, budget_gb: float = 6.5, start: int = 4, cap: int = 64) -> int:
    """Largest power-of-two-ish batch whose measured peak memory stays under budget_gb.

    peak_gb(batch) runs one worst-case batch (the longest sentences) and returns the peak GPU memory in GiB; it may raise
    MemoryError / RuntimeError('out of memory'), which counts as over budget. Returns at least 1.
    """
    best, batch = 1, max(1, start)
    while batch <= cap:
        try:
            peak = peak_gb(batch)
        except (MemoryError, RuntimeError) as exc:
            if isinstance(exc, RuntimeError) and "out of memory" not in str(exc).lower():
                raise
            break
        if peak > budget_gb:
            break
        best = batch
        batch *= 2
    return best
