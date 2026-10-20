"""Object detectors: color blobs, metric depth, and COCO when torchvision is present.

Color blobs do not need a depth map, so an OAK-D Lite on a link with no stereo
still gets boxes. Depth remains the RealSense path. COCO adds class names when
its weights are already available.
"""

from __future__ import annotations

import numpy as np

from .depth import _components, align_depth, depth_detections
from .taxonomy import kind_for
from .types import Detection, Frame

_COCO = None


def _center_inside(inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> bool:
    x, y, w, h = inner
    cx, cy = x + w / 2.0, y + h / 2.0
    ox, oy, ow, oh = outer
    return ox <= cx <= ox + ow and oy <= cy <= oy + oh


class CocoDetector:
    """SSDLite MobileNetV3 trained on COCO. Loaded on first use."""

    def __init__(self, score: float = 0.45, limit: int = 15) -> None:
        self.score = score
        self.limit = limit
        self._model = None
        self._categories: list[str] = []
        self._device = "cpu"

    def available(self) -> bool:
        try:
            import torch  # noqa: F401
            import torchvision  # noqa: F401
        except ImportError:
            return False
        return True

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from torchvision.models.detection import (
            SSDLite320_MobileNet_V3_Large_Weights,
            ssdlite320_mobilenet_v3_large,
        )

        weights = SSDLite320_MobileNet_V3_Large_Weights.DEFAULT
        model = ssdlite320_mobilenet_v3_large(weights=weights)
        model.eval()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = model.to(device)
        self._categories = list(weights.meta["categories"])
        self._device = device

    def detect(self, rgb: np.ndarray) -> list[Detection]:
        import torch

        self._load()
        image = np.asarray(rgb)
        if image.ndim != 3 or image.shape[2] < 3:
            return []
        tensor = torch.from_numpy(np.transpose(image[:, :, :3], (2, 0, 1))).float().div(255.0)
        with torch.no_grad():
            pred = self._model([tensor.to(self._device)])[0]
        boxes = pred["boxes"].detach().cpu().numpy()
        labels = pred["labels"].detach().cpu().numpy()
        scores = pred["scores"].detach().cpu().numpy()
        found: list[Detection] = []
        order = np.argsort(-scores)
        for index in order:
            score = float(scores[index])
            if score < self.score:
                break
            class_id = int(labels[index])
            name = self._categories[class_id] if class_id < len(self._categories) else ""
            if not name or name.upper() == "N/A":
                continue
            x0, y0, x1, y1 = boxes[index]
            bbox = (int(x0), int(y0), max(1, int(x1 - x0)), max(1, int(y1 - y0)))
            found.append(Detection(
                label=name,
                score=score,
                bbox=bbox,
                kind=kind_for(name),
                source="coco",
            ))
            if len(found) >= self.limit:
                break
        return found


def coco_detector() -> CocoDetector:
    global _COCO
    if _COCO is None:
        _COCO = CocoDetector()
    return _COCO


def color_detections(
    rgb: np.ndarray,
    *,
    max_side: int = 160,
    limit: int = 8,
) -> list[Detection]:
    """Boxes around regions that differ from the border color.

    No weights and no depth. Two surfaces of different colors stay separate
    even when they touch, because the mask is binned by color.
    """
    image = np.asarray(rgb)
    if image.ndim != 3 or image.shape[2] < 3 or image.size == 0:
        return []
    height, width = int(image.shape[0]), int(image.shape[1])
    if height < 8 or width < 8:
        return []
    step = max(1, int(max(height, width) / max_side))
    small = image[::step, ::step, :3].astype(np.float32)
    sh, sw = small.shape[:2]
    ring = max(1, int(round(min(sh, sw) * 0.08)))
    border = np.concatenate([
        small[:ring].reshape(-1, 3),
        small[-ring:].reshape(-1, 3),
        small[:, :ring].reshape(-1, 3),
        small[:, -ring:].reshape(-1, 3),
    ])
    background = np.median(border, axis=0)
    distance = np.linalg.norm(small - background, axis=2)
    median = float(np.median(distance))
    mad = float(np.median(np.abs(distance - median)))
    thresh = max(28.0, median + 3.0 * max(mad, 1e-3))
    mask = distance > thresh
    if int(mask.sum()) < 12:
        return []
    quantized = (small // 64).astype(np.int32)
    code = quantized[:, :, 0] * 16 + quantized[:, :, 1] * 4 + quantized[:, :, 2] + 1
    band = np.where(mask, code, 0).astype(np.int32)
    min_cells = max(12, int(0.003 * sh * sw))
    frame_area = float(height * width)
    found: list[tuple[float, Detection]] = []
    for x, y, w, h in _components(band, min_cells):
        bbox = (
            int(x * step),
            int(y * step),
            max(1, int(w * step)),
            max(1, int(h * step)),
        )
        if bbox[2] < 4 or bbox[3] < 4:
            continue
        if bbox[2] * bbox[3] > 0.7 * frame_area:
            continue
        x0 = max(0, min(sw - 1, x))
        y0 = max(0, min(sh - 1, y))
        x1 = max(x0 + 1, min(sw, x + w))
        y1 = max(y0 + 1, min(sh, y + h))
        score = float(np.mean(distance[y0:y1, x0:x1]))
        found.append((score, Detection(
            label="object",
            score=round(min(1.0, score / 80.0), 3),
            bbox=bbox,
            kind=kind_for("object"),
            source="color",
        )))
    found.sort(key=lambda item: item[0], reverse=True)
    return [det for _, det in found[:limit]]


def detect(frame: Frame, mode: str = "auto") -> list[Detection]:
    """Find objects in ``frame``.

    ``color`` uses the picture alone. ``depth`` uses the depth map. ``coco``
    uses SSDLite when torchvision is installed. ``auto`` uses COCO names when
    that model loads, then depth blobs outside those boxes, then color when
    neither path found anything.
    """
    mode = (mode or "auto").casefold()
    if mode == "color":
        return color_detections(frame.rgb)
    coco: list[Detection] = []
    if mode in ("auto", "coco"):
        detector = coco_detector()
        if detector.available():
            try:
                coco = detector.detect(frame.rgb)
            except Exception:
                if mode == "coco":
                    raise
                coco = []
        elif mode == "coco":
            raise RuntimeError("COCO detector is not available (torchvision missing)")
    blobs: list[Detection] = []
    if mode in ("auto", "depth") and frame.depth is not None:
        depth = align_depth(frame.depth, frame.rgb.shape)
        blobs = depth_detections(depth, frame.depth_scale)
        blobs = [
            blob for blob in blobs
            if not any(_center_inside(blob.bbox, det.bbox) for det in coco)
        ]
    if mode == "depth":
        return blobs
    if mode == "coco":
        return coco
    found = coco + blobs
    if found:
        return found
    return color_detections(frame.rgb)
