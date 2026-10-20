#!/usr/bin/env python3
"""Train object identification on as many labeled views as you have.

Workers embed views at the same time and fold them into one gallery.
Drop images in output/object3d/samples/<label>/*.jpg and run this, or enroll
a live camera view under a name you choose.

Examples:
  python3 scripts/object3d_train.py --data output/object3d/samples --workers 8
  python3 scripts/object3d_train.py --camera realsense --label "desk lamp" \\
      --maker Philips --year 2019 --views 8
  python3 scripts/object3d_train.py --camera realsense --bootstrap --views 4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from aoep_shared.object3d.capture import capture
from aoep_shared.object3d.cli import (
    DEFAULT_SAMPLES,
    add_camera_arg,
    add_detector_arg,
    add_gallery_arg,
    add_sensor_args,
    bundle_from_args,
    load_gallery,
)
from aoep_shared.object3d.pipeline import crop_rgb, observe
from aoep_shared.object3d.sensors import live_senses
from aoep_shared.object3d.taxonomy import kind_for
from aoep_shared.object3d.train import train_samples_blocking
from aoep_shared.object3d.types import TrainSample


def _load_rgb(path: Path) -> np.ndarray:
    from PIL import Image

    return np.asarray(Image.open(path).convert("RGB"))


def samples_from_dir(root: Path) -> list[TrainSample]:
    samples: list[TrainSample] = []
    if not root.is_dir():
        raise SystemExit(f"no sample folder at {root}")
    for label_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        meta: dict = {
            "maker": "", "year": None, "kind": "",
            "heat_c": None, "smell": "", "texture": "", "force_n": None,
        }
        sidecar = label_dir / "meta.json"
        if sidecar.is_file():
            raw = json.loads(sidecar.read_text(encoding="utf-8"))
            meta["maker"] = str(raw.get("maker") or "")
            meta["year"] = int(raw["year"]) if raw.get("year") else None
            meta["kind"] = str(raw.get("kind") or "")
            if raw.get("celsius") is not None:
                meta["heat_c"] = float(raw["celsius"])
            meta["smell"] = str(raw.get("smell") or "")
            meta["texture"] = str(raw.get("texture") or "")
            if raw.get("force_n") is not None:
                meta["force_n"] = float(raw["force_n"])
        for image_path in sorted(label_dir.iterdir()):
            if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            samples.append(TrainSample(
                label=label_dir.name,
                image=_load_rgb(image_path),
                maker=meta["maker"],
                year=meta["year"],
                kind=meta["kind"] or kind_for(label_dir.name),
                heat_c=meta["heat_c"],
                smell=meta["smell"],
                texture=meta["texture"],
                force_n=meta["force_n"],
            ))
    return samples


def _save_crop(root: Path, label: str, image: np.ndarray, index: int) -> None:
    from PIL import Image

    folder = root / label
    folder.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(image)).save(folder / f"{index:04d}.png")


def samples_from_camera(args: argparse.Namespace) -> list[TrainSample]:
    samples: list[TrainSample] = []
    cameras = ["realsense", "oak"] if args.camera == "both" else [args.camera]
    for view in range(args.views):
        for camera in cameras:
            frame = capture(camera)
            frame.sensors = args.bundle
            gallery = load_gallery(args.gallery)
            found = observe(frame, gallery, detector=args.detector)
            if args.label:
                crop = crop_rgb(frame.rgb, found[0].bbox) if found else frame.rgb
                senses = live_senses(found[0]) if found else {
                    "heat_c": args.bundle.heat.celsius if args.bundle.heat else None,
                    "smell": args.bundle.smell.label if args.bundle.smell else "",
                    "smell_intensity": args.bundle.smell.intensity if args.bundle.smell else None,
                    "texture": args.bundle.touch.texture if args.bundle.touch else "",
                    "force_n": args.bundle.touch.force_n if args.bundle.touch else None,
                }
                samples.append(TrainSample(
                    label=args.label,
                    image=crop,
                    maker=args.maker,
                    year=args.year or None,
                    kind=args.kind or kind_for(args.label),
                    **senses,
                ))
                if args.keep:
                    _save_crop(args.samples, args.label, crop, view)
                continue
            if not args.bootstrap:
                raise SystemExit("pass --label or --bootstrap or --data")
            for obs in found:
                if obs.label == "object" and not obs.identified:
                    continue
                label = obs.identified or obs.label
                crop = crop_rgb(frame.rgb, obs.bbox)
                samples.append(TrainSample(
                    label=label,
                    image=crop,
                    maker=args.maker,
                    year=args.year or None,
                    kind=obs.kind,
                    **live_senses(obs),
                ))
                if args.keep:
                    _save_crop(args.samples, label, crop, len(samples))
    return samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_gallery_arg(parser)
    add_camera_arg(parser)
    add_detector_arg(parser)
    add_sensor_args(parser)
    parser.add_argument("--data", type=Path, help="folder of <label>/*.jpg crops")
    parser.add_argument("--label", default="", help="name to enroll from the camera")
    parser.add_argument("--maker", default="", help="who made it")
    parser.add_argument("--year", type=int, default=0, help="year it was built")
    parser.add_argument("--kind", default="", help="animal, food, sign, person, or thing")
    parser.add_argument("--views", type=int, default=4, help="camera frames to enroll")
    parser.add_argument(
        "--bootstrap", action="store_true",
        help="enroll every detected COCO object under its own name",
    )
    parser.add_argument("--workers", type=int, default=8, help="parallel embedding workers")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES)
    parser.add_argument("--keep", action="store_true", help="save camera crops into --samples")
    args = parser.parse_args(argv)
    args.bundle = bundle_from_args(args)
    if args.data:
        samples = samples_from_dir(args.data)
    elif args.label or args.bootstrap:
        try:
            samples = samples_from_camera(args)
        except Exception as exc:
            print(f"camera error: {exc}", file=sys.stderr)
            return 1
    else:
        parser.error("pass --data, --label, or --bootstrap")
        return 2
    if not samples:
        print("no views to train")
        return 1
    for sample in samples:
        if args.bundle.heat is not None and sample.heat_c is None:
            sample.heat_c = args.bundle.heat.celsius
        if args.bundle.smell and args.bundle.smell.label and not sample.smell:
            sample.smell = args.bundle.smell.label
            sample.smell_intensity = args.bundle.smell.intensity
        if args.bundle.touch and args.bundle.touch.texture and not sample.texture:
            sample.texture = args.bundle.touch.texture
        if args.bundle.touch and args.bundle.touch.force_n is not None and sample.force_n is None:
            sample.force_n = args.bundle.touch.force_n
    gallery = load_gallery(args.gallery)
    report = train_samples_blocking(gallery, samples, workers=max(1, args.workers))
    gallery.save(args.gallery)
    print(
        f"trained {report.views} views across {report.objects} objects "
        f"with {args.workers} workers"
    )
    print("labels: " + ", ".join(report.labels))
    print(f"gallery={args.gallery}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
