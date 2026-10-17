"""Object detectors: metric depth blobs, and COCO when torchvision is present."""

from __future__ import annotations

import numpy as np

from .depth import align_depth, depth_detections
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


def detect(frame: Frame, mode: str = "auto") -> list[Detection]:
    """Find objects in ``frame``.

    ``auto`` uses COCO when the weights load, and always adds depth blobs that
    are not already inside a COCO box. ``depth`` and ``coco`` force one path.
    """
    mode = (mode or "auto").casefold()
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
    return coco + blobs
