"""Redis-backed live room + group class store tests."""

from __future__ import annotations

from aoep_shared.group_class_backend import (
    RedisGroupClassBackend,
    build_group_class_backend,
)
from aoep_shared.group_classes import GroupClassStore
from aoep_shared.live_room import LiveRoomStore
from aoep_shared.live_room_backend import (
    RedisLiveRoomBackend,
    build_live_room_backend,
)


class FakeRedis:
    """Minimal Redis stand-in (decode_responses=True semantics)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.sets: dict[str, set[str]] = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex

    def delete(self, key):
        self.store.pop(key, None)
        self.ttls.pop(key, None)

    def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(member)

    def srem(self, key, member):
        if key in self.sets:
            self.sets[key].discard(member)

    def smembers(self, key):
        return self.sets.get(key, set())


def _iso_future() -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()


def test_redis_live_room_roundtrip():
    r = FakeRedis()
    backend = RedisLiveRoomBackend(r, ttl_seconds=3600)
    store = LiveRoomStore(backend)
    store.open_room(
        room_id="class-shared",
        class_id="shared",
        session_id="s1",
        lesson_id="lesson",
        title="Shared",
        room_size=6,
    )
    assert "aoep:live:class-shared" in r.store
    assert r.ttls["aoep:live:class-shared"] == 3600
    learner = store.join("class-shared", "Ada", identity="ada-1")
    store.join_queue("class-shared", learner.id, question="Hi?")
    other = LiveRoomStore(backend)
    loaded = other.require("class-shared")
    assert loaded.learner_count == 1
    assert len(loaded.speaking_queue) == 1


def test_two_live_room_stores_share_chat():
    r = FakeRedis()
    backend = RedisLiveRoomBackend(r)
    pod_a = LiveRoomStore(backend)
    pod_b = LiveRoomStore(backend)
    pod_a.open_room(
        room_id="class-chat",
        class_id="chat",
        session_id="s1",
        lesson_id="lesson",
        title="Chat",
        room_size=4,
    )
    pid = pod_a.join("class-chat", "Grace", identity="g1").id
    pod_a.join_queue("class-chat", pid, question="May I speak?")
    pod_b.call_next("class-chat")
    pod_a.post_chat("class-chat", pid, "Hello from pod A")
    room = pod_b.require("class-chat")
    assert any(m.text == "Hello from pod A" for m in room.chat)


def test_redis_group_class_shared_start_fields():
    r = FakeRedis()
    backend = RedisGroupClassBackend(r)
    store_a = GroupClassStore(backend)
    gc = store_a.schedule(
        title="Evening class",
        lesson_id="intro-to-fractions",
        start_time=_iso_future(),
        platform="salareen",
        room_size=6,
        capacity=5,
    )
    gc.session_id = "sess-99"
    gc.live_room_id = f"class-{gc.id}"
    gc.status = "live"
    store_a.save(gc)

    store_b = GroupClassStore(backend)
    loaded = store_b.require(gc.id)
    assert loaded.session_id == "sess-99"
    assert loaded.live_room_id == f"class-{gc.id}"
    assert loaded.status == "live"


def test_factory_memory_override(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("LIVE_ROOM_BACKEND", "memory")
    monkeypatch.setenv("GROUP_CLASS_BACKEND", "memory")
    assert build_live_room_backend().name == "memory"
    assert build_group_class_backend().name == "memory"


def test_factory_defaults_to_memory_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("LIVE_ROOM_BACKEND", raising=False)
    assert build_live_room_backend().name == "memory"
