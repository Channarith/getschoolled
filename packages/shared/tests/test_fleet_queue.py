"""Queue logic: leases, retries, caps, windows, preemption, dedupe, sharding. No processes are started."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from aoep_shared.fleet_queue import (
    ConfigError,
    JobType,
    Queue,
    backoff_seconds,
    host_of,
    in_window,
    load_manifest,
    machine_for_shard,
    render_cmd,
    shard_for,
    shard_of_url,
)

REPO = Path(__file__).resolve().parents[3]
LA = ZoneInfo("America/Los_Angeles")


def at(hour: int, minute: int = 0, day: int = 24) -> float:
    return datetime(2026, 10, day, hour, minute, tzinfo=LA).timestamp()


class Clock:
    def __init__(self, t: float = 1_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


def spec(name: str = "job", **kw) -> JobType:
    raw = {"name": name, "cmd": ["true"], "resource": "cpu", **kw}
    return JobType.from_dict(raw)


CAPS = {"gpu": 1, "cpu": 2, "net": 2}


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def q(clock: Clock) -> Queue:
    return Queue(":memory:", clock=clock)


# ---- manifests -------------------------------------------------------------------------------
def test_real_manifests_load_and_are_consistent():
    types, caps, _ = load_manifest(REPO / "scripts" / "fleet" / "jobs")
    assert set(types) == {
        "harvest-crawl", "translate-stage", "voice-ingest", "voice-prep",
        "finetune-nightly", "finetune-kalel-nightly", "frozen-eval", "frozen-eval-small",
        "compare-bases-small", "grow-train-set", "tts-bakeoff", "validate-translations",
    }
    assert all(c["gpu"] <= 1 for c in caps.values()), "never more than one GPU job per machine"
    assert caps["mac"]["gpu"] == 0, "the Mac never runs GPU jobs"
    assert types["finetune-nightly"].priority > types["frozen-eval"].priority > types["translate-stage"].priority > types["voice-ingest"].priority
    assert types["finetune-kalel-nightly"].roles == ("kalel",)
    assert types["finetune-kalel-nightly"].priority == types["finetune-nightly"].priority
    assert not types["finetune-kalel-nightly"].preemptible
    assert types["voice-prep"].roles == ("kalel",) and types["voice-prep"].resource == "net"
    assert types["grow-train-set"].resource == "cpu" and "kalel" in types["grow-train-set"].roles
    assert not types["finetune-nightly"].preemptible, "a half-trained adapter must not be stopped mid-run"
    assert types["voice-ingest"].preemptible and types["translate-stage"].preemptible
    for t in types.values():
        assert t.resource in ("gpu", "cpu", "net")
        if t.resource == "gpu":
            assert t.needs_cuda, f"{t.name}: GPU jobs must pass the CUDA check"
        assert "mac" not in t.roles or t.resource != "gpu"


@pytest.mark.parametrize("bad", [
    {"name": "x", "cmd": []},
    {"name": "x", "cmd": ["a"], "resource": "tpu"},
    {"name": "Bad Name", "cmd": ["a"]},
    {"name": "x", "cmd": ["a"], "window": ["25:00", "07:00"]},
    {"name": "x", "cmd": ["a"], "priority": 200},
    {"name": "x", "cmd": ["a"], "resource": "gpu", "gs_args": ["--gpu"]},
    {"name": "x", "cmd": "a b"},
])
def test_bad_manifests_are_rejected(bad):
    with pytest.raises(ConfigError):
        JobType.from_dict(bad)


def test_render_cmd_fills_placeholders_and_never_leaves_braces():
    s = spec(cmd=["run", "{share}", "--n", "{n}", "{home}/x/{day}"], machine_params={"spark": {"share": "spark"}}, defaults={"n": 3})
    assert render_cmd(s, {}, "spark", "/repo", "/home/u", "2026-10-24") == ["run", "spark", "--n", "3", "/home/u/x/2026-10-24"]
    with pytest.raises(ConfigError):
        render_cmd(s, {}, "mac", "/repo", "/home/u", "2026-10-24")  # no value for {share} on mac


# ---- windows ----------------------------------------------------------------------------------
def test_window_wraps_midnight_and_uses_the_configured_zone():
    w = ("22:00", "07:00")
    assert in_window(w, at(23)) and in_window(w, at(3)) and in_window(w, at(6, 59))
    assert not in_window(w, at(7)) and not in_window(w, at(12)) and not in_window(w, at(21, 59))
    assert in_window(None, at(12))
    # The same instant is 15 hours ahead on the Spark (UTC+8). The window must NOT follow the machine clock.
    assert in_window(w, at(23), "America/Los_Angeles") and not in_window(w, at(23), "Asia/Shanghai")


# ---- claiming, caps, priority -----------------------------------------------------------------
def test_claim_takes_highest_priority_first(q: Queue):
    lo, hi = spec("lo", priority=20), spec("hi", priority=80)
    types = {"lo": lo, "hi": hi}
    q.enqueue(lo)
    q.enqueue(hi)
    assert q.claim("w", "spark", types, CAPS)["type"] == "hi"
    assert q.claim("w", "spark", types, CAPS)["type"] == "lo"


def test_concurrency_caps_per_resource_and_gpu_is_one(q: Queue):
    g = spec("g", resource="gpu")
    c = spec("c", resource="cpu")
    types = {"g": g, "c": c}
    for _ in range(3):
        q.enqueue(g)
        q.enqueue(c)
    claimed = [q.claim("w", "spark", types, CAPS) for _ in range(6)]
    kinds = [j["type"] for j in claimed if j]
    assert kinds.count("g") == 1, "never two GPU jobs at once"
    assert kinds.count("c") == 2
    assert claimed[-1] is None


def test_zero_cap_means_never_on_the_mac(q: Queue):
    g = spec("g", resource="gpu")
    q.enqueue(g)
    assert q.claim("w", "mac", {"g": g}, {"gpu": 0, "cpu": 1, "net": 1}) is None


def test_role_pin_window_and_disable_are_respected(q: Queue, clock: Clock):
    s = spec("night", roles=["spark"], window=["22:00", "07:00"])
    types = {"night": s}
    q.enqueue(s)
    clock.t = at(12)
    assert q.claim("w", "spark", types, CAPS) is None, "outside the window"
    clock.t = at(23)
    assert q.claim("w", "kalel", types, CAPS) is None, "wrong machine"
    q.set_setting("disabled_types", ["night"])
    assert q.claim("w", "spark", types, CAPS) is None, "disabled"
    q.set_setting("disabled_types", [])
    q.set_setting("paused", True)
    assert q.claim("w", "spark", types, CAPS) is None, "paused"
    q.set_setting("paused", False)
    assert q.claim("w", "spark", types, CAPS)["type"] == "night"


# ---- dedupe -----------------------------------------------------------------------------------
def test_dedupe_blocks_while_active_and_allows_after_done(q: Queue):
    s = spec("d")
    types = {"d": s}
    assert q.enqueue(s, dedupe_key="k") is not None
    assert q.enqueue(s, dedupe_key="k") is None
    job = q.claim("w", "spark", types, CAPS)
    assert q.enqueue(s, dedupe_key="k") is None, "still leased"
    q.mark_running(job["id"], "w", 1, "t")
    assert q.finish(job["id"], "w", 0, s) == "done"
    assert q.enqueue(s, dedupe_key="k") is not None, "finished jobs do not block a new one"


# ---- leases and crash recovery ----------------------------------------------------------------
def test_expired_lease_returns_the_job_to_the_queue(q: Queue, clock: Clock):
    s = spec("l")
    types = {"l": s}
    q.enqueue(s)
    job = q.claim("dead-worker", "spark", types, CAPS, ttl=120)
    q.mark_running(job["id"], "dead-worker", 999999, "tok")
    clock.advance(60)
    assert q.reap_expired() == [], "lease still valid"
    clock.advance(120)
    reaped = q.reap_expired()
    assert [r["id"] for r in reaped] == [job["id"]]
    row = q.get(job["id"])
    assert row["state"] == "queued" and row["leased_by"] is None and row["runner_pid"] is None
    clock.advance(31)
    again = q.claim("new-worker", "spark", types, CAPS)
    assert again["id"] == job["id"] and again["attempts"] == 2


def test_heartbeat_keeps_the_lease_and_reports_loss(q: Queue, clock: Clock):
    s = spec("h")
    q.enqueue(s)
    job = q.claim("w1", "spark", {"h": s}, CAPS, ttl=120)
    for _ in range(5):
        clock.advance(100)
        assert q.heartbeat(job["id"], "w1", 120)
        assert q.reap_expired() == []
    clock.advance(500)
    q.reap_expired()
    assert not q.heartbeat(job["id"], "w1", 120), "lease lost: the worker must stop the job"


def test_last_attempt_with_lost_lease_goes_dead_not_forever(q: Queue, clock: Clock):
    s = spec("m", max_attempts=1)
    q.enqueue(s)
    job = q.claim("w", "spark", {"m": s}, CAPS)
    clock.advance(1000)
    q.reap_expired()
    assert q.get(job["id"])["state"] == "dead"


# ---- retries, backoff, defer ------------------------------------------------------------------
def test_failure_retries_with_growing_backoff_then_goes_dead(q: Queue, clock: Clock):
    s = spec("r", max_attempts=3, backoff_s=100)
    types = {"r": s}
    q.enqueue(s)
    delays = []
    for attempt in (1, 2):
        job = q.claim("w", "spark", types, CAPS)
        assert job["attempts"] == attempt
        assert q.finish(job["id"], "w", 1, s) == "queued"
        delays.append(q.get(job["id"])["not_before"] - clock.t)
        assert q.claim("w", "spark", types, CAPS) is None, "backing off"
        clock.advance(delays[-1] + 1)
    assert delays[1] > delays[0]
    job = q.claim("w", "spark", types, CAPS)
    assert q.finish(job["id"], "w", 1, s) == "dead"


def test_config_errors_are_not_retried(q: Queue):
    s = spec("c78", max_attempts=5)
    q.enqueue(s)
    job = q.claim("w", "spark", {"c78": s}, CAPS)
    assert q.finish(job["id"], "w", 78, s) == "dead"


def test_exit_75_defers_without_using_an_attempt(q: Queue, clock: Clock):
    s = spec("d75", max_attempts=1)
    types = {"d75": s}
    q.enqueue(s)
    job = q.claim("w", "spark", types, CAPS)
    assert q.finish(job["id"], "w", 75, s) == "queued"
    row = q.get(job["id"])
    assert row["attempts"] == 0 and row["not_before"] > clock.t
    clock.advance(1000)
    assert q.claim("w", "spark", types, CAPS) is not None


def test_backoff_is_deterministic_and_capped():
    assert backoff_seconds(300, 1, 7) == backoff_seconds(300, 1, 7)
    assert backoff_seconds(300, 2, 7) > backoff_seconds(300, 1, 7)
    assert backoff_seconds(300, 40, 7) <= 6 * 3600 * 1.21


# ---- preemption -------------------------------------------------------------------------------
def test_higher_priority_gpu_job_preempts_a_preemptible_one(q: Queue):
    low = spec("low", resource="gpu", priority=30, preemptible=True)
    high = spec("high", resource="gpu", priority=90)
    types = {"low": low, "high": high}
    q.enqueue(low)
    running = q.claim("w", "spark", types, CAPS)
    q.mark_running(running["id"], "w", 5, "t")
    assert q.preemption_victim("spark", types, CAPS) is None, "nothing waiting"
    q.enqueue(high)
    victim = q.preemption_victim("spark", types, CAPS)
    assert victim and victim["id"] == running["id"]
    assert q.release(running["id"], "w", "preempted", delay_s=60)
    job = q.claim("w", "spark", types, CAPS)
    assert job["type"] == "high"
    # The preempted job is not penalised: it keeps its attempt count.
    assert q.get(running["id"])["attempts"] == 1 and q.get(running["id"])["state"] == "queued"


def test_non_preemptible_or_close_priority_jobs_are_left_alone(q: Queue):
    keep = spec("keep", resource="gpu", priority=30, preemptible=False)
    high = spec("high", resource="gpu", priority=90)
    types = {"keep": keep, "high": high}
    q.enqueue(keep)
    running = q.claim("w", "spark", types, CAPS)
    q.mark_running(running["id"], "w", 5, "t")
    q.enqueue(high)
    assert q.preemption_victim("spark", types, CAPS) is None, "a non-preemptible job is never stopped"

    near = spec("near", resource="gpu", priority=35, preemptible=True)
    close = spec("close", resource="gpu", priority=40)
    q2 = Queue(":memory:", clock=Clock())
    types2 = {"near": near, "close": close}
    q2.enqueue(near)
    r2 = q2.claim("w", "spark", types2, CAPS)
    q2.mark_running(r2["id"], "w", 6, "t")
    q2.enqueue(close)
    assert q2.preemption_victim("spark", types2, CAPS) is None, "only 5 points higher: inside the margin, so no churn"


# ---- scheduling the work itself ---------------------------------------------------------------
def test_fill_and_periodic_jobs_are_created_once(q: Queue, clock: Clock):
    fill = spec("fill", fill=True, roles=["spark"])
    daily = spec("daily", every_s=86400)
    types = {"fill": fill, "daily": daily}
    first = q.ensure_scheduled(types, "spark", {})
    assert len(first) == 2
    assert q.ensure_scheduled(types, "spark", {}) == [], "idempotent: nothing new while they wait"
    other = Queue(":memory:", clock=Clock())
    created = other.ensure_scheduled(types, "kalel", {})
    assert len(created) == 1, "the fill job is spark-only; only the periodic job is created on kalel"
    job = q.claim("w", "spark", types, CAPS)
    q.mark_running(job["id"], "w", 1, "t")
    q.finish(job["id"], "w", 0, types[job["type"]])
    clock.advance(86400 * 1.5)
    again = q.ensure_scheduled(types, "spark", {})
    assert again, "a new day starts a fresh periodic job, and a finished fill job is restocked"


def test_sharding_is_deterministic_by_host_and_machines_never_overlap(q: Queue):
    assert shard_for("example.org", 3) == shard_for("example.org", 3)
    assert shard_of_url("https://openstax.org/a/b", 3) == shard_of_url("http://OpenStax.org/c", 3), "by host, not by url"
    assert host_of("https://Site.edu:8080/x") == "site.edu"
    hosts = [f"site{i}.edu" for i in range(300)]
    counts = [sum(shard_for(h, 3) == s for h in hosts) for s in range(3)]
    assert all(60 < c < 140 for c in counts), counts
    s = spec("crawl", shards=3, roles=["kalel", "spark"])
    types = {"crawl": s}
    k, sp = Queue(":memory:", clock=Clock()), Queue(":memory:", clock=Clock())
    k.ensure_scheduled(types, "kalel", {})
    sp.ensure_scheduled(types, "spark", {})
    kshards = {json.loads(r["payload"])["shard"] for r in k.db.execute("SELECT payload FROM jobs")}
    sshards = {json.loads(r["payload"])["shard"] for r in sp.db.execute("SELECT payload FROM jobs")}
    assert kshards & sshards == set(), "no shard is crawled by two machines"
    assert kshards | sshards == {0, 1, 2}, "every shard is crawled by someone"
    assert machine_for_shard(0, ["spark", "kalel"]) == machine_for_shard(0, ["kalel", "spark"]), "order independent"


# ---- status -----------------------------------------------------------------------------------
def test_status_explains_why_work_is_not_running(q: Queue, clock: Clock):
    now_s = spec("now")
    later = spec("later", window=["22:00", "07:00"])
    gone = spec("gone", roles=["kalel"])
    types = {"now": now_s, "later": later, "gone": gone}
    clock.t = at(12)
    for s in types.values():
        q.enqueue(s)
    st = q.status("spark", types, CAPS)
    assert st["queued_eligible"] == 1
    assert st["queued_blocked"] == {"outside-window": 1, "other-machine": 1}
    job = q.claim("w", "spark", types, CAPS)
    q.mark_running(job["id"], "w", 1, "t")
    q.finish(job["id"], "w", 0, now_s)
    st = q.status("spark", types, CAPS)
    assert "now" in st["last_success"]
