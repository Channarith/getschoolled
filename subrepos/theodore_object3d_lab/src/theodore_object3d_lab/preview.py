"""Make a camera frame readable: contrast on color, a full depth picture.

Missing depth used to be painted black, so a sparse RealSense map looked cut
off. Small holes are filled for the picture only. Large gaps keep the color
frame underneath, dimmed, and distance still uses the measured pixels.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

# Nine stops of the turbo map, dark blue (near) through green to dark red (far).
_STOPS = np.array(
    [
        [48, 18, 59],
        [62, 70, 204],
        [28, 146, 232],
        [20, 214, 176],
        [122, 246, 72],
        [214, 236, 46],
        [250, 186, 40],
        [236, 96, 22],
        [122, 4, 3],
    ],
    dtype=np.float32,
)


def turbo(values: np.ndarray) -> np.ndarray:
    """Map 0..1 to RGB. 0 is near (blue), 1 is far (red)."""
    x = np.clip(np.asarray(values, dtype=np.float32), 0, 1) * 8
    index = np.minimum(np.floor(x).astype(np.int32), 7)
    frac = (x - index)[..., None]
    left = _STOPS[index]
    right = _STOPS[index + 1]
    return (left * (1 - frac) + right * frac).astype(np.uint8)


def _cv2():
    try:
        import cv2
    except Exception:
        return None
    return cv2


def fill_small_holes(depth: np.ndarray, passes: int = 4) -> np.ndarray:
    """Fill only pixels that already have two measured neighbors.

    A pass grows the valid region by about one pixel, so a handful of passes
    closes speckle without painting a whole missing wall.
    """
    out = np.asarray(depth, dtype=np.float32).copy()
    for _ in range(max(0, passes)):
        valid = out > 0
        acc = np.zeros_like(out)
        count = np.zeros(out.shape, dtype=np.float32)
        acc[1:] += np.where(valid[:-1], out[:-1], 0)
        count[1:] += valid[:-1]
        acc[:-1] += np.where(valid[1:], out[1:], 0)
        count[:-1] += valid[1:]
        acc[:, 1:] += np.where(valid[:, :-1], out[:, :-1], 0)
        count[:, 1:] += valid[:, :-1]
        acc[:, :-1] += np.where(valid[:, 1:], out[:, 1:], 0)
        count[:, :-1] += valid[:, 1:]
        need = (~valid) & (count >= 2)
        out[need] = acc[need] / count[need]
    return out


def depth_stats(depth: np.ndarray, scale: float) -> dict[str, Any]:
    meters = np.asarray(depth, dtype=np.float32) * float(scale)
    valid = np.isfinite(meters) & (meters > 0.05) & (meters < 20)
    coverage = float(valid.mean()) if meters.size else 0.0
    near_m = None
    far_m = None
    if valid.any():
        lo, hi = np.percentile(meters[valid], [4, 96])
        near_m = round(float(max(0.15, lo)), 2)
        far_m = round(float(max(near_m + 0.25, hi)), 2)
    hint = ""
    if coverage < 0.35:
        hint = (
            "Most of this frame has no depth. Aim at a surface between "
            "0.3 m and 3 m. A USB 3 cable returns a denser map."
        )
    return {
        "coverage": round(coverage, 3),
        "scene_near_m": near_m,
        "scene_far_m": far_m,
        "hint": hint,
    }


def colorize_depth(
    depth: np.ndarray,
    scale: float,
    rgb: Optional[np.ndarray],
    *,
    near_m: float = 0.3,
    far_m: float = 4.0,
    auto_range: bool = True,
    fill_holes: bool = True,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Color the measured range and keep the photo visible where depth is missing."""
    raw = np.asarray(depth)
    stats = depth_stats(raw, scale)
    show = fill_small_holes(raw) if fill_holes else np.asarray(raw, dtype=np.float32)
    near = float(near_m)
    far = float(far_m)
    if auto_range and stats["scene_near_m"] is not None:
        near = float(stats["scene_near_m"])
        far = float(stats["scene_far_m"])
    if far <= near:
        far = near + 0.3
    meters = show.astype(np.float32) * float(scale)
    span = max(1e-3, far - near)
    norm = np.clip((meters - near) / span, 0, 1)
    colored = turbo(norm)
    holes = show <= 0
    if rgb is not None and rgb.shape[:2] == colored.shape[:2]:
        under = rgb.astype(np.float32) * 0.42 + 8
        colored[holes] = under[holes].astype(np.uint8)
    else:
        colored[holes] = (8, 28, 36)
    colored = _legend(colored)
    stats["range_near_m"] = round(near, 2)
    stats["range_far_m"] = round(far, 2)
    return colored, stats


def _legend(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    bar_h = max(8, height // 28)
    xs = np.linspace(0, 1, width, dtype=np.float32)
    bar = turbo(np.broadcast_to(xs, (bar_h, width)))
    out = image.copy()
    out[-bar_h:] = bar
    return out


def no_depth_view(rgb: np.ndarray, message: str) -> np.ndarray:
    image = (np.asarray(rgb, dtype=np.float32) * 0.4 + 8).astype(np.uint8)
    return banner(image, message)


def banner(image: np.ndarray, message: str) -> np.ndarray:
    out = np.asarray(image).copy()
    cv2 = _cv2()
    if cv2 is None or not message:
        return out
    bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
    cv2.putText(
        bgr,
        message[:64],
        (16, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (210, 236, 236),
        1,
        cv2.LINE_AA,
    )
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def enhance_color(rgb: np.ndarray, *, clahe: bool = True, sharpen: float = 0.35) -> np.ndarray:
    """Lift a dark frame for the preview. Recognition keeps the camera frame."""
    image = np.ascontiguousarray(rgb)
    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)
    else:
        image = image.copy()
    cv2 = _cv2()
    if cv2 is None:
        return _stretch(image) if clahe else image
    if clahe:
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        lightness, green, blue = cv2.split(lab)
        lightness = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(lightness)
        image = cv2.cvtColor(cv2.merge((lightness, green, blue)), cv2.COLOR_LAB2RGB)
    amount = float(sharpen or 0)
    if amount > 0:
        blurred = cv2.GaussianBlur(image, (0, 0), 1.1)
        image = cv2.addWeighted(image, 1.0 + amount, blurred, -amount, 0)
    return np.clip(image, 0, 255).astype(np.uint8)


def _stretch(image: np.ndarray) -> np.ndarray:
    flat = image.astype(np.float32)
    lo, hi = np.percentile(flat, [2, 98])
    if hi <= lo:
        return image
    return np.clip((flat - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)


def draw_overlay(rgb: np.ndarray, observations: list[Any]) -> np.ndarray:
    cv2 = _cv2()
    if cv2 is None or not observations:
        return rgb
    bgr = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2BGR)
    for obs in observations:
        x, y, w, h = (int(v) for v in obs.bbox)
        cv2.rectangle(bgr, (x, y), (x + w, y + h), (198, 210, 62), 2)
        meters = getattr(obs, "distance_m", None)
        name = getattr(obs, "name", None) or getattr(obs, "label", "object")
        text = name if meters is None else f"{name} {float(meters):.2f} m"
        text_x = min(max(4, x), max(4, bgr.shape[1] - 8 * len(text)))
        text_y = y - 6 if y > 22 else min(bgr.shape[0] - 8, y + 16)
        cv2.putText(
            bgr,
            text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (236, 246, 248),
            1,
            cv2.LINE_AA,
        )
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def waiting_image(message: str, width: int = 640, height: int = 360) -> np.ndarray:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = (7, 28, 36)
    return banner(image, message)


def jpeg_bytes(rgb: np.ndarray, quality: int = 88) -> bytes:
    cv2 = _cv2()
    if cv2 is not None:
        bgr = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2BGR)
        ok, buf = cv2.imencode(
            ".jpg",
            bgr,
            [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)],
        )
        if ok:
            return buf.tobytes()
    from io import BytesIO

    from PIL import Image

    out = BytesIO()
    Image.fromarray(np.ascontiguousarray(rgb)).save(out, format="JPEG", quality=int(quality))
    return out.getvalue()
