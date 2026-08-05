from __future__ import annotations

import json
from pathlib import Path

from theodore_webcam_lab.training_orchestrator import (
    load_runbook,
    load_state,
    run_once,
    save_state,
)


def _write_runbook(path: Path) -> None:
    payload = {
        "loop_sleep_seconds": 10,
        "tasks": [
            {
                "task_id": "quick-pass",
                "description": "quick command",
                "command": ["python3", "-c", "print('ok')"],
                "cadence_minutes": 1,
                "timeout_seconds": 15,
                "enabled": True,
            },
            {
                "task_id": "disabled-task",
                "description": "disabled command",
                "command": ["python3", "-c", "print('skip')"],
                "cadence_minutes": 1,
                "timeout_seconds": 15,
                "enabled": False,
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_once_dry_run_executes_due_tasks_and_updates_state(tmp_path: Path):
    runbook_path = tmp_path / "runbook.json"
    _write_runbook(runbook_path)
    runbook = load_runbook(runbook_path)
    state = load_state(tmp_path / "state.json")

    results = run_once(runbook=runbook, state=state, now_ms=100_000, dry_run=True)
    assert len(results) == 1
    assert results[0]["task_id"] == "quick-pass"
    assert results[0]["exit_code"] == 0
    assert state["run_count"]["quick-pass"] == 1
    assert state["last_run_ms"]["quick-pass"] == 100_000


def test_run_once_respects_cadence_window(tmp_path: Path):
    runbook_path = tmp_path / "runbook.json"
    _write_runbook(runbook_path)
    runbook = load_runbook(runbook_path)
    state = load_state(tmp_path / "state.json")
    state["last_run_ms"]["quick-pass"] = 50_000

    # Cadence is 1 minute, so only 30s elapsed here.
    results = run_once(runbook=runbook, state=state, now_ms=80_000, dry_run=True)
    assert results == []

    # Now cadence threshold is crossed.
    results2 = run_once(runbook=runbook, state=state, now_ms=111_000, dry_run=True)
    assert len(results2) == 1
    assert results2[0]["task_id"] == "quick-pass"


def test_run_once_executes_command_and_captures_output(tmp_path: Path):
    runbook_path = tmp_path / "runbook.json"
    _write_runbook(runbook_path)
    runbook = load_runbook(runbook_path)
    state_path = tmp_path / "state.json"
    state = load_state(state_path)

    results = run_once(runbook=runbook, state=state, now_ms=200_000, dry_run=False)
    assert len(results) == 1
    result = results[0]
    assert result["task_id"] == "quick-pass"
    assert result["exit_code"] == 0
    assert result["stdout"] == "ok"
    assert result["error"] == ""

    save_state(state_path, state)
    loaded_state = load_state(state_path)
    assert loaded_state["last_exit_code"]["quick-pass"] == 0
