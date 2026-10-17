"""Compact appearance embedding for object identification.

The vector is deterministic and needs no downloaded weights, so the training
queue can enroll as many objects as you have labeled views. Lighting-stable
enough for same-object views; different-looking objects land far apart.
"""

from __future__ import annotations

import numpy as np

EMBED_DIM = 80


def _resize(image: np.ndarray, size: int = 32) -> np.ndarray:
    height, width = image.shape[:2]
    if height < 1 or width < 1:
        return np.zeros((size, size, 3), dtype=np.uint8)
    ys = np.linspace(0, height - 1, size).astype(np.int32)
    xs = np.linspace(0, width - 1, size).astype(np.int32)
    return image[ys][:, xs]


def embed_rgb(image: np.ndarray) -> np.ndarray:
    """Return an L2-normalized ``EMBED_DIM`` vector for an RGB uint8 crop."""
    rgb = np.asarray(image)
    if rgb.ndim == 2:
        rgb = np.stack([rgb, rgb, rgb], axis=-1)
    rgb = rgb[:, :, :3]
    small = _resize(rgb).astype(np.float32)
    parts: list[np.ndarray] = []
    for channel in range(3):
        hist, _ = np.histogram(small[:, :, channel], bins=8, range=(0.0, 255.0))
        parts.append(hist.astype(np.float32))
    hist_vec = np.concatenate(parts)
    hist_vec = hist_vec / (hist_vec.sum() + 1e-6)
    grid = small.reshape(4, 8, 4, 8, 3).mean(axis=(1, 3)).reshape(-1) / 255.0
    gray = small.mean(axis=2)
    mag = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    mag += np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    grad, _ = np.histogram(mag, bins=8, range=(0.0, 255.0))
    grad_vec = grad.astype(np.float32)
    grad_vec = grad_vec / (grad_vec.sum() + 1e-6)
    vec = np.concatenate([hist_vec, grid, grad_vec]).astype(np.float32)
    if vec.shape[0] != EMBED_DIM:
        raise RuntimeError(f"embedding dim {vec.shape[0]} != {EMBED_DIM}")
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec
