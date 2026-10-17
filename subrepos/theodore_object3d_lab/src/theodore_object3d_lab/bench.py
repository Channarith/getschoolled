"""Offline bench: two depth objects, then recognition and questions.

No camera and no model download. The same checks run in pytest and in the lab.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from aoep_shared.object3d.ask import answer_about
from aoep_shared.object3d.gallery import ObjectGallery
from aoep_shared.object3d.pipeline import crop_rgb, observe
from aoep_shared.object3d.sensors import HeatReading, SensorBundle, SmellReading, TouchReading
from aoep_shared.object3d.train import train_samples_blocking
from aoep_shared.object3d.types import Frame, TrainSample


def synthetic_frame() -> Frame:
    """A near blue block at 0.8 m and a far red block at 1.5 m."""
    image = np.zeros((80, 100, 3), dtype=np.uint8)
    image[10:40, 5:35] = (180, 40, 40)
    image[10:45, 60:95] = (40, 80, 220)
    depth = np.zeros((80, 100), dtype=np.uint16)
    depth[10:40, 5:35] = 1500
    depth[10:45, 60:95] = 800
    return Frame(rgb=image, depth=depth, depth_scale=0.001, camera="synthetic")


def run_bench(gallery: Optional[ObjectGallery] = None) -> dict[str, Any]:
    """Detect, enroll the nearest block, and ask the fixed question set."""
    gallery = gallery if gallery is not None else ObjectGallery()
    frame = synthetic_frame()
    seen = observe(frame, ObjectGallery(), detector="depth")
    if not seen:
        return {"ok": False, "checks": {"saw_objects": False}, "answers": [], "observations": []}
    nearest = seen[0]
    crop = crop_rgb(frame.rgb, nearest.bbox)
    train_samples_blocking(
        gallery,
        [TrainSample(
            label="blue block",
            image=crop,
            maker="Lab",
            year=2024,
            kind="thing",
            heat_c=22.0,
            smell="none",
            texture="smooth",
        )],
        workers=1,
    )
    found = observe(frame, gallery, detector="depth")
    distance = answer_about("how far is it?", found)
    animal = answer_about("is it an animal?", found)
    food = answer_about("is it food?", found)
    maker = answer_about("who made it?", found)
    year = answer_about("when was it built?", found)
    sign = answer_about("translate this sign", found, ocr_text="SALIDA", target_language="en")
    cold = answer_about("is it hot?", found)
    missing_touch = answer_about("what does it feel like?", [])
    hot_frame = synthetic_frame()
    hot_frame.sensors = SensorBundle(heat=HeatReading(62.0), smell=SmellReading("coffee"),
                                     touch=TouchReading("rough", force_n=1.1))
    hot_found = observe(hot_frame, gallery, detector="depth")
    hot = answer_about("is it hot?", hot_found)
    smell = answer_about("what does it smell like?", hot_found)
    checks = {
        "saw_two_objects": len(found) >= 2,
        "nearest_is_close": bool(found) and found[0].distance_m is not None and found[0].distance_m < 1.0,
        "identified_nearest": bool(found) and found[0].identified == "blue block",
        "distance_sentence": "meters" in distance.text or "centimeters" in distance.text,
        "not_an_animal": animal.text.startswith("No"),
        "not_food": food.text.startswith("No"),
        "maker_from_catalog": "Lab" in maker.text,
        "year_from_catalog": "2024" in year.text,
        "sign_exit": "exit" in sign.text.casefold(),
        "catalog_temperature_not_hot": cold.text.startswith("From training, No"),
        "live_probe_is_hot": hot.text.startswith("Yes"),
        "live_smell": "coffee" in smell.text,
        "touch_absent_without_sensor": "touch sensor" in missing_touch.text,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "answers": {
            "distance": distance.text,
            "animal": animal.text,
            "food": food.text,
            "maker": maker.text,
            "year": year.text,
            "sign": sign.text,
            "catalog_heat": cold.text,
            "live_heat": hot.text,
            "live_smell": smell.text,
        },
        "observations": [obs.to_dict() for obs in found],
    }
