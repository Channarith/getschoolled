"""Depth, gallery, questions, and the async training queue."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import numpy as np

from aoep_shared.object3d.ask import answer_about, intent_of
from aoep_shared.object3d.depth import depth_detections, distance_m
from aoep_shared.object3d.embed import EMBED_DIM, embed_rgb
from aoep_shared.object3d.gallery import ObjectGallery
from aoep_shared.object3d.pipeline import observe
from aoep_shared.object3d.sensors import (
    HeatReading,
    SensorBundle,
    SmellReading,
    TouchReading,
    region_celsius,
)
from aoep_shared.object3d.signs import translate_sign
from aoep_shared.object3d.taxonomy import kind_for
from aoep_shared.object3d.train import train_samples, train_samples_blocking
from aoep_shared.object3d.types import Frame, Observation, TrainSample


def _pattern(index: int) -> np.ndarray:
    rng = np.random.default_rng(index + 7)
    image = np.zeros((48, 48, 3), dtype=np.uint8)
    color = rng.integers(0, 255, size=3, dtype=np.uint8)
    image[:] = color
    image[index % 40: index % 40 + 6, :] = 255 - color
    image[:, (index * 3) % 40] = (index * 17) % 255
    return image


def test_distance_is_median_meters():
    depth = np.zeros((20, 20), dtype=np.uint16)
    depth[2:10, 2:10] = 1500
    depth[2, 2] = 9000
    assert abs(distance_m(depth, (2, 2, 8, 8), 0.001) - 1.5) < 1e-6


def test_depth_blobs_split_two_distances():
    depth = np.zeros((80, 100), dtype=np.uint16)
    depth[10:40, 5:35] = 1500
    depth[10:45, 60:95] = 800
    found = depth_detections(depth, 0.001, min_cells=10, max_side=100)
    assert len(found) == 2
    distances = sorted(distance_m(depth, det.bbox, 0.001) for det in found)
    assert abs(distances[0] - 0.8) < 0.05
    assert abs(distances[1] - 1.5) < 0.05


def test_kinds():
    assert kind_for("dog") == "animal"
    assert kind_for("pizza") == "food"
    assert kind_for("stop sign") == "sign"
    assert kind_for("person") == "person"
    assert kind_for("laptop") == "thing"


def test_embedding_is_stable_and_normalized():
    image = _pattern(1)
    first = embed_rgb(image)
    second = embed_rgb(image)
    assert first.shape == (EMBED_DIM,)
    assert abs(float(np.linalg.norm(first)) - 1) < 1e-5
    assert np.allclose(first, second)


def test_gallery_matches_enrolled_object_and_remembers_facts(tmp_path: Path):
    gallery = ObjectGallery()
    lamp = _pattern(3)
    mug = _pattern(9)
    gallery.enroll("desk lamp", embed_rgb(lamp), maker="Philips", year=2019, kind="thing")
    gallery.enroll("mug", embed_rgb(mug), maker="IKEA", year=2021, kind="thing")
    hit = gallery.match(embed_rgb(lamp))
    assert hit is not None
    assert hit.label == "desk lamp"
    assert hit.maker == "Philips"
    assert hit.year == 2019
    path = gallery.save(tmp_path / "gallery.json")
    loaded = ObjectGallery(path)
    again = loaded.match(embed_rgb(mug))
    assert again is not None
    assert again.label == "mug"
    assert again.maker == "IKEA"


def test_async_training_scales_across_objects():
    samples = []
    images = {}
    for index in range(24):
        image = _pattern(index)
        images[f"obj-{index}"] = image
        samples.append(TrainSample(
            label=f"obj-{index}",
            image=image,
            maker="Workshop",
            year=2000 + index,
            kind="thing",
        ))
        noisy = image.copy()
        noisy[0, 0] = (int(noisy[0, 0, 0]) + 3) % 255
        samples.append(TrainSample(label=f"obj-{index}", image=noisy, maker="Workshop"))
    gallery = ObjectGallery()
    report = train_samples_blocking(gallery, samples, workers=8)
    assert report.views == 48
    assert report.objects == 24
    hit = gallery.match(embed_rgb(images["obj-11"]))
    assert hit is not None
    assert hit.label == "obj-11"
    assert hit.maker == "Workshop"
    assert hit.year == 2011
    assert hit.views == 2


def test_observe_names_a_trained_object_and_measures_it():
    image = np.zeros((60, 80, 3), dtype=np.uint8)
    image[10:40, 10:40] = (20, 180, 40)
    depth = np.zeros((60, 80), dtype=np.uint16)
    depth[10:40, 10:40] = 1250
    gallery = ObjectGallery()
    gallery.enroll(
        "plant", embed_rgb(image[10:40, 10:40]), maker="Local", year=2020, kind="thing",
    )
    frame = Frame(rgb=image, depth=depth, depth_scale=0.001, camera="realsense")
    found = observe(frame, gallery, detector="depth")
    assert found
    named = next(obs for obs in found if obs.identified == "plant")
    assert named.maker == "Local"
    assert named.year == 2020
    assert abs(named.distance_m - 1.25) < 0.05


def test_questions_use_camera_facts_and_sign_lexicon():
    dog = Observation(
        label="dog", score=0.9, bbox=(0, 0, 10, 10), distance_m=2.4,
        kind="animal", camera="realsense",
    )
    lamp = Observation(
        label="object", score=1, bbox=(0, 0, 10, 10), distance_m=0.8,
        kind="thing", identified="desk lamp", maker="Philips", year=2019,
    )
    banana = Observation(
        label="banana", score=0.8, bbox=(0, 0, 10, 10), distance_m=0.4, kind="food",
    )
    assert intent_of("how far is it from me?") == "distance"
    assert "2.4 meters" in answer_about("how far is it?", [dog]).text
    assert answer_about("is it an animal?", [dog]).text.startswith("Yes")
    assert answer_about("is it an animal?", [lamp]).text.startswith("No")
    assert answer_about("is it food?", [banana]).text.startswith("Yes")
    assert answer_about("is it food?", [lamp]).text.startswith("No")
    assert "Philips" in answer_about("who made it?", [lamp]).text
    assert "2019" in answer_about("when was it built?", [lamp]).text
    assert "don't know who made" in answer_about("who made it?", [dog]).text
    called = {"n": 0}

    def llm(_prompt: str) -> str:
        called["n"] += 1
        return "Invented brand."

    kept = answer_about("who made it?", [lamp], llm=llm)
    assert called["n"] == 0
    assert "Philips" in kept.text
    sign = answer_about("translate this sign", [], ocr_text="SALIDA", target_language="en")
    assert "exit" in sign.text
    assert translate_sign("no entry", "ja") == "進入禁止"


def test_thermal_is_per_object_and_a_probe_wins_on_the_nearest():
    image = np.zeros((80, 100, 3), dtype=np.uint8)
    image[10:40, 5:35] = (255, 0, 0)
    image[10:45, 60:95] = (0, 0, 255)
    depth = np.zeros((80, 100), dtype=np.uint16)
    depth[10:40, 5:35] = 1500
    depth[10:45, 60:95] = 800
    thermal = np.full((80, 100), 20, dtype=np.float32)
    thermal[10:40, 5:35] = 80
    thermal[10:45, 60:95] = 15
    frame = Frame(rgb=image, depth=depth, depth_scale=0.001, camera="realsense")
    frame.sensors = SensorBundle(
        thermal=thermal,
        heat=HeatReading(55.0),
        smell=SmellReading("coffee"),
        touch=TouchReading("rough", force_n=1.4),
    )
    found = observe(frame, ObjectGallery(), detector="depth")
    assert len(found) >= 2
    nearest, farther = found[0], found[1]
    assert nearest.distance_m < farther.distance_m
    assert nearest.heat_c == 55.0
    assert nearest.heat_source == "heat"
    assert nearest.smell == "coffee"
    assert nearest.texture == "rough"
    assert abs(farther.heat_c - 80) < 1
    assert farther.heat_source == "thermal"
    assert farther.smell == ""
    assert region_celsius(thermal, (5, 10, 30, 30)) == 80


def test_training_remembers_heat_smell_and_touch(tmp_path: Path):
    image = _pattern(4)
    gallery = ObjectGallery()
    report = train_samples_blocking(gallery, [
        TrainSample(label="kettle", image=image, heat_c=40, smell="steam", texture="smooth", force_n=0.5),
        TrainSample(label="kettle", image=image, heat_c=60, smell="steam", texture="smooth", force_n=1.5),
    ], workers=2)
    assert report.views == 2
    hit = gallery.match(embed_rgb(image))
    assert hit is not None
    assert abs(hit.heat_c - 50) < 1e-6
    assert hit.smell == "steam"
    assert hit.texture == "smooth"
    assert abs(hit.force_n - 1.0) < 1e-6
    gallery.save(tmp_path / "gallery.json")
    loaded = ObjectGallery(tmp_path / "gallery.json")
    again = loaded.match(embed_rgb(image))
    assert again is not None and again.heat_c == hit.heat_c
    hot = Observation(
        label="kettle", score=1, bbox=(0, 0, 8, 8), distance_m=0.4, kind="thing",
        heat_c=62, heat_source="heat", smell="coffee", smell_source="sensor",
        texture="rough", touch_source="sensor", force_n=0.2,
    )
    assert answer_about("is it hot?", [hot]).text.startswith("Yes")
    assert "62" in answer_about("how hot is it?", [hot]).text
    cold = Observation(
        label="kettle", score=1, bbox=(0, 0, 8, 8), distance_m=0.4, kind="thing",
        heat_c=22, heat_source="trained", smell="steam", smell_source="trained",
        texture="smooth", touch_source="trained",
    )
    assert answer_about("is it hot?", [cold]).text.startswith("From training, No")
    assert "steam" in answer_about("what does it smell like?", [cold]).text
    assert "smooth" in answer_about("what does it feel like?", [cold]).text
    bare = Observation(label="cup", score=1, bbox=(0, 0, 4, 4), distance_m=1, kind="thing")
    assert "isn't connected" in answer_about("is it hot?", [bare]).text
    assert "heat sensor" in answer_about("is it hot?", []).text
    assert "touch sensor" in answer_about("what does it feel like?", []).text
    assert "smell sensor" in answer_about("what does it smell like?", [bare]).text
    assert "touch sensor" in answer_about("how does it feel?", [bare]).text
    called = {"n": 0}

    def llm(_prompt: str) -> str:
        called["n"] += 1
        return "It is freezing."

    kept = answer_about("how hot is it?", [hot], llm=llm)
    assert called["n"] == 0
    assert "62" in kept.text


def test_old_gallery_without_sensor_fields_still_loads(tmp_path: Path):
    image = _pattern(2)
    gallery = ObjectGallery()
    gallery.enroll("mug", embed_rgb(image), maker="IKEA", year=2020)
    path = gallery.save(tmp_path / "old.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    for rec in raw["objects"].values():
        for key in ("heat_c", "heat_n", "smell", "texture", "force_n"):
            rec.pop(key, None)
    path.write_text(json.dumps(raw), encoding="utf-8")
    loaded = ObjectGallery(path)
    hit = loaded.match(embed_rgb(image))
    assert hit is not None
    assert hit.label == "mug"
    assert hit.heat_c is None
    assert hit.smell == ""


def test_empty_training_queue_is_a_noop():
    gallery = ObjectGallery()
    report = asyncio.run(train_samples(gallery, []))
    assert report.views == 0
    assert report.objects == 0
