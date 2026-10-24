"""RAG lab slow routes: 202 at once, finish as polled jobs, never a 5xx."""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

import theodore_rag_lab.main as rag

client = TestClient(rag.app)


def _poll(url, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(url).json()
        if job["state"] in ("done", "failed"):
            return job
        time.sleep(0.03)
    raise AssertionError("job did not finish")


def test_run_blocking_is_202_fast_for_a_slow_bakeoff(monkeypatch):
    gate = threading.Event()

    def slow(hours):
        gate.wait(5)
        return {"rounds_done": 3}

    monkeypatch.setattr(rag.get_runner(), "run_blocking", slow)
    started = time.perf_counter()
    first = client.post("/api/rag/train/run-blocking", json={"hours": 0.05})
    second = client.post("/api/rag/train/run-blocking", json={"hours": 0.05})
    assert time.perf_counter() - started < 2.0
    assert first.status_code == 202 and second.json()["job_id"] == first.json()["job_id"]
    gate.set()
    done = _poll(first.json()["status_url"])
    assert done["state"] == "done" and done["result"] == {"rounds_done": 3}


def test_run_blocking_during_a_background_run_is_a_friendly_failed_job(monkeypatch):
    def busy(hours):
        raise RuntimeError("a background training run is active")

    monkeypatch.setattr(rag.get_runner(), "run_blocking", busy)
    res = client.post("/api/rag/train/run-blocking", json={"hours": 0.01})
    job = _poll(res.json()["status_url"])
    assert job["state"] == "failed" and job["error"]["code"] == "busy"
    assert "already active" in job["error"]["message"]


def test_corpus_update_is_a_job_and_unknown_job_is_a_friendly_404(monkeypatch):
    monkeypatch.setattr(rag, "run_train_update", lambda **kw: {"ingest": {"en": 7}})
    res = client.post("/api/corpus/train-update", json={"force": True, "language": "en"})
    assert res.status_code == 202
    assert _poll(res.json()["status_url"])["result"] == {"ingest": {"en": 7}}
    missing = client.get("/api/rag/jobs/doesnotexist")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
