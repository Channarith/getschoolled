"""Step-by-step health check for the Theodore webcam lab.

Run this when something does not work. It walks the same path the product takes
— imports, analysis, imaging, tuning, then every HTTP endpoint — and prints one
PASS/FAIL line per step with a specific fix for whatever failed, so you can see
exactly how far the system gets instead of guessing.

    python3 subrepos/theodore_webcam_lab/scripts/selfcheck.py            # offline checks only
    python3 subrepos/theodore_webcam_lab/scripts/selfcheck.py --serve    # start the API itself
    python3 subrepos/theodore_webcam_lab/scripts/selfcheck.py --base-url http://127.0.0.1:8015

Exit code is 0 when every step passed, 1 otherwise, so CI can gate on it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
SRC = LAB_ROOT / "src"
DEFAULT_BASE_URL = "http://127.0.0.1:8015"

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _colour(text: str, code: str) -> str:
    return text if os.environ.get("NO_COLOR") else f"{code}{text}{RESET}"


@dataclass
class Step:
    name: str
    ok: bool
    detail: str = ""
    fix: str = ""
    skipped: bool = False


@dataclass
class Report:
    steps: list[Step] = field(default_factory=list)

    def add(self, step: Step) -> Step:
        self.steps.append(step)
        mark = (
            _colour("SKIP", YELLOW)
            if step.skipped
            else _colour("PASS", GREEN)
            if step.ok
            else _colour("FAIL", RED)
        )
        print(f"  [{mark}] {step.name}")
        if step.detail:
            print(f"         {_colour(step.detail, DIM)}")
        if not step.ok and not step.skipped and step.fix:
            print(f"         {_colour('fix: ' + step.fix, YELLOW)}")
        return step

    @property
    def failed(self) -> list[Step]:
        return [s for s in self.steps if not s.ok and not s.skipped]

    @property
    def passed(self) -> list[Step]:
        return [s for s in self.steps if s.ok]


def _http(
    base_url: str, path: str, *, method: str = "GET", body: dict | None = None, timeout: float = 8.0
) -> tuple[int, object]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        method=method,
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        try:
            return response.status, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return response.status, raw


# --------------------------------------------------------------- offline steps
def check_python(report: Report) -> None:
    ok = sys.version_info >= (3, 11)
    report.add(
        Step(
            "Python 3.11+",
            ok,
            detail=f"running {sys.version.split()[0]}",
            fix="install Python 3.11 or newer (the repo targets 3.11/3.12)",
        )
    )


def check_dependencies(report: Report) -> None:
    missing = []
    for module in ("fastapi", "pydantic", "uvicorn"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    report.add(
        Step(
            "Python dependencies",
            not missing,
            detail="fastapi, pydantic, uvicorn present" if not missing else f"missing: {', '.join(missing)}",
            fix='python3 -m pip install "fastapi>=0.111,<0.116" "pydantic>=2.7,<3" "uvicorn[standard]>=0.30,<0.35"',
        )
    )


def check_imports(report: Report) -> bool:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    try:
        import theodore_webcam_lab  # noqa: F401

        report.add(Step("Lab package imports", True, detail=f"from {SRC}"))
        return True
    except ModuleNotFoundError as exc:
        # A missing third-party package is a different problem from the lab not
        # being importable, and needs a different fix.
        third_party = (exc.name or "") not in {"theodore_webcam_lab", ""}
        report.add(
            Step(
                "Lab package imports",
                False,
                detail=f"missing module: {exc.name}",
                fix=(
                    f'python3 -m pip install "{exc.name}"  (see Step 1 in README.md)'
                    if third_party
                    else f"run from the repo root, or add {SRC} to PYTHONPATH"
                ),
            )
        )
        return False
    except Exception as exc:  # noqa: BLE001 - report any import problem verbatim
        report.add(
            Step(
                "Lab package imports",
                False,
                detail=f"{type(exc).__name__}: {exc}",
                fix=f"run from the repo root, or add {SRC} to PYTHONPATH",
            )
        )
        return False


def check_analyzer(report: Report) -> None:
    from theodore_webcam_lab.analysis import WebcamSessionAnalyzer
    from theodore_webcam_lab.types import ClassMode, WebcamSignal

    try:
        result = WebcamSessionAnalyzer().evaluate(
            session_id="selfcheck",
            mode=ClassMode.SOLO,
            signals=[
                WebcamSignal(
                    participant_id="learner",
                    timestamp_ms=1_000,
                    face_count=1,
                    liveness_state="live",
                    face_size_ratio=0.2,
                    light_quality_score=0.8,
                )
            ],
        )
        participant = result.participants[0]
        ok = participant.distance_from_camera_m is not None
        report.add(
            Step(
                "Webcam analysis",
                ok,
                detail=(
                    f"distance={participant.distance_from_camera_m}m "
                    f"confidence={participant.recognition_confidence:.2f}"
                ),
                fix="analysis.py raised or returned no distance; run the pytest suite for detail",
            )
        )
    except Exception as exc:  # noqa: BLE001
        report.add(Step("Webcam analysis", False, detail=f"{type(exc).__name__}: {exc}",
                        fix="run: python3 -m pytest subrepos/theodore_webcam_lab/tests -q"))


def check_imaging(report: Report) -> None:
    from theodore_webcam_lab.imaging import analyze_luminance_grid

    try:
        sharp = analyze_luminance_grid([[0.3] * 8 + [0.7] * 8 for _ in range(16)])
        blurred = analyze_luminance_grid(
            [[0.35 + 0.3 * x / 15 for x in range(16)] for _ in range(16)]
        )
        ok = sharp.sharpness_score > blurred.sharpness_score
        report.add(
            Step(
                "Sobel imaging",
                ok,
                detail=(
                    f"backend={sharp.backend} sharp={sharp.sharpness_score:.2f} "
                    f"blurred={blurred.sharpness_score:.2f}"
                ),
                fix="sharpness no longer separates a sharp edge from a blur; check imaging.py",
            )
        )
    except Exception as exc:  # noqa: BLE001
        report.add(Step("Sobel imaging", False, detail=f"{type(exc).__name__}: {exc}",
                        fix="check imaging.py; numpy is optional, the pure-Python path should still work"))


def check_tuning(report: Report) -> None:
    from theodore_webcam_lab.vision_tuning import PRESETS, VisionTuning
    from theodore_webcam_lab.voice_tuning import VoiceTuning

    try:
        for name in PRESETS:
            VisionTuning.preset(name).validate()
        VoiceTuning().validate()
        report.add(
            Step(
                "Tuning knobs",
                True,
                detail=f"{len(VisionTuning().to_dict())} vision knobs, "
                       f"{len(VoiceTuning().to_dict())} voice knobs, presets: {', '.join(sorted(PRESETS))}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        report.add(Step("Tuning knobs", False, detail=f"{type(exc).__name__}: {exc}",
                        fix="a preset holds an out-of-range value; see vision_tuning.py validate()"))


# ------------------------------------------------------------------ API steps
def check_server(report: Report, base_url: str) -> bool:
    try:
        status, body = _http(base_url, "/health")
        ok = status == 200 and isinstance(body, dict) and body.get("status") == "ok"
        report.add(Step("API reachable", ok, detail=f"{base_url} -> {status}",
                        fix="start it, or pass --serve to have this script start it"))
        return ok
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        report.add(
            Step(
                "API reachable",
                False,
                detail=f"{base_url}: {getattr(exc, 'reason', exc)}",
                fix=(
                    "python3 -m uvicorn theodore_webcam_lab.main:app "
                    "--app-dir subrepos/theodore_webcam_lab/src --port 8015   (or re-run with --serve)"
                ),
            )
        )
        return False


def check_evaluate(report: Report, base_url: str) -> None:
    payload = {
        "session_id": "selfcheck",
        "mode": "solo",
        "signals": [
            {
                "participant_id": "learner",
                "timestamp_ms": 1_000,
                "face_count": 1,
                "liveness_state": "live",
                "foreground_ratio": 0.4,
                "motion_score": 0.2,
                "face_size_ratio": 0.19,
                "light_quality_score": 0.8,
                "image_detection_confidence": 0.9,
            }
        ],
    }
    try:
        status, body = _http(base_url, "/api/theodore/webcam/evaluate", method="POST", body=payload)
        ok = status == 200 and isinstance(body, dict) and bool(body.get("participants"))
        detail = ""
        if ok:
            p = body["participants"][0]  # type: ignore[index]
            detail = f"confidence={p['recognition_confidence']:.2f} gates={p['quality_flags'] or 'none'}"
        report.add(Step("Frame evaluation", ok, detail=detail,
                        fix="POST /api/theodore/webcam/evaluate failed; check the server log"))
    except Exception as exc:  # noqa: BLE001
        report.add(Step("Frame evaluation", False, detail=f"{type(exc).__name__}: {exc}",
                        fix="check the server log for a traceback"))


def check_live_metrics(report: Report, base_url: str) -> None:
    try:
        status, body = _http(base_url, "/api/theodore/webcam/live-metrics/selfcheck")
        aligned = False
        if status == 200 and isinstance(body, dict) and body.get("participants"):
            series = body["participants"][0]  # type: ignore[index]
            aligned = len(series["timestamps_ms"]) == len(series["light_quality_score"])
        report.add(Step("Live metrics", status == 200 and aligned,
                        detail="series aligned with timestamps" if aligned else f"status {status}",
                        fix="run the frame-evaluation step first; metrics only exist for a seeded session"))
    except Exception as exc:  # noqa: BLE001
        report.add(Step("Live metrics", False, detail=f"{type(exc).__name__}: {exc}"))


def check_monitor_page(report: Report, base_url: str) -> None:
    try:
        status, body = _http(base_url, "/theodore/webcam/live-monitor/selfcheck")
        html = body if isinstance(body, str) else ""
        ok = status == 200 and "Student Windows" in html and 'id="cam"' in html
        report.add(Step("Live monitor page", ok,
                        detail="camera panel and tuning sliders present" if ok else f"status {status}",
                        fix="the HTML did not render; check main.py live_monitor_page"))
    except Exception as exc:  # noqa: BLE001
        report.add(Step("Live monitor page", False, detail=f"{type(exc).__name__}: {exc}"))


def check_voice(report: Report, base_url: str) -> None:
    try:
        status, body = _http(
            base_url,
            "/api/theodore/voice/respond",
            method="POST",
            body={"class_mode": "solo", "learner_message": "hello", "session_id": "selfcheck"},
        )
        ok = status == 200 and isinstance(body, dict) and bool(body.get("message"))
        provider = body.get("provider") if isinstance(body, dict) else "?"
        note = " (set XAI_API_KEY for real xAI replies)" if provider == "local-fallback" else ""
        report.add(Step("Voice agent", ok, detail=f"provider={provider}{note}",
                        fix="POST /api/theodore/voice/respond failed; check the server log"))
    except Exception as exc:  # noqa: BLE001
        report.add(Step("Voice agent", False, detail=f"{type(exc).__name__}: {exc}"))


def check_tuning_api(report: Report, base_url: str) -> None:
    try:
        status, body = _http(base_url, "/api/theodore/vision/tuning")
        ok = status == 200 and isinstance(body, dict) and bool(body.get("knobs"))
        report.add(Step("Tuning API", ok,
                        detail=f"{len(body.get('knobs', {}))} knobs live" if ok else f"status {status}",
                        fix="GET /api/theodore/vision/tuning failed; check the server log"))
    except Exception as exc:  # noqa: BLE001
        report.add(Step("Tuning API", False, detail=f"{type(exc).__name__}: {exc}"))


def check_games(report: Report, base_url: str) -> None:
    try:
        status, body = _http(
            base_url,
            "/api/theodore/webcam/games/challenge",
            method="POST",
            body={
                "session_id": "selfcheck",
                "mode": "solo",
                "learning_prompt": "Explain inertia",
                "preferred_game_type": "focus_streak",
            },
        )
        ok = status == 200 and isinstance(body, dict) and bool(body.get("challenge_id"))
        report.add(Step("Webcam games", ok,
                        detail=f"challenge {body.get('challenge_id')}" if ok else f"status {status}",
                        fix="POST /api/theodore/webcam/games/challenge failed; check the server log"))
    except Exception as exc:  # noqa: BLE001
        report.add(Step("Webcam games", False, detail=f"{type(exc).__name__}: {exc}"))


# ----------------------------------------------------------------------- main
def start_server(port: int) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "theodore_webcam_lab.main:app",
            "--app-dir", str(SRC), "--host", "127.0.0.1", "--port", str(port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for(base_url: str, timeout_s: float = 25.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            _http(base_url, "/health", timeout=2.0)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.4)
    return False


def run(base_url: str, *, serve: bool, port: int) -> int:
    print()
    print("Theodore webcam lab — self check")
    print("=" * 60)

    report = Report()

    print("\nOffline (no server needed)")
    check_python(report)
    check_dependencies(report)
    imported = check_imports(report)
    if imported:
        check_analyzer(report)
        check_imaging(report)
        check_tuning(report)

    server: subprocess.Popen[bytes] | None = None
    if serve:
        print(f"\nStarting the API on port {port}…")
        server = start_server(port)
        base_url = f"http://127.0.0.1:{port}"
        if not wait_for(base_url):
            print(_colour("  the server did not come up in time", RED))

    try:
        print(f"\nAPI ({base_url})")
        if check_server(report, base_url):
            check_evaluate(report, base_url)
            check_live_metrics(report, base_url)
            check_monitor_page(report, base_url)
            check_tuning_api(report, base_url)
            check_voice(report, base_url)
            check_games(report, base_url)
        else:
            print(_colour("  skipping the API steps until the server is reachable", YELLOW))
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()

    print()
    print("=" * 60)
    failed = report.failed
    if failed:
        print(_colour(f"{len(failed)} step(s) failed:", RED))
        for step in failed:
            print(f"  - {step.name}: {step.detail}")
            if step.fix:
                print(f"      {_colour(step.fix, YELLOW)}")
        return 1
    print(_colour(f"All {len(report.passed)} checks passed.", GREEN))
    print(f"Open the monitor: {base_url}/theodore/webcam/live-monitor/demo-session")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--serve", action="store_true", help="Start the API for the duration of the check.")
    parser.add_argument("--port", type=int, default=8015)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args.base_url, serve=args.serve, port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
