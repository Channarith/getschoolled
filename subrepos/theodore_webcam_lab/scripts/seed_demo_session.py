"""Seed the Theodore live monitor with realistic demo frames.

By default this seeds the **group** scenario (3 simulated students) so cheating /
silhouette windows appear. Pass ``--scenario solo`` for one learner (matches a
single physical webcam).

  group (default):
    student-a  healthy learner
    student-b  distracted / cheating signals
    student-c  silhouette-only

  solo:
    learner    one healthy (or degraded) student

Usage (from the repo root, with the lab API already running):

    python3 subrepos/theodore_webcam_lab/scripts/seed_demo_session.py
    python3 subrepos/theodore_webcam_lab/scripts/seed_demo_session.py --scenario solo
    python3 subrepos/theodore_webcam_lab/scripts/seed_demo_session.py --port 8028

Prefer the in-page buttons: "Load solo demo (1 student)" / "Load group demo (3 students)".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Allow running as a script without installing the package.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from theodore_webcam_lab.demo_seed import (  # noqa: E402
    DEFAULT_SESSION_ID,
    build_demo_payload,
)

_DEFAULT_PORT = 8015
_DISCOVER_PORTS = tuple(range(8015, 8036))


def _env_base_url() -> str | None:
    for key in ("THEODORE_WEBCAM_LAB_URL", "THEODORE_LAB_BASE_URL"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            return raw.rstrip("/")
    port_raw = (os.environ.get("THEODORE_WEBCAM_LAB_PORT") or "").strip()
    if port_raw.isdigit():
        return f"http://127.0.0.1:{int(port_raw)}"
    return None


def health_ok(base_url: str, *, timeout: float = 0.6) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=timeout) as resp:
            if resp.status != 200:
                return False
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("service") == "theodore-webcam-lab" and body.get("status") == "ok"
    except Exception:
        # Connection refused/reset, timeouts, bad JSON, half-dead listeners, …
        return False


def discover_lab_base_url(
    *,
    preferred: str | None = None,
    ports: tuple[int, ...] = _DISCOVER_PORTS,
) -> str | None:
    """Return a reachable Theodore lab URL.

    Prefers ``preferred`` when healthy; otherwise the highest listening port in
    range (usually the most recently started local lab).
    """
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred.rstrip("/"))
    env_url = _env_base_url()
    if env_url and env_url not in candidates:
        candidates.append(env_url)
    for port in ports:
        url = f"http://127.0.0.1:{port}"
        if url not in candidates:
            candidates.append(url)

    healthy: list[str] = []
    for url in candidates:
        if health_ok(url):
            healthy.append(url)
    if not healthy:
        return None
    if preferred and preferred.rstrip("/") in healthy:
        return preferred.rstrip("/")
    def _port_key(url: str) -> int:
        try:
            return int(url.rsplit(":", 1)[-1])
        except ValueError:
            return -1

    return sorted(healthy, key=_port_key, reverse=True)[0]


def resolve_base_url(*, base_url: str | None, port: int | None, discover: bool) -> str:
    if base_url:
        return base_url.rstrip("/")
    if port is not None:
        return f"http://127.0.0.1:{int(port)}"
    preferred = _env_base_url() or f"http://127.0.0.1:{_DEFAULT_PORT}"
    if discover:
        found = discover_lab_base_url(preferred=preferred)
        if found:
            return found
    return preferred


def post_frame(
    *,
    base_url: str,
    session_id: str,
    step: int,
    degraded: bool = False,
    scenario: str = "group",
) -> None:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/theodore/webcam/evaluate",
        data=json.dumps(
            build_demo_payload(
                session_id=session_id, step=step, degraded=degraded, scenario=scenario
            )
        ).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        response.read()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 subrepos/theodore_webcam_lab/scripts/seed_demo_session.py\n"
            "  python3 subrepos/theodore_webcam_lab/scripts/seed_demo_session.py --port 8028\n"
            "  THEODORE_WEBCAM_LAB_PORT=8028 python3 "
            "subrepos/theodore_webcam_lab/scripts/seed_demo_session.py\n"
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Lab origin (overrides --port / env). Example: http://127.0.0.1:8028",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Lab port on 127.0.0.1 (overrides default 8015 / env).",
    )
    parser.add_argument(
        "--no-discover",
        action="store_true",
        help="Do not scan ports 8015–8035 when the preferred URL is down.",
    )
    parser.add_argument("--session-id", default=DEFAULT_SESSION_ID)
    parser.add_argument("--frames", type=int, default=12, help="Frames for a one-shot seed.")
    parser.add_argument(
        "--degraded",
        action="store_true",
        help="Send dim/soft-focus/noisy frames so recognition quality gates fire.",
    )
    parser.add_argument(
        "--scenario",
        choices=("solo", "group"),
        default="group",
        help="solo = 1 learner; group = 3 simulated students (default).",
    )
    parser.add_argument(
        "--rolling",
        action="store_true",
        help="Keep posting one frame per second until interrupted.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    discover = not args.no_discover and args.base_url is None
    base_url = resolve_base_url(
        base_url=args.base_url, port=args.port, discover=discover
    )

    if not health_ok(base_url):
        if discover:
            found = discover_lab_base_url(preferred=base_url)
            if found:
                print(f"Preferred URL unreachable; using discovered lab at {found}")
                base_url = found
        if not health_ok(base_url):
            print(f"Could not reach {base_url}")
            print("Start the lab API first, then re-run with the matching port, e.g.:")
            print(
                "  python3 -m uvicorn theodore_webcam_lab.main:app "
                "--app-dir subrepos/theodore_webcam_lab/src --host 127.0.0.1 --port 8028"
            )
            print(
                "  python3 subrepos/theodore_webcam_lab/scripts/seed_demo_session.py "
                "--port 8028"
            )
            print("Find a listening lab with: lsof -nP -iTCP:8015-8035 -sTCP:LISTEN")
            return 1

    print(f"Seeding against {base_url} (scenario={args.scenario})")
    try:
        for step in range(args.frames):
            post_frame(
                base_url=base_url,
                session_id=args.session_id,
                step=step,
                degraded=args.degraded,
                scenario=args.scenario,
            )
    except urllib.error.URLError as exc:
        print(f"Could not reach {base_url}: {exc.reason}")
        print("Pass --port / --base-url for the port your lab is actually using.")
        return 1

    print(f"Seeded '{args.session_id}' with {args.frames} frames ({args.scenario}).")
    print(f"Open {base_url}/theodore/webcam/live-monitor/{args.session_id}")

    if not args.rolling:
        return 0

    print("Rolling feed started (Ctrl-C to stop).")
    step = args.frames
    try:
        while True:
            post_frame(
                base_url=base_url,
                session_id=args.session_id,
                step=step,
                degraded=args.degraded,
                scenario=args.scenario,
            )
            step += 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nRolling feed stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
