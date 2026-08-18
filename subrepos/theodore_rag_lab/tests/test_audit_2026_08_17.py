"""Regression test for the 2026-08-17 audit (RAG lab).

POST /api/rag/train/run-blocking used to clobber a live background run's
status block (reset running/rounds_done/target_hours mid-thread) — now 409.
"""

from __future__ import annotations

import time

from theodore_rag_lab.bakeoff_loop import RagBakeoffRunner


def test_run_blocking_refuses_during_background_run():
    runner = RagBakeoffRunner()
    runner.start(hours=24.0)
    try:
        try:
            runner.run_blocking(hours=0.01)
            raise AssertionError("run_blocking ran during a live background run")
        except RuntimeError:
            pass
        # The background run's status block is untouched.
        assert runner.status()["running"] is True
        assert runner.status()["target_hours"] == 24.0
    finally:
        runner.stop()
        # Wait for the thread to actually exit so it can't leak into other tests.
        thread = runner._thread
        if thread:
            thread.join(timeout=5.0)
