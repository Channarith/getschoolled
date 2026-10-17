"""Identification gallery: running-mean prototypes, saved as JSON."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from .embed import EMBED_DIM


def _blend_mean(rec: dict, value_key: str, count_key: str, sample: Optional[float]) -> None:
    """Running mean. A missing sample leaves the stored value alone."""
    if sample is None:
        return
    sample_f = float(sample)
    count = int(rec.get(count_key) or 0)
    current = rec.get(value_key)
    if current is None or count <= 0:
        rec[value_key] = sample_f
        rec[count_key] = 1
        return
    count += 1
    rec[value_key] = (float(current) * (count - 1) + sample_f) / count
    rec[count_key] = count


@dataclass
class GalleryHit:
    label: str
    score: float
    maker: str
    year: Optional[int]
    kind: str
    views: int
    heat_c: Optional[float] = None
    smell: str = ""
    smell_intensity: Optional[float] = None
    texture: str = ""
    force_n: Optional[float] = None


class ObjectGallery:
    """Cosine gallery of enrolled objects. Safe to update from training workers."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self._objects: dict[str, dict] = {}
        if self.path and self.path.is_file():
            self.load(self.path)

    def __len__(self) -> int:
        with self._lock:
            return len(self._objects)

    def labels(self) -> list[str]:
        with self._lock:
            return sorted(self._objects)

    def enroll(
        self,
        label: str,
        embedding: np.ndarray,
        *,
        maker: str = "",
        year: Optional[int] = None,
        kind: str = "",
        heat_c: Optional[float] = None,
        smell: str = "",
        smell_intensity: Optional[float] = None,
        texture: str = "",
        force_n: Optional[float] = None,
    ) -> int:
        """Fold one view into ``label``. Returns how many views that object has."""
        name = " ".join((label or "").split())
        if not name:
            raise ValueError("object label is empty")
        vec = np.asarray(embedding, dtype=np.float32).reshape(-1)
        if vec.shape[0] != EMBED_DIM:
            raise ValueError(f"embedding must be {EMBED_DIM}-d, got {vec.shape[0]}")
        norm = float(np.linalg.norm(vec))
        if norm == 0:
            raise ValueError("embedding is zero")
        vec = vec / norm
        with self._lock:
            rec = self._objects.get(name)
            if rec is None:
                rec = {
                    "prototype": vec,
                    "count": 1,
                    "maker": maker.strip(),
                    "year": int(year) if year else None,
                    "kind": kind.strip(),
                    "heat_c": float(heat_c) if heat_c is not None else None,
                    "heat_n": 1 if heat_c is not None else 0,
                    "smell": smell.strip(),
                    "smell_intensity": float(smell_intensity) if smell_intensity is not None else None,
                    "smell_n": 1 if smell_intensity is not None else 0,
                    "texture": texture.strip(),
                    "force_n": float(force_n) if force_n is not None else None,
                    "force_n_count": 1 if force_n is not None else 0,
                }
                self._objects[name] = rec
                return 1
            count = int(rec["count"])
            merged = (rec["prototype"] * count + vec) / (count + 1)
            merged_norm = float(np.linalg.norm(merged))
            rec["prototype"] = merged / merged_norm if merged_norm else merged
            rec["count"] = count + 1
            if maker.strip():
                rec["maker"] = maker.strip()
            if year:
                rec["year"] = int(year)
            if kind.strip():
                rec["kind"] = kind.strip()
            _blend_mean(rec, "heat_c", "heat_n", heat_c)
            _blend_mean(rec, "smell_intensity", "smell_n", smell_intensity)
            _blend_mean(rec, "force_n", "force_n_count", force_n)
            if smell.strip():
                rec["smell"] = smell.strip()
            if texture.strip():
                rec["texture"] = texture.strip()
            return int(rec["count"])

    def match(self, embedding: np.ndarray, *, threshold: float = 0.75) -> Optional[GalleryHit]:
        vec = np.asarray(embedding, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        if norm == 0 or not self._objects:
            return None
        vec = vec / norm
        best_label = ""
        best_score = -1.0
        best: Optional[dict] = None
        with self._lock:
            items = list(self._objects.items())
        for label, rec in items:
            score = float(np.dot(vec, rec["prototype"]))
            if score > best_score:
                best_score = score
                best_label = label
                best = rec
        if best is None or best_score < threshold:
            return None
        return GalleryHit(
            label=best_label,
            score=best_score,
            maker=str(best.get("maker") or ""),
            year=best.get("year"),
            kind=str(best.get("kind") or ""),
            views=int(best.get("count") or 0),
            heat_c=best.get("heat_c"),
            smell=str(best.get("smell") or ""),
            smell_intensity=best.get("smell_intensity"),
            texture=str(best.get("texture") or ""),
            force_n=best.get("force_n"),
        )

    def save(self, path: Optional[Path] = None) -> Path:
        target = Path(path or self.path or "")
        if not str(target):
            raise ValueError("gallery path is not set")
        with self._lock:
            payload = {
                "version": 1,
                "dim": EMBED_DIM,
                "objects": {
                    label: {
                        "maker": rec.get("maker") or "",
                        "year": rec.get("year"),
                        "kind": rec.get("kind") or "",
                        "count": int(rec["count"]),
                        "heat_c": rec.get("heat_c"),
                        "heat_n": int(rec.get("heat_n") or 0),
                        "smell": rec.get("smell") or "",
                        "smell_intensity": rec.get("smell_intensity"),
                        "smell_n": int(rec.get("smell_n") or 0),
                        "texture": rec.get("texture") or "",
                        "force_n": rec.get("force_n"),
                        "force_n_count": int(rec.get("force_n_count") or 0),
                        "prototype": [round(float(v), 6) for v in rec["prototype"]],
                    }
                    for label, rec in self._objects.items()
                },
            }
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(target)
        self.path = target
        return target

    def load(self, path: Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        objects: dict[str, dict] = {}
        for label, rec in (data.get("objects") or {}).items():
            proto = np.asarray(rec["prototype"], dtype=np.float32)
            objects[str(label)] = {
                "prototype": proto,
                "count": int(rec.get("count") or 1),
                "maker": rec.get("maker") or "",
                "year": rec.get("year"),
                "kind": rec.get("kind") or "",
                "heat_c": rec.get("heat_c"),
                "heat_n": int(rec.get("heat_n") or (1 if rec.get("heat_c") is not None else 0)),
                "smell": rec.get("smell") or "",
                "smell_intensity": rec.get("smell_intensity"),
                "smell_n": int(rec.get("smell_n") or 0),
                "texture": rec.get("texture") or "",
                "force_n": rec.get("force_n"),
                "force_n_count": int(rec.get("force_n_count") or 0),
            }
        with self._lock:
            self._objects = objects
            self.path = Path(path)
