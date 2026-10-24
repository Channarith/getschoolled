"""The homework bakeoff (up to 20 rounds) is a polled background job."""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

import theodore_homework_lab.main as homework

client = TestClient(homework.app)


def test_bakeoff_returns_202_fast_and_finishes_as_a_job(monkeypatch):
    gate = threading.Event()

    def slow(rounds):
        gate.wait(5)
        return {"rounds_done": rounds}

    monkeypatch.setattr(homework.get_runner(), "run_blocking", slow)
    started = time.perf_counter()
    res = client.post("/api/homework/bakeoff?rounds=3")
    assert time.perf_counter() - started < 2.0
    assert res.status_code == 202
    gate.set()
    end = time.time() + 8
    job = {}
    while time.time() < end:
        job = client.get(res.json()["status_url"]).json()
        if job["state"] in ("done", "failed"):
            break
        time.sleep(0.03)
    assert job["state"] == "done" and job["result"] == {"rounds_done": 3}
