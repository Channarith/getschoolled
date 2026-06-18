#!/usr/bin/env python3
"""Track A.3 - scaling-laws fit (run small proxies, extrapolate the big run).

Fit a power law loss = a * compute^(-b) from cheap proxy runs (log-log least
squares), then predict the loss at the target compute budget so the full run is
de-risked before committing. Pure Python; tested on synthetic power-law data.
"""

from __future__ import annotations

import math
from typing import Dict, Sequence, Tuple


def fit_power_law(points: Sequence[Tuple[float, float]]) -> Dict[str, float]:
    """points: [(compute, loss), ...] with >= 2 distinct compute values."""
    xs = [math.log(c) for c, _ in points]
    ys = [math.log(l) for _, l in points]
    n = len(xs)
    if n < 2:
        raise ValueError("need >= 2 points")
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    if denom == 0:
        raise ValueError("compute values must differ")
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return {"a": math.exp(intercept), "b": -slope}


def predict_loss(fit: Dict[str, float], compute: float) -> float:
    return fit["a"] * compute ** (-fit["b"])
