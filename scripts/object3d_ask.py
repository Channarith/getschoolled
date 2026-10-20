#!/usr/bin/env python3
"""Ask the camera about an object.

Distance, animal, and food come from the depth camera and the detector.
Who made it and when it was built come from the training catalog.
Signs are translated from the travel lexicon, or from text you pass in.

Examples:
  python3 scripts/object3d_ask.py --camera realsense "how far is it?"
  python3 scripts/object3d_ask.py --camera realsense "is it an animal?"
  python3 scripts/object3d_ask.py --camera realsense "who made it?"
  python3 scripts/object3d_ask.py --sign SALIDA --target en "translate this sign"
  python3 scripts/object3d_ask.py --sign "no entry" --target ja --no-camera
"""

from __future__ import annotations

import argparse
import sys

from aoep_shared.object3d.ask import answer_about
from aoep_shared.object3d.capture import capture
from aoep_shared.object3d.cli import (
    add_camera_arg,
    add_detector_arg,
    add_gallery_arg,
    add_sensor_args,
    bundle_from_args,
    llm_from_env,
    load_gallery,
    speak,
)
from aoep_shared.object3d.ocr import read_sign_text
from aoep_shared.object3d.pipeline import observe
from aoep_shared.object3d.sensors import apply_sensors
from aoep_shared.object3d.types import Observation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_camera_arg(parser)
    add_detector_arg(parser)
    add_gallery_arg(parser)
    add_sensor_args(parser)
    parser.add_argument("question", nargs="?", default="", help="what to ask about the view")
    parser.add_argument("--sign", default="", help="sign text, if you already know what it says")
    parser.add_argument("--target", default="en", help="language to translate a sign into")
    parser.add_argument("--source", default="auto", help="language the sign is written in")
    parser.add_argument("--speak", action="store_true", help="speak the answer if a local voice exists")
    parser.add_argument("--no-camera", action="store_true", help="answer from --sign only")
    args = parser.parse_args(argv)
    question = args.question.strip() or ("translate this sign" if args.sign else "what is this?")
    observations = []
    ocr_text = args.sign.strip()
    bundle = bundle_from_args(args)
    if not args.no_camera and not args.sign:
        try:
            cameras = ["realsense", "oak"] if args.camera == "both" else [args.camera]
            gallery = load_gallery(args.gallery)
            for camera in cameras:
                frame = capture(camera)
                frame.sensors = bundle
                observations.extend(observe(frame, gallery, detector=args.detector))
                if "translat" in question.casefold() or "sign" in question.casefold():
                    ocr_text = ocr_text or read_sign_text(frame.rgb)
        except Exception as exc:
            print(f"camera error: {exc}", file=sys.stderr)
            return 1
    if not observations and any((bundle.touch, bundle.smell, bundle.heat, bundle.thermal is not None)):
        if bundle.thermal is not None:
            height, width = bundle.thermal.shape[:2]
            bbox = (0, 0, int(width), int(height))
            shape = bundle.thermal.shape
        else:
            bbox = (0, 0, 1, 1)
            shape = (1, 1)
        probe = Observation(label="object", score=1.0, bbox=bbox, distance_m=None, kind="thing")
        apply_sensors([probe], bundle, shape)
        observations = [probe]
    if observations:
        nearest = observations[0]
        distance = "no depth" if nearest.distance_m is None else f"{nearest.distance_m:.2f} m"
        prefix = f"[{nearest.camera}] " if nearest.camera else ""
        print(f"{prefix}{nearest.name} {distance} ({nearest.kind})")
    answer = answer_about(
        question,
        observations,
        ocr_text=ocr_text,
        target_language=args.target,
        source_language=args.source,
        llm=llm_from_env(),
    )
    print(answer.text)
    if args.speak:
        speak(answer.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
