import threading
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aoep_shared.background_jobs import (
    JobError, JobRunner, accepted_response, install_job_status_route, payload_key,
)


def wait_for(runner, job_id, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        job = runner.get(job_id)
        if job and job["state"] not in ("queued", "running"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_submit_returns_immediately_for_a_slow_job_and_result_is_polled():
    runner = JobRunner(max_workers=2)
    gate = threading.Event()

    def slow(report):
        report(0.5, "halfway")
        gate.wait(5)
        return {"ok": True}

    started = time.perf_counter()
    snap = runner.submit("slow", slow)
    assert time.perf_counter() - started < 0.5
    assert snap["state"] in ("queued", "running")
    time.sleep(0.1)
    mid = runner.get(snap["job_id"])
    assert mid["state"] == "running" and mid["progress"] == 0.5 and mid["message"] == "halfway"
    gate.set()
    done = wait_for(runner, snap["job_id"])
    assert done["state"] == "done" and done["result"] == {"ok": True} and done["progress"] == 1.0


def test_failures_become_failed_jobs_with_friendly_messages():
    runner = JobRunner()

    def bad(report):
        raise JobError("bad_request", "Pick at least one source.")

    def boom(report):
        raise RuntimeError("secret internal detail")

    one = wait_for(runner, runner.submit("a", bad)["job_id"])
    assert one["state"] == "failed" and one["error"] == {"code": "bad_request", "message": "Pick at least one source."}
    two = wait_for(runner, runner.submit("b", boom)["job_id"])
    assert two["state"] == "failed" and two["error"]["code"] == "internal"
    assert "secret" not in two["error"]["message"]


def test_duplicate_submit_joins_the_running_job_and_exclusive_kind_does_too():
    runner = JobRunner(max_workers=2)
    gate = threading.Event()

    def fn(report):
        gate.wait(5)
        return "x"

    first = runner.submit("build", fn, key=payload_key("build", {"a": 1}))
    again = runner.submit("build", fn, key=payload_key("build", {"a": 1}))
    other = runner.submit("build", fn, key=payload_key("build", {"a": 2}))
    assert again["job_id"] == first["job_id"] and again["joined"] is True
    assert other["job_id"] != first["job_id"]
    t1 = runner.submit("train", fn, exclusive=True)
    t2 = runner.submit("train", fn, exclusive=True)
    assert t2["job_id"] == t1["job_id"]
    gate.set()
    wait_for(runner, first["job_id"])
    wait_for(runner, other["job_id"])
    wait_for(runner, t1["job_id"])
    fresh = runner.submit("build", lambda r: 1, key=payload_key("build", {"a": 1}))
    assert fresh["job_id"] != first["job_id"]


def test_concurrent_jobs_are_bounded_and_all_finish():
    runner = JobRunner(max_workers=2)
    live = {"now": 0, "peak": 0}
    lock = threading.Lock()

    def work(report):
        with lock:
            live["now"] += 1
            live["peak"] = max(live["peak"], live["now"])
        time.sleep(0.1)
        with lock:
            live["now"] -= 1
        return 1

    ids = [runner.submit("w", work)["job_id"] for _ in range(6)]
    assert all(wait_for(runner, i)["state"] == "done" for i in ids)
    assert live["peak"] <= 2


def test_results_survive_a_new_runner_and_interrupted_jobs_are_reported(tmp_path):
    runner = JobRunner(store_dir=tmp_path)
    done = wait_for(runner, runner.submit("p", lambda r: {"n": 1})["job_id"])
    reborn = JobRunner(store_dir=tmp_path)
    assert reborn.get(done["job_id"])["result"] == {"n": 1}
    (tmp_path / "abc123.json").write_text(
        '{"job_id":"abc123","kind":"x","state":"running","created_at":1,"finished_at":null,"progress":0.2}'
    )
    stale = reborn.get("abc123")
    assert stale["state"] == "failed" and stale["error"]["code"] == "interrupted"
    assert reborn.get("../etc/passwd") is None


def test_http_pattern_202_then_poll_and_unknown_is_friendly_404():
    app = FastAPI()
    runner = JobRunner()
    gate = threading.Event()

    def slow(report):
        gate.wait(5)
        return {"v": 1}

    @app.post("/go")
    def go():
        return accepted_response(runner.submit("go", slow), "/jobs")

    install_job_status_route(app, runner, "/jobs")
    client = TestClient(app)
    started = time.perf_counter()
    res = client.post("/go")
    assert time.perf_counter() - started < 1.0
    assert res.status_code == 202 and res.headers["location"].startswith("/jobs/")
    assert client.get(res.json()["status_url"]).json()["state"] in ("queued", "running")
    gate.set()
    wait_for(runner, res.json()["job_id"])
    final = client.get(res.json()["status_url"]).json()
    assert final["state"] == "done" and final["result"] == {"v": 1}
    missing = client.get("/jobs/nope")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
