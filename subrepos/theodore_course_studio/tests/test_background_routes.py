"""Slow studio routes answer 202 at once and finish as polled background jobs."""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

import theodore_course_studio.main as studio

client = TestClient(studio.app)


def _poll(url: str, timeout: float = 8.0) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(url).json()
        if job["state"] in ("done", "failed"):
            return job
        time.sleep(0.03)
    raise AssertionError("job did not finish")


def test_course_build_is_202_fast_even_when_the_build_is_slow(monkeypatch):
    gate = threading.Event()

    class Course:
        course_id = "c-slow"
        audience = "general"

        def model_dump(self, mode="json"):
            return {"course_id": self.course_id, "language": "en"}

    def slow_build(**kwargs):
        gate.wait(5)
        return Course()

    monkeypatch.setattr(studio._builder, "build_from_sources", slow_build)
    started = time.perf_counter()
    res = client.post("/api/studio/courses/build", json={"max_slides": 3, "title": "slow-one"})
    assert time.perf_counter() - started < 2.0
    assert res.status_code == 202
    body = res.json()
    assert body["state"] in ("queued", "running") and body["status_url"].startswith("/api/studio/jobs/")
    dup = client.post("/api/studio/courses/build", json={"max_slides": 3, "title": "slow-one"})
    assert dup.json()["job_id"] == body["job_id"]
    gate.set()
    done = _poll(body["status_url"])
    assert done["state"] == "done" and done["result"]["course_id"] == "c-slow"


def test_course_build_bad_request_is_a_failed_job_not_a_5xx(monkeypatch):
    def reject(**kwargs):
        raise ValueError("Choose at least one source.")

    monkeypatch.setattr(studio._builder, "build_from_sources", reject)
    res = client.post("/api/studio/courses/build", json={"title": "bad-one"})
    assert res.status_code == 202
    job = _poll(res.json()["status_url"])
    assert job["state"] == "failed"
    assert job["error"] == {"code": "bad_request", "message": "Choose at least one source."}


def test_training_run_and_offline_are_jobs_and_exclusive(monkeypatch):
    gate = threading.Event()

    class Report:
        def model_dump(self, mode="json"):
            return {"run_id": "r1"}

    def slow_pass(**kwargs):
        gate.wait(5)
        return Report()

    monkeypatch.setattr(studio, "run_training_pass", slow_pass)
    started = time.perf_counter()
    first = client.post("/api/studio/training/run", json={})
    second = client.post("/api/studio/training/run", json={})
    assert time.perf_counter() - started < 2.0
    assert first.status_code == 202 and second.json()["job_id"] == first.json()["job_id"]
    gate.set()
    assert _poll(first.json()["status_url"])["result"] == {"run_id": "r1"}

    def missing(**kwargs):
        raise FileNotFoundError("nope")

    monkeypatch.setattr(studio, "run_offline_training", missing)
    off = client.post("/api/studio/training/offline", json={"resume_run_id": "gone"})
    assert off.status_code == 202
    job = _poll(off.json()["status_url"])
    assert job["state"] == "failed" and job["error"]["code"] == "not_found"


def test_unknown_job_is_a_friendly_404():
    res = client.get("/api/studio/jobs/doesnotexist")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"
