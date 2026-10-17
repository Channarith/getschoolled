#!/usr/bin/env python3
"""Look through a 3D camera and list what it sees.

Examples:
  python3 scripts/object3d_pipeline.py --camera realsense
  python3 scripts/object3d_pipeline.py --camera oak --detector coco
  python3 scripts/object3d_pipeline.py --camera both --watch
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from aoep_shared.object3d.capture import capture
from aoep_shared.object3d.cli import (
    add_camera_arg,
    add_detector_arg,
    add_gallery_arg,
    add_sensor_args,
    bundle_from_args,
    load_gallery,
)
from aoep_shared.object3d.pipeline import observe
from aoep_shared.object3d.types import Frame


def _frames(camera: str) -> list[Frame]:
    if camera == "both":
        return [capture("realsense"), capture("oak")]
    return [capture(camera)]


def _print_frame(frame: Frame, gallery, detector: str) -> None:
    found = observe(frame, gallery, detector=detector)
    print(f"camera={frame.camera or 'image'} objects={len(found)}")
    if not found:
        print("  (nothing in range)")
        return
    for index, obs in enumerate(found, start=1):
        distance = "no-depth" if obs.distance_m is None else f"{obs.distance_m:.2f}m"
        extra = ""
        if obs.identified:
            extra = f" match={obs.identify_score:.2f}"
        if obs.maker:
            extra += f" maker={obs.maker}"
        if obs.year:
            extra += f" year={obs.year}"
        if obs.heat_c is not None:
            extra += f" {obs.heat_c:.0f}C"
        if obs.smell:
            extra += f" smell={obs.smell}"
        if obs.texture:
            extra += f" feel={obs.texture}"
        print(
            f"  {index}. {obs.name} kind={obs.kind} {distance} "
            f"score={obs.score:.2f} via={obs.source}{extra}"
        )
        print("    " + json.dumps(obs.to_dict(), ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_camera_arg(parser)
    add_detector_arg(parser)
    add_gallery_arg(parser)
    add_sensor_args(parser)
    parser.add_argument("--watch", action="store_true", help="keep scanning until Ctrl-C")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between scans")
    args = parser.parse_args(argv)
    gallery = load_gallery(args.gallery)
    bundle = bundle_from_args(args)
    print(f"gallery={args.gallery} objects={len(gallery)} detector={args.detector}")
    while True:
        try:
            frames = _frames(args.camera)
        except Exception as exc:
            print(f"camera error: {exc}", file=sys.stderr)
            return 1
        for frame in frames:
            frame.sensors = bundle
            _print_frame(frame, gallery, args.detector)
        if not args.watch:
            return 0
        time.sleep(max(0.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
