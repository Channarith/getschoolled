"""Sharding, bundles, object store, quality tiers and the publisher (offline, fake servers)."""

from __future__ import annotations

import gzip
import json
import sqlite3
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from aoep_shared.harvest.bundle import (
    export_bundle,
    import_bundle,
    license_gate,
    open_index,
    verify_bundle,
)
from aoep_shared.harvest.objectstore import (
    LocalObjectStore,
    canonical_bytes,
    content_sha256,
    course_key,
    pack_course,
    unpack_course,
)
from aoep_shared.harvest.publish import (
    CircuitBreaker,
    CurriculumHttpSink,
    ObjectStoreIndexSink,
    PublishConfig,
    Publisher,
    TokenBucket,
    build_payload,
    default_transport,
)
from aoep_shared.harvest.quality import NearDuplicateIndex, assign_tier, metrics, sample_for_review
from aoep_shared.harvest.queue_store import PersistentHarvestQueue
from aoep_shared.harvest.shard import ShardFilter, ShardMap, host_key, virtual_shard
from aoep_shared.harvest.sources import SourceSpec


# ----------------------------------------------------------------------------- shards
def test_host_key_ignores_www_port_case_and_path():
    assert host_key("https://WWW.OpenStax.org:443/a/b") == host_key("http://openstax.org/other")
    assert host_key("openstax.org") == "openstax.org"


def test_shard_map_is_deterministic_and_order_independent():
    a = ShardMap.build({"spark": 3, "kalel": 2, "mac": 1})
    b = ShardMap.build({"mac": 1, "kalel": 2, "spark": 3})
    assert a == b
    urls = [f"https://site{i}.example.org/page" for i in range(500)]
    assert [a.owner(u) for u in urls] == [b.owner(u) for u in urls]


def test_every_url_has_exactly_one_owner_and_pages_of_a_host_stay_together():
    m = ShardMap.build({"spark": 3, "kalel": 2, "mac": 1})
    filters = {n: ShardFilter(m, n) for n in m.machines()}
    for i in range(300):
        url = f"https://host{i % 40}.edu/p{i}"
        assert sum(f.owns(url) for f in filters.values()) == 1
    assert len({m.owner(f"https://ocw.mit.edu/page{i}") for i in range(50)}) == 1


def test_shard_balance_tracks_weights():
    m = ShardMap.build({"spark": 3, "kalel": 2, "mac": 1})
    counts = Counter(m.owner(f"https://h{i}.example.com/") for i in range(12000))
    total = sum(counts.values())
    for name, share in m.share().items():
        assert abs(counts[name] / total - share) < 0.04, (name, counts[name] / total, share)
    assert abs(sum(m.share().values()) - 1.0) < 1e-9


def test_shard_map_validation():
    with pytest.raises(ValueError):
        ShardMap.build({})
    with pytest.raises(ValueError):
        ShardMap.build({"a": 0})
    with pytest.raises(ValueError):
        ShardMap.build({"a": 1, "b": 1}, virtual_shards=1)
    assert ShardFilter().owns("https://anything.example/")  # unsharded owns everything


def test_shard_config_and_env(tmp_path, monkeypatch):
    cfg = tmp_path / "s.json"
    cfg.write_text(
        json.dumps(
            {"virtual_shards": 64, "machines": {"spark": {"weight": 2}, "mac": {"weight": 1}}}
        )
    )
    monkeypatch.setenv("HARVEST_SHARD_CONFIG", str(cfg))
    monkeypatch.setenv("HARVEST_MACHINE", "spark")
    f = ShardFilter.from_env()
    assert f.machine == "spark" and f.shard_map.virtual_shards == 64
    monkeypatch.setenv("HARVEST_MACHINE", "nope")
    with pytest.raises(ValueError):
        ShardFilter.from_env()
    monkeypatch.delenv("HARVEST_MACHINE")
    assert ShardFilter.from_env().shard_map is None


def test_queue_only_enqueues_owned_hosts(tmp_path):
    from aoep_shared.harvest.corpus_store import HarvestCorpusStore

    m = ShardMap.build({"spark": 1, "mac": 1})
    urls = [f"https://h{i}.example.org/x" for i in range(60)]
    queues = {}
    for name in ("spark", "mac"):
        store = HarvestCorpusStore(tmp_path / f"{name}.db")
        queues[name] = PersistentHarvestQueue(store, ShardFilter(m, name))
        queues[name].enqueue_many(SourceSpec(url=u, license="cc0") for u in urls)
    assert len(queues["spark"]) + len(queues["mac"]) == len(urls)
    assert queues["spark"].skipped_not_owned == len(queues["mac"])


# ----------------------------------------------------------------------------- object store
def test_local_store_is_idempotent_atomic_and_safe(tmp_path):
    s = LocalObjectStore(tmp_path)
    assert s.put("courses/ab/x.json.gz", b"1") is True
    assert s.put("courses/ab/x.json.gz", b"2") is False  # never overwrites
    assert s.get("courses/ab/x.json.gz") == b"1"
    assert list(s.list("courses/")) == ["courses/ab/x.json.gz"]
    with pytest.raises(ValueError):
        s.put("../escape", b"x")
    with pytest.raises(ValueError):
        s.put("/abs", b"x")


def test_pack_is_reproducible_and_roundtrips():
    course = {"b": 2, "a": [1, {"z": "é"}]}
    sha1, gz1 = pack_course(course)
    sha2, gz2 = pack_course({"a": [1, {"z": "é"}], "b": 2})  # key order must not matter
    assert (sha1, gz1) == (sha2, gz2)
    assert sha1 == content_sha256(canonical_bytes(course))
    assert unpack_course(gz1) == course
    assert course_key(sha1) == f"courses/{sha1[:2]}/{sha1}.json.gz"


# ----------------------------------------------------------------------------- quality
def _course(i: int, slides: int = 8, text: int = 500, score: int = 400) -> dict:
    return {
        "course_id": f"c{i}",
        "title": f"Course {i}",
        "language": "en",
        "composition_score": score,
        "slides": [
            {"title": f"S{j}", "body": (f"unique content {i}-{j} " + "word" * 3) * (text // 20)}
            for j in range(slides)
        ],
    }


def test_tier_gate_and_labels():
    ok = assign_tier(_course(1), key="a")
    assert ok.tier == 1 and not ok.failures
    thin = assign_tier(_course(2, slides=2, text=40), key="b")
    assert thin.tier == 0 and any("slides" in f or "text" in f for f in thin.failures)
    ph = _course(3)
    ph["slides"][0]["body"] = "lorem ipsum " * 300
    assert metrics(ph)["placeholder_ratio"] > 0
    assert assign_tier(_course(4, score=10), key="c").tier == 0
    assert assign_tier(_course(5), key="d", corroborate=lambda c: False).tier == 0  # hook can veto
    assert (
        assign_tier(_course(6), key="e", corroborate=lambda c: True).tier == 1
    )  # never tier 2 here


def test_near_duplicates_are_detected_not_unrelated_decks():
    idx = NearDuplicateIndex()
    base = _course(7)
    assert assign_tier(base, key="x", dedup=idx).tier == 1
    twin = json.loads(json.dumps(base))
    twin["course_id"] = "other"
    twin["slides"][3]["body"] += " tweak"
    d = assign_tier(twin, key="y", dedup=idx)
    assert d.duplicate_of == "x" and d.tier == 0
    assert assign_tier(_course(99), key="z", dedup=idx).duplicate_of is None


def test_review_sample_is_deterministic_and_at_least_one_per_source():
    ids = {"src1": [f"a{i}" for i in range(250)], "src2": ["only"]}
    s1, s2 = sample_for_review(ids), sample_for_review(ids)
    assert s1 == s2 and len(s1["src1"]) == 2 and s1["src2"] == ["only"]


# ----------------------------------------------------------------------------- bundles
def _make_machine(
    tmp_path: Path, name: str, courses: list[tuple[dict, str | None]]
) -> tuple[Path, Path]:
    root = tmp_path / name
    (root / "courses").mkdir(parents=True)
    db = root / "corpus.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
      CREATE TABLE sources (url_key TEXT PRIMARY KEY, url TEXT, license TEXT, subject TEXT, title TEXT, source_type TEXT);
      CREATE TABLE courses (course_id TEXT PRIMARY KEY, url_key TEXT, title TEXT, subject TEXT,
                            composition_score INTEGER, json_path TEXT, created_at TEXT);""")
    for i, (course, lic) in enumerate(courses):
        path = root / "courses" / f"{course['course_id']}.course.json"
        path.write_text(json.dumps(course))
        conn.execute(
            "INSERT INTO sources VALUES (?,?,?,?,?,?)",
            (f"k{i}", f"https://s{i}.org/", lic, "math", "t", "html"),
        )
        conn.execute(
            "INSERT INTO courses VALUES (?,?,?,?,?,?,?)",
            (course["course_id"], f"k{i}", course["title"], "math", 400, str(path), "2026-10-24"),
        )
    conn.commit()
    conn.close()
    return db, root


def test_export_import_roundtrip_dedup_and_license_gate(tmp_path):
    good, dup = _course(1), _course(1)  # identical content on two machines
    db_a, root_a = _make_machine(
        tmp_path, "spark", [(good, "cc-by"), (_course(2), "cc-by-nc"), (_course(3), "proprietary")]
    )
    db_b, root_b = _make_machine(tmp_path, "kalel", [(dup, "cc0"), (_course(4), "mit")])
    store = LocalObjectStore(tmp_path / "agg" / "store")
    idx = open_index(tmp_path / "agg" / "index.db")

    rep = export_bundle(db_a, tmp_path / "bundleA", machine="spark", repo_root=root_a)
    assert rep.courses == 3 and rep.objects_written == 3
    assert verify_bundle(tmp_path / "bundleA") == []
    again = export_bundle(
        db_a, tmp_path / "bundleA", machine="spark", repo_root=root_a
    )  # resumable/idempotent
    assert again.objects_written == 0 and again.objects_existing == 3

    ra = import_bundle(tmp_path / "bundleA", store, idx)
    assert ra.imported == 1 and ra.rejected_license == 2  # NC and unknown licenses never ship
    reasons = [r["reason"] for r in idx.execute("SELECT reason FROM rejected")]
    assert any("non-commercial" in r for r in reasons) and any("not allowed" in r for r in reasons)

    export_bundle(db_b, tmp_path / "bundleB", machine="kalel", repo_root=root_b)
    rb = import_bundle(tmp_path / "bundleB", store, idx)
    assert (
        rb.duplicates == 1 and rb.imported == 1
    )  # same content hash from another machine is not re-imported
    assert idx.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 2
    rc = import_bundle(tmp_path / "bundleB", store, idx)  # re-import is a no-op
    assert rc.imported == 0 and rc.duplicates == 2
    assert len(list(store.list("courses/"))) == 2  # nothing deleted, nothing duplicated


def test_import_detects_corruption_and_tampering_and_never_deletes(tmp_path):
    db, root = _make_machine(tmp_path, "m", [(_course(10), "cc0"), (_course(11), "cc0")])
    export_bundle(db, tmp_path / "b", machine="m", repo_root=root)
    objs = sorted((tmp_path / "b" / "courses").rglob("*.json.gz"))
    assert len(objs) == 2
    objs[0].write_bytes(b"not gzip")  # corrupt
    tampered = json.loads(gzip.decompress(objs[1].read_bytes()))
    tampered["title"] = "evil"
    objs[1].write_bytes(gzip.compress(json.dumps(tampered).encode()))  # valid gzip, wrong hash
    idx = open_index(tmp_path / "idx.db")
    store = LocalObjectStore(tmp_path / "st")
    rep = import_bundle(tmp_path / "b", store, idx)
    assert rep.imported == 0 and rep.rejected_integrity == 2
    assert len(list(store.list())) == 0
    assert all(p.exists() for p in objs)  # the bundle is untouched
    (tmp_path / "b" / "provenance.jsonl").write_text("changed\n")
    assert any("provenance" in p for p in verify_bundle(tmp_path / "b"))
    assert import_bundle(
        tmp_path / "b", store, idx
    ).problems  # refuses a bundle whose header does not match


def test_license_gate_rules():
    assert license_gate("CC-BY")[0] and license_gate("cc0")[0] and license_gate("MIT")[0]
    assert not license_gate("cc-by-nc-sa")[0] and not license_gate("cc-by-nc")[0]
    assert license_gate("cc-by-nc", require_commercial=False)[
        0
    ]  # explicit internal-research override
    assert not license_gate(None)[0] and not license_gate("all rights reserved")[0]


# ----------------------------------------------------------------------------- publisher
class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


def _loaded_index(tmp_path: Path, n: int, tier: int = 1):
    store = LocalObjectStore(tmp_path / "store")
    idx = open_index(tmp_path / "idx.db")
    shas = []
    for i in range(n):
        course = _course(100 + i)
        sha, gz = pack_course(course)
        store.put(course_key(sha), gz)
        idx.execute(
            "INSERT INTO courses (sha256,course_id,title,subject,language,slides,source_url,license,machine,tier,imported_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                sha,
                f"c{i}",
                course["title"],
                "math",
                "en",
                8,
                "https://x.org/",
                "cc0",
                "m",
                tier,
                "now",
            ),
        )
        shas.append(sha)
    idx.commit()
    return store, idx, shas


class FakeTransport:
    """Scriptable curriculum service: per-call status codes, records every request."""

    def __init__(self, script=None, existing: set | None = None) -> None:
        self.script, self.calls, self.existing = list(script or []), [], existing or set()

    def __call__(self, method, url, body, headers):
        self.calls.append((method, url, body, headers))
        if "/courses/search" in url:
            tag = url.split("tag=")[1].split("&")[0]
            return 200, {}, json.dumps([{"x": 1}] if tag in self.existing else []).encode()
        status = self.script.pop(0) if self.script else 200
        extra = {"retry-after": "7"} if status == 429 else {}
        return status, extra, b'{"detail":"nope"}' if status >= 400 else b"{}"


def _publisher(idx, store, transport, clock, **cfg):
    sink = CurriculumHttpSink("https://api.example", "secret", transport)
    c = PublishConfig(rate_per_sec=100, burst=100, backoff_base=1, **cfg)
    return Publisher(idx, store, sink, c, clock=clock.now, sleep=clock.sleep, rng=lambda: 1.0)


def test_publish_is_idempotent_and_resumable(tmp_path):
    store, idx, shas = _loaded_index(tmp_path, 5)
    clock, tr = FakeClock(), FakeTransport()
    rep = _publisher(idx, store, tr, clock, max_total=3).run()
    assert rep.published == 3 and rep.stopped == "max_total"
    rep2 = _publisher(
        idx, store, tr, clock
    ).run()  # a new process resumes where the last one stopped
    assert rep2.published == 2 and rep2.stopped == "done"
    posts = [c for c in tr.calls if c[0] == "POST"]
    assert len(posts) == 5 and len({p[2]["tags"][1] for p in posts}) == 5
    assert all(p[3]["X-Internal-Token"] == "secret" for p in posts)
    assert _publisher(idx, store, tr, clock).run().published == 0  # nothing left


def test_publish_skips_decks_the_catalog_already_has(tmp_path):
    store, idx, shas = _loaded_index(tmp_path, 3)
    tr = FakeTransport(existing={f"sha:{shas[0][:16]}"})
    rep = _publisher(idx, store, tr, FakeClock()).run()
    assert rep.skipped_existing == 1 and rep.published == 2


def test_dry_run_posts_nothing_and_marks_nothing(tmp_path):
    store, idx, _ = _loaded_index(tmp_path, 4)
    tr = FakeTransport()
    rep = _publisher(idx, store, tr, FakeClock(), dry_run=True).run()
    assert rep.dry_run == 4 and tr.calls == []
    assert (
        idx.execute("SELECT COUNT(*) FROM courses WHERE published_at IS NOT NULL").fetchone()[0]
        == 0
    )


def test_retries_with_backoff_and_retry_after(tmp_path):
    store, idx, _ = _loaded_index(tmp_path, 1)
    clock, tr = FakeClock(), FakeTransport(script=[503, 429, 200])
    rep = _publisher(idx, store, tr, clock, check_existing=False).run()
    assert rep.published == 1 and rep.retries == 2
    assert clock.sleeps[0] == pytest.approx(1.0)  # base * 2**0, jitter fixed at 1.0
    assert clock.sleeps[1] >= 7  # honors Retry-After over the computed backoff


def test_permanent_errors_are_recorded_once_and_never_retried(tmp_path):
    store, idx, shas = _loaded_index(tmp_path, 2)
    tr = FakeTransport(script=[422, 200])
    rep = _publisher(idx, store, tr, FakeClock(), check_existing=False).run()
    assert rep.failed_permanent == 1 and rep.published == 1 and rep.retries == 0
    assert idx.execute("SELECT status FROM publish_failures").fetchone()[0] == 422
    assert (
        _publisher(idx, store, FakeTransport(), FakeClock(), check_existing=False).run().published
        == 0
    )  # failed one stays parked


def test_auth_failure_stops_the_whole_run(tmp_path):
    store, idx, _ = _loaded_index(tmp_path, 3)
    rep = _publisher(
        idx, store, FakeTransport(script=[401]), FakeClock(), check_existing=False
    ).run()
    assert rep.stopped.startswith("auth") and rep.published == 0


def test_circuit_breaker_stops_flooding_a_failing_service(tmp_path):
    store, idx, _ = _loaded_index(tmp_path, 12)
    clock, tr = FakeClock(), FakeTransport(script=[503] * 500)
    rep = _publisher(
        idx,
        store,
        tr,
        clock,
        check_existing=False,
        max_retries=1,
        breaker_failures=3,
        breaker_cooldown=60,
        max_breaker_waits=1,
    ).run()
    assert rep.breaker_trips >= 1 and rep.stopped == "breaker_open" and rep.published == 0
    assert (
        len([c for c in tr.calls if c[0] == "POST"]) < 12 * 2
    )  # far fewer calls than hammering every deck
    assert any(s >= 59 for s in clock.sleeps)  # it waited out the cool-down before probing again


def test_token_bucket_and_breaker_units():
    clock = FakeClock()
    b = TokenBucket(2.0, 1, clock.now, clock.sleep)
    for _ in range(5):
        b.acquire()
    assert clock.t == pytest.approx(2.0, abs=0.01)  # 5 calls at 2/s with burst 1 take about 2 s
    b.slow_down()
    assert b.rate == 1.0
    cb = CircuitBreaker(2, 10, clock.now)
    cb.failure()
    assert cb.allow()
    cb.failure()
    assert not cb.allow() and cb.remaining() == pytest.approx(10)
    clock.t += 10
    assert cb.allow()
    cb.success()
    assert cb.opened_at is None


def test_object_store_index_sink_is_idempotent(tmp_path):
    store, idx, _ = _loaded_index(tmp_path, 3)
    out = LocalObjectStore(tmp_path / "pub")
    p = Publisher(
        idx, store, ObjectStoreIndexSink(out), PublishConfig(rate_per_sec=1000, burst=1000)
    )
    assert p.run().published == 3
    assert len(list(out.list("index/records/"))) == 3
    idx.execute("UPDATE courses SET published_at=NULL")
    idx.commit()
    assert p.run().skipped_existing == 3  # re-publishing finds the records already there


def test_payload_labels_the_tier():
    c = _course(1)
    assert "machine-generated" in build_payload(c, sha="a" * 64, tier=0)["tags"]
    assert "auto-validated" in build_payload(c, sha="a" * 64, tier=1)["tags"]


def test_default_transport_against_a_real_local_server():
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(
                (
                    self.path,
                    self.headers.get("X-Internal-Token"),
                    self.rfile.read(int(self.headers["Content-Length"])),
                )
            )
            self.send_response(201)
            self.end_headers()
            self.wfile.write(b"{}")

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"[]")

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        sink = CurriculumHttpSink(f"http://127.0.0.1:{srv.server_port}", "tok", default_transport)
        assert sink.exists("a" * 64) is False
        sink.publish("a" * 64, {"title": "t"})
        assert seen and seen[0][0] == "/courses" and seen[0][1] == "tok"
    finally:
        srv.shutdown()
