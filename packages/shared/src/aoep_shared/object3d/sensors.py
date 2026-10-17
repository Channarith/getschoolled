"""Touch, smell, heat, and thermal readings.

Nothing here talks to hardware. A later collector fills a SensorBundle (or a
JSON file plus a Celsius .npy) and the camera pipeline attaches it to the
nearest object. Thermal imagery is per object. A single probe is not.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

import numpy as np


@dataclass
class TouchReading:
    """One contact reading. ``texture`` is a short word such as smooth or rough."""

    texture: str = ""
    force_n: Optional[float] = None


@dataclass
class SmellReading:
    label: str = ""
    intensity: Optional[float] = None  # 0..1


@dataclass
class HeatReading:
    celsius: float
    source: str = "heat"  # "heat" probe, or "thermal" imagery


@dataclass
class SensorBundle:
    """Absent fields mean that sensor is not connected."""

    touch: Optional[TouchReading] = None
    smell: Optional[SmellReading] = None
    heat: Optional[HeatReading] = None
    thermal: Optional[np.ndarray] = None  # Celsius, HxW


class SensorSource(Protocol):
    """Implemented later by the touch, gas, or thermal driver."""

    def read(self) -> SensorBundle:
        ...


class DisconnectedSensors:
    """The sensors are not installed yet."""

    def read(self) -> SensorBundle:
        return SensorBundle()


def region_celsius(thermal: np.ndarray, bbox: tuple[int, int, int, int]) -> Optional[float]:
    """Median Celsius inside ``bbox``. Non-finite pixels are ignored."""
    x, y, w, h = bbox
    height, width = thermal.shape[:2]
    x0 = max(0, int(x))
    y0 = max(0, int(y))
    x1 = min(width, int(x + max(w, 1)))
    y1 = min(height, int(y + max(h, 1)))
    if x1 <= x0 or y1 <= y0:
        return None
    crop = np.asarray(thermal[y0:y1, x0:x1], dtype=np.float32)
    valid = crop[np.isfinite(crop)]
    if valid.size < 4:
        return None
    return float(np.median(valid))


def _float_or_none(value) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def bundle_from_mapping(data: dict, thermal: Optional[np.ndarray] = None) -> SensorBundle:
    """Build a bundle from a collector JSON object."""
    touch = None
    texture = str(data.get("texture") or "").strip()
    force = _float_or_none(data.get("force_n", data.get("force")))
    if texture or force is not None:
        touch = TouchReading(texture=texture, force_n=force)
    smell = None
    label = str(data.get("smell") or "").strip()
    intensity = _float_or_none(data.get("smell_intensity", data.get("intensity")))
    if label or intensity is not None:
        smell = SmellReading(label=label, intensity=intensity)
    heat = None
    celsius = _float_or_none(data.get("celsius", data.get("heat_c")))
    if celsius is not None:
        heat = HeatReading(celsius=celsius, source=str(data.get("heat_source") or "heat"))
    if thermal is None and data.get("thermal_npy"):
        thermal = np.load(str(data["thermal_npy"]))
    return SensorBundle(touch=touch, smell=smell, heat=heat, thermal=thermal)


def load_sensor_bundle(
    path: Optional[Path] = None,
    thermal_path: Optional[Path] = None,
    *,
    celsius: Optional[float] = None,
    smell: str = "",
    texture: str = "",
    force_n: Optional[float] = None,
) -> SensorBundle:
    """JSON and CLI flags override each other. CLI wins when it is set."""
    data: dict = {}
    if path is not None and Path(path).is_file():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    thermal = np.load(thermal_path) if thermal_path else None
    bundle = bundle_from_mapping(data, thermal)
    if texture or force_n is not None:
        previous = bundle.touch
        bundle.touch = TouchReading(
            texture=texture or (previous.texture if previous else ""),
            force_n=force_n if force_n is not None else (previous.force_n if previous else None),
        )
    if smell:
        intensity = bundle.smell.intensity if bundle.smell else None
        bundle.smell = SmellReading(label=smell, intensity=intensity)
    if celsius is not None:
        bundle.heat = HeatReading(celsius=float(celsius), source="heat")
    return bundle


def apply_sensors(observations: list, bundle: SensorBundle, image_shape: tuple[int, ...]) -> None:
    """Write live readings onto observations. A probe attaches to the nearest."""
    if bundle.thermal is not None:
        from .depth import align_depth

        thermal = align_depth(np.asarray(bundle.thermal), image_shape)
        for obs in observations:
            med = region_celsius(thermal, obs.bbox)
            if med is None:
                continue
            obs.heat_c = round(med, 1)
            obs.heat_source = "thermal"
    if not observations:
        return
    nearest = observations[0]
    if bundle.heat is not None:
        nearest.heat_c = round(float(bundle.heat.celsius), 1)
        nearest.heat_source = bundle.heat.source or "heat"
    if bundle.smell is not None:
        if bundle.smell.label:
            nearest.smell = bundle.smell.label
            nearest.smell_source = "sensor"
        if bundle.smell.intensity is not None:
            nearest.smell_intensity = bundle.smell.intensity
            nearest.smell_source = "sensor"
    if bundle.touch is not None:
        if bundle.touch.texture:
            nearest.texture = bundle.touch.texture
            nearest.touch_source = "sensor"
        if bundle.touch.force_n is not None:
            nearest.force_n = bundle.touch.force_n
            nearest.touch_source = "sensor"


def live_senses(obs) -> dict:
    """Sensor values worth storing. Catalog copies are left out."""
    return {
        "heat_c": obs.heat_c if obs.heat_source in ("heat", "thermal") else None,
        "smell": obs.smell if obs.smell_source == "sensor" else "",
        "smell_intensity": obs.smell_intensity if obs.smell_source == "sensor" else None,
        "texture": obs.texture if obs.touch_source == "sensor" else "",
        "force_n": obs.force_n if obs.touch_source == "sensor" else None,
    }
