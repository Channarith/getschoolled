"""CLI entry: python3 -m webcam_lab"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="webcam-lab",
        description="Private webcam recognition lab for Theodore solo/group classes",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser("demo", help="Run an offline solo/group presence + voice demo")
    demo.add_argument("--class-mode", choices=("solo", "group"), default="solo")
    demo.add_argument(
        "--teaching-mode",
        choices=("theodore", "self_teach"),
        default="theodore",
    )
    demo.add_argument("--topic", default="photosynthesis")
    demo.add_argument("--use-xai", action="store_true", help="Use live xAI voice when keyed")

    sub.add_parser("server", help="Start the FastAPI lab server (:8093)")

    synth = sub.add_parser("synthetic", help="Silhouette/absence tick on a synthetic frame")
    synth.add_argument("--absent", type=int, default=0, help="Emit N empty frames (absence)")
    synth.add_argument("--body", action="store_true", default=True)
    synth.add_argument("--no-body", action="store_true")
    synth.add_argument("--face", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "server":
        from .server import main as server_main

        server_main()
        return 0

    if args.cmd == "demo":
        return asyncio.run(_run_demo(args))

    if args.cmd == "synthetic":
        return _run_synthetic(args)

    parser.error(f"unknown command {args.cmd}")
    return 2


async def _run_demo(args) -> int:
    from .teaching import TeachingSession

    session = TeachingSession.create(
        class_mode=args.class_mode,
        teaching_mode=args.teaching_mode,
        topic=args.topic,
        use_xai=args.use_xai,
    )
    session.add_participant("learner-1", "Ada")
    if args.class_mode == "group":
        session.add_participant("learner-2", "Bea", required=False)

    # Simulate: present -> silhouette -> absent hold -> return
    session.report_presence("learner-1", face_count=1)
    await session.handle_presence_voice("learner-1")
    session.report_presence("learner-1", face_count=0, silhouette_count=1)
    await session.handle_presence_voice("learner-1")
    for _ in range(3):
        session.report_presence("learner-1", face_count=0, silhouette_count=0)
    await session.handle_presence_voice("learner-1")
    await session.say(
        f"Welcome back. Today we will explore {args.topic}."
        if not session.should_pause_teaching()
        else "Pausing until you're back on camera."
    )
    session.report_presence("learner-1", face_count=1)
    await session.say(f"Great — let's continue with {args.topic}.")
    print(json.dumps(session.snapshot(), indent=2))
    return 0


def _run_synthetic(args) -> int:
    from .vision_session import VisionSession, synthetic_person_frame

    vision = VisionSession(participant_id="learner-1")
    with_body = not args.no_body
    if args.absent:
        reports = []
        for _ in range(args.absent):
            frame, _ = synthetic_person_frame(with_body=False, with_face_box=False)
            reports.append(vision.analyze_frame(frame).report.as_dict())
        print(json.dumps(reports, indent=2))
        return 0
    frame, faces = synthetic_person_frame(with_body=with_body, with_face_box=args.face)
    if args.face:
        analysis = vision.analyze_detections(
            faces=faces,
            silhouettes=vision.silhouette.detect(frame),
        )
    else:
        analysis = vision.analyze_frame(frame)
    print(
        json.dumps(
            {
                "faces": len(analysis.faces),
                "silhouettes": [s.__dict__ for s in analysis.silhouettes],
                "report": analysis.report.as_dict(),
                "live_room_payload": analysis.report.to_live_room_payload(),
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
