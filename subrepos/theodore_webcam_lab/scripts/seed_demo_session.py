"""Seed the Theodore live monitor with realistic demo frames.

Posts webcam frames to /api/theodore/webcam/evaluate so the live monitor page has
something to chart. Two students are simulated:

  student-a  healthy learner. Its microphone samples drop out every 3rd frame so
             you can confirm missing samples render as an "n/a" gap instead of
             being silently dropped (which used to misalign the charts).
  student-b  distracted learner: eyes down, phone visible, typing audio. After the
             sustained-gaze window it trips the cheating signal and raises the
             group lesson alerts.

Usage (from the repo root, with the lab API already running on port 8015):

    python3 subrepos/theodore_webcam_lab/scripts/seed_demo_session.py
    python3 subrepos/theodore_webcam_lab/scripts/seed_demo_session.py --rolling

`--rolling` keeps posting one frame per second so the dashboard updates live;
stop it with Ctrl-C.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://127.0.0.1:8015"
DEFAULT_SESSION_ID = "demo-session"


def build_payload(*, session_id: str, step: int) -> dict:
    timestamp_ms = 10_000 + step * 1_000
    # Drop student-a's audio inputs entirely on every 3rd frame so the resulting
    # microphone-quality sample is genuinely absent rather than merely low.
    mic_present = step % 3 != 0
    return {
        "session_id": session_id,
        "mode": "group",
        "expected_participant_ids": ["student-a", "student-b"],
        "signals": [
            {
                "participant_id": "student-a",
                "timestamp_ms": timestamp_ms,
                "face_count": 1,
                "liveness_state": "live",
                "foreground_ratio": 0.42,
                "motion_score": 0.2,
                "face_size_ratio": 0.19,
                "light_quality_score": round(0.72 + ((step % 6) - 2) * 0.02, 3),
                "image_detection_confidence": 0.91,
                "expression_label": "happy" if step % 2 == 0 else "neutral",
                "gaze_frontal": 0.82,
                "gaze_down_score": 0.10,
                "microphone_input_level_score": 0.84 if mic_present else None,
                "noise_filter_effectiveness_score": 0.80 if mic_present else None,
                "audio_noise_level_db": 35.0 if mic_present else None,
                "audio_snr_db": 24.0 if mic_present else None,
            },
            {
                "participant_id": "student-b",
                "timestamp_ms": timestamp_ms,
                "face_count": 1,
                "liveness_state": "live",
                "foreground_ratio": 0.35,
                "motion_score": 0.28,
                "face_size_ratio": 0.12,
                "light_quality_score": 0.58,
                "image_detection_confidence": 0.74,
                "expression_label": "neutral",
                "gaze_frontal": 0.22,
                "gaze_down_score": 0.86,
                "phone_visible": True,
                "typing_activity_score": 0.78,
                "keyboard_typing_audio_score": 0.80,
                "microphone_input_level_score": 0.62,
                "noise_filter_effectiveness_score": 0.58,
                "audio_noise_level_db": 49.0,
                "audio_snr_db": 12.0,
            },
        ],
    }


def post_frame(*, base_url: str, session_id: str, step: int) -> None:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/theodore/webcam/evaluate",
        data=json.dumps(build_payload(session_id=session_id, step=step)).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        response.read()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--session-id", default=DEFAULT_SESSION_ID)
    parser.add_argument("--frames", type=int, default=60, help="Frames for a one-shot seed.")
    parser.add_argument(
        "--rolling",
        action="store_true",
        help="Keep posting one frame per second until interrupted.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        for step in range(args.frames):
            post_frame(base_url=args.base_url, session_id=args.session_id, step=step)
    except urllib.error.URLError as exc:
        print(f"Could not reach {args.base_url}: {exc.reason}")
        print("Start the lab API first (see subrepos/theodore_webcam_lab/README.txt).")
        return 1

    print(f"Seeded '{args.session_id}' with {args.frames} frames.")
    print(f"Open {args.base_url}/theodore/webcam/live-monitor/{args.session_id}")

    if not args.rolling:
        return 0

    print("Rolling feed started (Ctrl-C to stop).")
    step = args.frames
    try:
        while True:
            post_frame(base_url=args.base_url, session_id=args.session_id, step=step)
            step += 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nRolling feed stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
