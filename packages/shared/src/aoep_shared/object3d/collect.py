"""Save labeled camera views, then stop when that object leaves the frame.

Pictures land in ``output/object3d/samples/<label>/`` so
``scripts/object3d_train.py`` can train them later. The live loop samples the
video at a rate tied to the camera fps, and only keeps a frame when the view
has changed.
"""

from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from .embed import embed_rgb
from .pipeline import crop_rgb
from .types import Frame, Observation

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def folder_name(label: str) -> str:
    """A single path segment. Slashes and other punctuation become spaces."""
    cleaned = []
    for char in label or "":
        if char.isalnum() or char in " ._-'":
            cleaned.append(char)
        else:
            cleaned.append(" ")
    name = " ".join("".join(cleaned).split()).strip(" .")
    if not name or set(name) <= {".", " "}:
        raise ValueError("object label is empty")
    return name[:80]


def shots_per_second(fps: float) -> float:
    """How many training stills to consider each second, from the live fps."""
    rate = float(fps) if fps and fps > 0 else 4.0
    return max(0.5, min(4.0, rate / 4.0))


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.dot(left, right))


def _iou(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = left
    bx, by, bw, bh = right
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    union = aw * ah + bw * bh - inter
    if union <= 0:
        return 0.0
    return inter / float(union)


def write_png(path: Path, rgb: np.ndarray) -> None:
    """Write an RGB PNG with the stdlib. The training script reads these."""
    image = np.asarray(rgb)
    if image.ndim == 2:
        image = np.stack([image, image, image], axis=-1)
    image = np.clip(image[:, :, :3], 0, 255).astype(np.uint8)
    height, width = image.shape[:2]

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = b"".join(b"\x00" + image[y].tobytes() for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def _image_count(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    return sum(1 for path in folder.iterdir() if path.suffix.lower() in _IMAGE_SUFFIXES)


def _next_index(folder: Path) -> int:
    best = 0
    if folder.is_dir():
        for path in folder.iterdir():
            if path.suffix.lower() not in _IMAGE_SUFFIXES:
                continue
            try:
                best = max(best, int(path.stem))
            except ValueError:
                continue
    return best + 1


@dataclass
class AngleCapture:
    """One labeled object being photographed from new angles."""

    label: str
    folder: Path
    reference: np.ndarray
    saved_emb: np.ndarray
    saved_view: np.ndarray
    saved_bbox: tuple[int, int, int, int]
    last_bbox: tuple[int, int, int, int]
    recent: np.ndarray
    saved: int = 0
    misses: int = 0
    active: bool = True
    reason: str = "capturing"
    last_save: float = 0.0
    kind: str = ""
    maker: str = ""
    year: Optional[int] = None
    heat_c: Optional[float] = None
    smell: str = ""
    texture: str = ""
    camera: str = ""

    @classmethod
    def begin(
        cls,
        root: Path,
        label: str,
        crop: np.ndarray,
        bbox: tuple[int, int, int, int],
        *,
        now: float,
        kind: str = "",
        maker: str = "",
        year: Optional[int] = None,
        heat_c: Optional[float] = None,
        smell: str = "",
        texture: str = "",
        camera: str = "",
    ) -> "AngleCapture":
        name = folder_name(label)
        folder = Path(root) / name
        folder.mkdir(parents=True, exist_ok=True)
        embedding = embed_rgb(np.asarray(crop))
        view = _view_image(crop)
        job = cls(
            label=name,
            folder=folder,
            reference=embedding,
            saved_emb=embedding,
            saved_view=view,
            saved_bbox=bbox,
            last_bbox=bbox,
            recent=embedding,
            kind=kind,
            maker=maker.strip(),
            year=int(year) if year else None,
            heat_c=heat_c,
            smell=smell.strip(),
            texture=texture.strip(),
            camera=camera,
            last_save=float(now),
        )
        job._write_crop(crop)
        return job

    def status(self) -> dict:
        return {
            "active": self.active,
            "label": self.label,
            "saved": self.saved,
            "reason": self.reason,
            "folder": str(self.folder),
        }

    def stop(self, reason: str) -> None:
        self.active = False
        self.reason = reason
        self._write_meta()

    def step(
        self,
        frame: Frame,
        observations: list[Observation],
        *,
        now: float,
        fps: float,
    ) -> Optional[int]:
        """Track the labeled object. Save a new angle, or stop once it is gone.

        Returns the observation index while the object is still in frame.
        """
        if not self.active:
            return None
        matched = self._match(frame, observations)
        if matched is None:
            self.misses += 1
            rate = float(fps) if fps and fps > 0 else 4.0
            rate = min(rate, 15.0)
            if self.misses >= max(4, int(round(rate))):
                self.stop("object left the frame")
            return None
        index, obs, embedding = matched
        self.misses = 0
        self.last_bbox = obs.bbox
        self.recent = embedding
        gap = 1.0 / shots_per_second(fps)
        crop = crop_rgb(frame.rgb, obs.bbox)
        view = _view_image(crop)
        changed = _view_changed(view, self.saved_view, obs.bbox, self.saved_bbox)
        if changed and (float(now) - self.last_save) >= gap:
            self._write_crop(crop)
            self.saved_emb = embedding
            self.saved_view = view
            self.saved_bbox = obs.bbox
            self.last_save = float(now)
        return index

    def _match(
        self,
        frame: Frame,
        observations: list[Observation],
    ) -> Optional[tuple[int, Observation, np.ndarray]]:
        best = None
        best_score = -1.0
        for index, obs in enumerate(observations):
            overlap = _iou(obs.bbox, self.last_bbox)
            embedding = embed_rgb(crop_rgb(frame.rgb, obs.bbox))
            similar = max(_cosine(embedding, self.recent), _cosine(embedding, self.reference))
            if overlap < 0.12 and similar < 0.72:
                continue
            score = overlap + similar
            if score > best_score:
                best_score = score
                best = (index, obs, embedding)
        return best

    def _write_crop(self, crop: np.ndarray) -> None:
        index = _next_index(self.folder)
        write_png(self.folder / f"{index:04d}.png", crop)
        self.saved = _image_count(self.folder)
        self._write_meta()

    def _write_meta(self) -> None:
        payload = {
            "maker": self.maker,
            "year": self.year,
            "kind": self.kind,
            "celsius": self.heat_c,
            "smell": self.smell,
            "texture": self.texture,
            "camera": self.camera,
            "views": self.saved,
        }
        (self.folder / "meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _view_image(crop: np.ndarray) -> np.ndarray:
    """32x32 RGB stand-in so two angles can be compared without the ID embedding."""
    rgb = np.asarray(crop)
    if rgb.ndim == 2:
        rgb = np.stack([rgb, rgb, rgb], axis=-1)
    rgb = rgb[:, :, :3]
    height, width = rgb.shape[:2]
    if height < 1 or width < 1:
        return np.zeros((32, 32, 3), dtype=np.uint8)
    ys = np.linspace(0, max(height - 1, 0), 32).astype(np.int32)
    xs = np.linspace(0, max(width - 1, 0), 32).astype(np.int32)
    return np.ascontiguousarray(rgb[ys][:, xs])


def _view_changed(
    current: np.ndarray,
    saved: np.ndarray,
    bbox: tuple[int, int, int, int],
    previous: tuple[int, int, int, int],
) -> bool:
    # Depth boxes jitter by about 15 levels. A real turn of the object is larger.
    delta = float(np.mean(np.abs(current.astype(np.float32) - saved.astype(np.float32))))
    if delta >= 24.0:
        return True
    return _scale_changed(bbox, previous)


def _scale_changed(bbox: tuple[int, int, int, int], previous: tuple[int, int, int, int]) -> bool:
    area = max(1, int(bbox[2]) * int(bbox[3]))
    before = max(1, int(previous[2]) * int(previous[3]))
    return abs(area - before) / float(before) > 0.18
