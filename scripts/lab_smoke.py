#!/usr/bin/env python3
"""Probe lab /health and /version. Read-only: GET only, no process control.

Default ports are the ones each lab's README tells you to pass to uvicorn.
Kal-el (or any other host) can shift them:

  python3 scripts/lab_smoke.py --host 10.0.0.8 --port-offset 10000
  make lab-smoke LAB_SMOKE_HOST=10.0.0.8 LAB_SMOKE_PORT_OFFSET=10000

--port-offset 10000 turns 8095 into 18095. Repeat --port name=N to pin one lab.
--allow-down exits 0 when a lab is not listening (GitHub runners). A lab that
answers with a different version than the repo VERSION file still fails.
Labs with no /version stay "up" unless --require-version is set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# name, default port or None, kind. Ports match the README start command.
# run_theodore_lab.sh uses a different map (8011-8019); pass --port to use it.
LABS: tuple[tuple[str, int | None, str], ...] = (
    ("speech", 8002, "http"),
    ("llm-lab", 8019, "http"),
    ("object3d", 8020, "http"),
    ("course-studio", 8040, "http"),
    ("rag-lab", 8095, "http"),
    ("cosyvoice", 9880, "http"),
    ("audio-translation", 8041, "http"),
    ("webcam", 8015, "http"),
    ("children", 8018, "http"),
    ("drive", 8096, "http"),
    ("homework", 8098, "http"),
    ("music", 8097, "http"),
    ("meeting-agents", None, "offline"),
)

# Why `make <lab>` does not leave an HTTP server running.
NOT_A_DAEMON = {
    "webcam": (
        "make webcam-lab runs two one-shot recognition modes "
        "(labs/webcam-recognition-suite/scripts/run_lab.py). "
        "The HTTP lab is a separate uvicorn on 8015 and is not part of make dev-all. "
        "It can run without a camera; the README seeds demo frames."
    ),
    "children": (
        "make children-lab runs scripts/selfcheck.py through TestClient. "
        "The HTTP lab is uvicorn theodore_children_webcam_lab.main:app on 8018. "
        "The camera stays in the browser; the server itself needs no camera."
    ),
    "drive": (
        "make drive-lab runs an 8-round in-process bakeoff and prints metrics. "
        "The HTTP lab is uvicorn theodore_drive_lab.main:app on 8096. "
        "The bakeoff uses fixture utterances, so no microphone is required."
    ),
    "homework": (
        "make homework-lab runs the in-process gold battery and prints a score. "
        "The HTTP lab is uvicorn theodore_homework_lab.main:app on 8098. "
        "homework-generate and homework-grade are separate CLIs, not this server."
    ),
    "music": (
        "make music-lab prints the catalog size. "
        "The HTTP player is uvicorn theodore_music_lab.main:app on 8097. "
        "A full language warmup is only the container entrypoint, not this command."
    ),
    "meeting-agents": (
        "make meeting-agents-lab runs scripts/meeting_agents_lab.py --all. "
        "That is an offline zoom/teams/meet simulation with no port, no /health, "
        "and no /version. It does not listen."
    ),
    "audio-translation": (
        "There is no Makefile target. Start it with uvicorn "
        "theodore_audio_translation_lab.main:app on 8041 "
        "(scripts/run_theodore_lab.sh audio_translation uses 8011 instead)."
    ),
}


def expected_version(root: Path = ROOT) -> str:
    return (root / "VERSION").read_text(encoding="utf-8").strip()


def effective_port(
    name: str,
    default: int | None,
    *,
    offset: int,
    overrides: dict[str, int],
) -> int | None:
    if name in overrides:
        return overrides[name]
    if default is None:
        return None
    return default + offset


def _get_json(url: str, timeout: float) -> tuple[int | None, dict | None, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(8192)
            status = int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code), None, ""
    except Exception as exc:  # noqa: BLE001 — down is a result, not a crash
        return None, None, type(exc).__name__
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return status, None, "not-json"
    if not isinstance(body, dict):
        return status, None, "not-object"
    return status, body, ""


def _version_of(payload: dict | None) -> str:
    if not payload:
        return ""
    return str(payload.get("version") or "").strip()


def probe_one(
    name: str,
    port: int | None,
    kind: str,
    *,
    host: str,
    expected: str,
    timeout: float,
) -> dict:
    row = {
        "name": name,
        "host": host,
        "port": port,
        "status": "down",
        "version": "",
        "expected": expected,
        "detail": "",
    }
    if kind == "offline" or port is None:
        row["status"] = "offline"
        row["detail"] = NOT_A_DAEMON.get(name, "no HTTP server")
        return row
    health_status, health, health_err = _get_json(
        f"http://{host}:{port}/health", timeout
    )
    if health_status is None or not (200 <= health_status < 300):
        row["status"] = "down"
        if health_status is None:
            row["detail"] = f"not listening ({health_err})" if health_err else "not listening"
        else:
            row["detail"] = f"health HTTP {health_status}"
        return row
    ver_status, ver_body, _ver_err = _get_json(
        f"http://{host}:{port}/version", timeout
    )
    found = ""
    if ver_status is not None and 200 <= ver_status < 300:
        found = _version_of(ver_body)
    if not found:
        found = _version_of(health)
    row["version"] = found
    if not found:
        row["status"] = "up"
        row["detail"] = "no /version"
        return row
    if found != expected:
        row["status"] = "mismatch"
        row["detail"] = f"{found} != {expected}"
        return row
    row["status"] = "up"
    row["detail"] = found
    return row


def probe_all(
    *,
    host: str,
    offset: int,
    overrides: dict[str, int],
    expected: str,
    timeout: float,
    labs: tuple[tuple[str, int | None, str], ...] = LABS,
) -> list[dict]:
    rows = []
    for name, default, kind in labs:
        port = effective_port(name, default, offset=offset, overrides=overrides)
        rows.append(
            probe_one(
                name, port, kind, host=host, expected=expected, timeout=timeout
            )
        )
    return rows


def exit_code(rows: list[dict], *, allow_down: bool, require_version: bool) -> int:
    if any(row["status"] == "mismatch" for row in rows):
        return 1
    if require_version and any(
        row["status"] == "up" and row["detail"] == "no /version" for row in rows
    ):
        return 1
    if not allow_down and any(row["status"] == "down" for row in rows):
        return 2
    return 0


def format_table(rows: list[dict]) -> str:
    lines = [f"{'lab':<18} {'port':>6}  {'status':<10} detail"]
    for row in rows:
        port = "-" if row["port"] is None else str(row["port"])
        lines.append(
            f"{row['name']:<18} {port:>6}  {row['status']:<10} {row['detail']}"
        )
    return "\n".join(lines) + "\n"


def _parse_ports(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in values:
        if "=" not in item:
            raise SystemExit(f"--port expects name=PORT, got {item!r}")
        name, raw = item.split("=", 1)
        out[name.strip()] = int(raw)
    extra = os.environ.get("LAB_SMOKE_PORTS", "")
    for item in extra.split(","):
        item = item.strip()
        if not item:
            continue
        name, raw = item.split("=", 1)
        out.setdefault(name.strip(), int(raw))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("LAB_SMOKE_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port-offset",
        type=int,
        default=int(os.environ.get("LAB_SMOKE_PORT_OFFSET", "0")),
        help="Added to each default port. 10000 maps 8xxx onto 18xxx.",
    )
    parser.add_argument(
        "--port",
        action="append",
        default=[],
        metavar="NAME=PORT",
        help="Override one lab port. Repeatable.",
    )
    parser.add_argument("--timeout", type=float, default=0.8)
    parser.add_argument(
        "--allow-down",
        action="store_true",
        help="Exit 0 when labs are not listening. Version mismatches still fail.",
    )
    parser.add_argument(
        "--require-version",
        action="store_true",
        help="Treat a healthy lab with no version field as a failure.",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--why",
        action="store_true",
        help="Print why the Makefile targets are not long-running servers.",
    )
    args = parser.parse_args(argv)
    overrides = _parse_ports(args.port)
    expected = expected_version()
    rows = probe_all(
        host=args.host,
        offset=args.port_offset,
        overrides=overrides,
        expected=expected,
        timeout=args.timeout,
    )
    if args.json:
        json.dump(
            {"expected": expected, "host": args.host, "labs": rows},
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"expected version {expected} on {args.host}\n")
        sys.stdout.write(format_table(rows))
    if args.why:
        for name, text in NOT_A_DAEMON.items():
            sys.stdout.write(f"\n{name}: {text}\n")
    return exit_code(
        rows, allow_down=args.allow_down, require_version=args.require_version
    )


if __name__ == "__main__":
    raise SystemExit(main())
