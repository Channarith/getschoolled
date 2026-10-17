"""Frames, detections, and spoken answers for the 3D object pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import numpy as np

from .sensors import SensorBundle


@dataclass
class Frame:
    """One RGB view plus optional depth and later sensor readings."""

    rgb: np.ndarray
    depth: Optional[np.ndarray] = None
    # Multiply raw depth values by this to get meters. RealSense Z16 uses 0.001.
    depth_scale: float = 0.001
    camera: str = ""
    sensors: SensorBundle = field(default_factory=SensorBundle)


@dataclass
class Detection:
    """An object box before distance and identity are attached."""

    label: str
    score: float
    bbox: tuple[int, int, int, int]  # x, y, w, h
    kind: str
    source: str


@dataclass
class Observation:
    """What the camera can say about one object."""

    label: str
    score: float
    bbox: tuple[int, int, int, int]
    distance_m: Optional[float]
    kind: str
    camera: str = ""
    source: str = ""
    identified: Optional[str] = None
    identify_score: float = 0.0
    maker: str = ""
    year: Optional[int] = None
    # Live sensor or a value remembered from training. Empty source means unknown.
    heat_c: Optional[float] = None
    heat_source: str = ""  # heat, thermal, trained
    smell: str = ""
    smell_intensity: Optional[float] = None
    smell_source: str = ""  # sensor, trained
    texture: str = ""
    force_n: Optional[float] = None
    touch_source: str = ""  # sensor, trained

    @property
    def name(self) -> str:
        return self.identified or self.label or "object"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["name"] = self.name
        if self.distance_m is not None:
            data["distance_m"] = round(float(self.distance_m), 3)
        if self.heat_c is not None:
            data["heat_c"] = round(float(self.heat_c), 1)
        if self.force_n is not None:
            data["force_n"] = round(float(self.force_n), 3)
        return data


@dataclass
class Answer:
    """A sentence a voice agent can speak, plus the facts it came from."""

    text: str
    intent: str
    facts: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainSample:
    """One labeled view for the identification gallery."""

    label: str
    image: np.ndarray
    maker: str = ""
    year: Optional[int] = None
    kind: str = ""
    heat_c: Optional[float] = None
    smell: str = ""
    smell_intensity: Optional[float] = None
    texture: str = ""
    force_n: Optional[float] = None


@dataclass
class TrainReport:
    views: int
    objects: int
    labels: list[str]
