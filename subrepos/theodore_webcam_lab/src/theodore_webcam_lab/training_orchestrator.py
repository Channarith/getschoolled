from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainingTask:
    task_id: str
    description: str
    command: list[str]
    cadence_minutes: int
    timeout_seconds: int = 7200
    enabled: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> TrainingTask:
        task_id = str(raw.get("task_id", "")).strip()
        description = str(raw.get("description", "")).strip()
        command_raw = raw.get("command", [])
        cadence_minutes = int(raw.get("cadence_minutes", 0))
        timeout_seconds = int(raw.get("timeout_seconds", 7200))
        enabled = bool(raw.get("enabled", True))
        if not task_id:
            raise ValueError("task_id is required")
        if not description:
            raise ValueError(f"description is required for task '{task_id}'")
        if not isinstance(command_raw, list) or not command_raw:
            raise ValueError(f"command list is required for task '{task_id}'")
        command = [str(item) for item in command_raw]
        if cadence_minutes <= 0:
            raise ValueError(f"cadence_minutes must be > 0 for task '{task_id}'")
        if timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be > 0 for task '{task_id}'")
        return cls(
            task_id=task_id,
            description=description,
            command=command,
            cadence_minutes=cadence_minutes,
            timeout_seconds=timeout_seconds,
            enabled=enabled,
        )


@dataclass(frozen=True)
class Runbook:
    loop_sleep_seconds: int
    tasks: list[TrainingTask]

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> Runbook:
        loop_sleep_seconds = int(raw.get("loop_sleep_seconds", 30))
        if loop_sleep_seconds <= 0:
            raise ValueError("loop_sleep_seconds must be > 0")
        task_rows = raw.get("tasks", [])
        if not isinstance(task_rows, list) or not task_rows:
            raise ValueError("runbook must contain a non-empty tasks list")
        tasks = [TrainingTask.from_dict(item) for item in task_rows]
        task_ids = [task.task_id for task in tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task_id values must be unique")
        return cls(loop_sleep_seconds=loop_sleep_seconds, tasks=tasks)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_runbook(path: Path) -> Runbook:
    return Runbook.from_dict(_load_json(path))


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "last_run_ms": {},
            "run_count": {},
            "last_exit_code": {},
            "last_error": {},
        }
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError("state file must be a JSON object")
    data.setdefault("last_run_ms", {})
    data.setdefault("run_count", {})
    data.setdefault("last_exit_code", {})
    data.setdefault("last_error", {})
    return data


def save_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _due(task: TrainingTask, state: dict[str, object], now_ms: int) -> bool:
    if not task.enabled:
        return False
    last_run_ms_map = state.get("last_run_ms", {})
    if not isinstance(last_run_ms_map, dict):
        return True
    last_run_raw = last_run_ms_map.get(task.task_id)
    if last_run_raw is None:
        return True
    last_run_ms = int(last_run_raw)
    cadence_ms = task.cadence_minutes * 60 * 1000
    return (now_ms - last_run_ms) >= cadence_ms


def run_once(
    *,
    runbook: Runbook,
    state: dict[str, object],
    now_ms: int | None = None,
    dry_run: bool = False,
) -> list[dict[str, object]]:
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    results: list[dict[str, object]] = []
    last_run_ms = state.setdefault("last_run_ms", {})
    run_count = state.setdefault("run_count", {})
    last_exit_code = state.setdefault("last_exit_code", {})
    last_error = state.setdefault("last_error", {})
    if not isinstance(last_run_ms, dict):
        raise ValueError("state.last_run_ms must be a dict")
    if not isinstance(run_count, dict):
        raise ValueError("state.run_count must be a dict")
    if not isinstance(last_exit_code, dict):
        raise ValueError("state.last_exit_code must be a dict")
    if not isinstance(last_error, dict):
        raise ValueError("state.last_error must be a dict")

    for task in runbook.tasks:
        if not _due(task, state, now_ms):
            continue
        record: dict[str, object] = {
            "task_id": task.task_id,
            "description": task.description,
            "scheduled_at_ms": now_ms,
            "dry_run": dry_run,
            "command": task.command,
        }
        if dry_run:
            exit_code = 0
            error_text = ""
        else:
            try:
                completed = subprocess.run(
                    task.command,
                    check=False,
                    timeout=task.timeout_seconds,
                    text=True,
                    capture_output=True,
                )
                exit_code = int(completed.returncode)
                error_text = completed.stderr.strip()
                record["stdout"] = completed.stdout.strip()
                record["stderr"] = error_text
            except subprocess.TimeoutExpired:
                exit_code = 124
                error_text = "timeout"
            except OSError as exc:
                exit_code = 127
                error_text = str(exc)

        last_run_ms[task.task_id] = now_ms
        run_count[task.task_id] = int(run_count.get(task.task_id, 0)) + 1
        last_exit_code[task.task_id] = exit_code
        last_error[task.task_id] = error_text
        record["exit_code"] = exit_code
        record["error"] = error_text
        results.append(record)
    return results


def run_forever(
    *,
    runbook_path: Path,
    state_path: Path,
    dry_run: bool = False,
    iterations: int | None = None,
    sleep_override_seconds: int | None = None,
) -> int:
    runbook = load_runbook(runbook_path)
    state = load_state(state_path)
    # 0 is a legitimate override (tight loop), so test for None rather than falsiness.
    loop_sleep = (
        sleep_override_seconds
        if sleep_override_seconds is not None
        else runbook.loop_sleep_seconds
    )
    count = 0
    while True:
        now_ms = int(time.time() * 1000)
        results = run_once(runbook=runbook, state=state, now_ms=now_ms, dry_run=dry_run)
        for result in results:
            print(json.dumps(result, sort_keys=True))
        save_state(state_path, state)
        count += 1
        if iterations is not None and count >= iterations:
            return 0
        time.sleep(loop_sleep)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="24/7 orchestrator for Theodore webcam vision training agents."
    )
    parser.add_argument(
        "--runbook",
        required=True,
        help="Path to the training runbook JSON file.",
    )
    parser.add_argument(
        "--state",
        default="subrepos/theodore_webcam_lab/training/runtime_state.json",
        help="Path to runtime state JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not execute commands; only schedule and record tasks.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Optional number of loop iterations (for CI/smoke checks).",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=int,
        default=None,
        help="Override runbook loop_sleep_seconds.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_forever(
        runbook_path=Path(args.runbook),
        state_path=Path(args.state),
        dry_run=bool(args.dry_run),
        iterations=args.iterations,
        sleep_override_seconds=args.sleep_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
