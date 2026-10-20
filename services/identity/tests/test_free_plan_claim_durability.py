"""Adversarial checks for free-plan seat durability.

A restart must not forget a claim, two replicas must not admit more than the
cap, and concurrent claims in one process must stop at the cap.
"""

from __future__ import annotations

import threading
import time

import pytest

from identity.persistence import (
    FREE_CLAIM_KEY,
    FreeClaimUnavailable,
    _COUNT_FREE_CLAIMS_LUA,
    _RESERVE_FREE_CLAIM_LUA,
    dump_state,
    load_state,
)
from identity.store import Account, AccountStore


class FakeRedis:
    """In-process stand-in whose eval is atomic, matching a Redis Lua script."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.sets: dict[str, set[str]] = {}
        self.scripts: list[str] = []
        self._lock = threading.Lock()

    def ping(self):
        return True

    def set(self, key, value, *args, **kwargs):
        with self._lock:
            self.values[key] = value
        return True

    def get(self, key):
        with self._lock:
            return self.values.get(key)

    def hgetall(self, key):
        with self._lock:
            return dict(self.hashes.get(key, {}))

    def delete(self, key):
        with self._lock:
            self.values.pop(key, None)
        return 1

    def hget(self, key, field):
        with self._lock:
            return self.hashes.get(key, {}).get(field)

    def hset(self, key, field, value):
        with self._lock:
            self.hashes.setdefault(key, {})[field] = value
        return 1

    def hdel(self, key, field):
        with self._lock:
            self.hashes.get(key, {}).pop(field, None)
        return 1

    def sadd(self, key, member):
        with self._lock:
            self.sets.setdefault(key, set()).add(member)
        return 1

    def srem(self, key, member):
        with self._lock:
            self.sets.get(key, set()).discard(member)
        return 1

    def _cas(self, keys, argv):
        rev_key, acct_key, index_key, email_key = keys
        aid, expected, blob, email = argv
        revs = self.hashes.setdefault(rev_key, {})
        rev = revs.get(aid, "0")
        if rev != expected:
            return 0
        newrev = str(int(expected) + 1)
        revs[aid] = newrev
        self.values[acct_key] = blob
        self.sets.setdefault(index_key, set()).add(aid)
        if email:
            self.hashes.setdefault(email_key, {})[email] = aid
        return int(newrev)

    def eval(self, script, numkeys, *keys_and_args):
        self.scripts.append(script)
        keys = keys_and_args[:numkeys]
        argv = [str(part) for part in keys_and_args[numkeys:]]
        with self._lock:
            if "newrev" in script:
                return self._cas(keys, argv)
            key = keys[0]
            claims = self.hashes.setdefault(key, {})
            if script.lstrip().startswith("-- aoep-free-claim-count"):
                self._backfill(claims, argv[1:], int(argv[0]))
                return len(claims)
            account_id = argv[0]
            limit = int(argv[1])
            record = f"{argv[2]}|{argv[3]}"
            self._backfill(claims, argv[5:], int(argv[4]))
            existing = claims.get(account_id)
            if existing:
                return ["existing", existing]
            if len(claims) >= limit:
                return ["full", ""]
            claims[account_id] = record
            return ["new", record]

    @staticmethod
    def _backfill(claims: dict[str, str], pairs: list[str], count: int) -> None:
        idx = 0
        for _ in range(count):
            aid = pairs[idx]
            rec = pairs[idx + 1]
            if aid and rec and aid not in claims:
                claims[aid] = rec
            idx += 2


def _use_fake_redis(monkeypatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setenv("REDIS_URL", "redis://identity-test/0")
    monkeypatch.setattr("identity.persistence._redis_client", lambda: fake)
    return fake


def test_deserialize_restores_free_plan_timestamps_and_legacy_snapshots_load():
    from identity.persistence import _deserialize_account, _serialize_account

    claimed = 1_700_000_000.0
    expires = claimed + 14 * 86400
    acct = Account(
        id="acc-free",
        email="free@example.com",
        free_plan_claimed_at=claimed,
        free_plan_expires_at=expires,
    )
    restored = _deserialize_account(_serialize_account(acct))
    assert restored.free_plan_claimed_at == claimed
    assert restored.free_plan_expires_at == expires

    legacy = _deserialize_account({"id": "old", "email": "old@example.com"})
    assert legacy.free_plan_claimed_at is None
    assert legacy.free_plan_expires_at is None


def test_restart_replay_keeps_the_seat_and_does_not_extend_the_trial(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "local")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("FREE_PLAN_SEAT_LIMIT", "1")
    monkeypatch.setenv("FREE_PLAN_OFFER_START", "1")
    monkeypatch.setenv("FREE_PLAN_OFFER_DAYS", "36500")
    past = time.time() - 30 * 86400
    store = AccountStore()
    first = store.create(f"replay-{time.time_ns()}@example.com", "Secret123")
    store.claim_free_plan(first.id, now=past)
    original_expires = store.get_by_id(first.id).free_plan_expires_at

    restarted = AccountStore()
    load_state(restarted, dump_state(store))
    assert restarted.free_claim_count() == 1
    with pytest.raises(ValueError, match="ended"):
        restarted.claim_free_plan(first.id)
    assert restarted.get_by_id(first.id).free_plan_expires_at == original_expires

    fake = _use_fake_redis(monkeypatch)
    other = restarted.create(f"replay-next-{time.time_ns()}@example.com", "Secret123")
    with pytest.raises(ValueError, match="full"):
        restarted.claim_free_plan(other.id)
    assert first.id in fake.hashes[FREE_CLAIM_KEY]
    assert other.id not in fake.hashes[FREE_CLAIM_KEY]
    assert any("HSETNX" in script and "HLEN" in script for script in fake.scripts)
    assert _RESERVE_FREE_CLAIM_LUA.lstrip().startswith("-- aoep-free-claim-reserve")
    assert _COUNT_FREE_CLAIMS_LUA.lstrip().startswith("-- aoep-free-claim-count")


def test_concurrent_local_claims_stop_at_the_seat_cap(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "local")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("FREE_PLAN_SEAT_LIMIT", "5")
    monkeypatch.setenv("FREE_PLAN_OFFER_DAYS", "36500")
    store = AccountStore()
    ids = [
        store.create(f"race-{i}-{time.time_ns()}@example.com", "Secret123").id
        for i in range(16)
    ]
    ok: list[str] = []
    errors: list[str] = []
    guard = threading.Lock()
    barrier = threading.Barrier(len(ids))

    def claim(account_id: str) -> None:
        barrier.wait()
        try:
            store.claim_free_plan(account_id)
        except ValueError as exc:
            with guard:
                errors.append(str(exc))
            return
        with guard:
            ok.append(account_id)

    threads = [threading.Thread(target=claim, args=(account_id,)) for account_id in ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(ok) == 5
    assert store.free_claim_count() == 5
    assert errors
    assert all("full" in item.lower() for item in errors)


def test_two_replicas_share_one_atomic_seat_cap(monkeypatch):
    monkeypatch.setenv("FREE_PLAN_SEAT_LIMIT", "4")
    monkeypatch.setenv("FREE_PLAN_OFFER_DAYS", "36500")
    fake = _use_fake_redis(monkeypatch)
    left = AccountStore()
    right = AccountStore()
    left_ids = [
        left.create(f"left-{i}-{time.time_ns()}@example.com", "Secret123").id
        for i in range(6)
    ]
    right_ids = [
        right.create(f"right-{i}-{time.time_ns()}@example.com", "Secret123").id
        for i in range(6)
    ]
    ok: list[str] = []
    guard = threading.Lock()
    barrier = threading.Barrier(len(left_ids) + len(right_ids))

    def claim(store: AccountStore, account_id: str) -> None:
        barrier.wait()
        try:
            store.claim_free_plan(account_id)
        except ValueError:
            return
        with guard:
            ok.append(account_id)

    threads = [
        threading.Thread(target=claim, args=(left, account_id)) for account_id in left_ids
    ] + [
        threading.Thread(target=claim, args=(right, account_id)) for account_id in right_ids
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(ok) == 4
    assert len(fake.hashes[FREE_CLAIM_KEY]) == 4
    assert left.free_claim_count() == 4
    assert right.free_claim_count() == 4


def test_configured_redis_outage_does_not_grant_a_local_seat(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://identity-test/0")
    monkeypatch.setenv("FREE_PLAN_OFFER_DAYS", "36500")
    monkeypatch.setattr("identity.persistence._redis_client", lambda: None)
    store = AccountStore()
    acct = store.create(f"outage-{time.time_ns()}@example.com", "Secret123")
    with pytest.raises(FreeClaimUnavailable):
        store.claim_free_plan(acct.id)
    assert store.get_by_id(acct.id).free_plan_claimed_at is None


def test_local_compose_redis_hostname_uses_in_process_seat(monkeypatch):
    """config/local.env uses host ``redis``, which does not resolve on a laptop."""
    monkeypatch.setenv("DEPLOY_MODE", "local")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("FREE_PLAN_OFFER_DAYS", "36500")

    def _unresolved(*_args, **_kwargs):
        raise OSError("nodename nor servname provided, or not known")

    monkeypatch.setattr("aoep_shared.redis_url.socket.getaddrinfo", _unresolved)
    store = AccountStore()
    acct = store.create(f"local-redis-{time.time_ns()}@example.com", "Secret123")
    updated = store.claim_free_plan(acct.id)
    assert updated.free_plan_claimed_at is not None
    assert updated.tier.value == "free"


def test_cloud_cluster_redis_keeps_password_and_does_not_bypass(monkeypatch):
    """Vultr must dial the in-cluster Redis with its password, never the local seat lock."""
    from identity.persistence import effective_redis_url

    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.setenv("REDIS_URL", "redis://redis.aoep.svc.cluster.local:6379/0")
    monkeypatch.setenv("REDIS_PASSWORD", "cluster-secret")

    def _must_not_be_called(*_args, **_kwargs):
        raise AssertionError("cloud mode must not probe the compose hostname")

    monkeypatch.setattr("aoep_shared.redis_url.socket.getaddrinfo", _must_not_be_called)
    assert (
        effective_redis_url()
        == "redis://:cluster-secret@redis.aoep.svc.cluster.local:6379/0"
    )


def test_same_account_replay_across_replicas_does_not_refresh_expiry(monkeypatch):
    monkeypatch.setenv("FREE_PLAN_SEAT_LIMIT", "2")
    monkeypatch.setenv("FREE_PLAN_OFFER_START", "1")
    monkeypatch.setenv("FREE_PLAN_OFFER_DAYS", "36500")
    fake = _use_fake_redis(monkeypatch)
    past = time.time() - 40 * 86400
    origin = AccountStore()
    acct = origin.create(f"once-{time.time_ns()}@example.com", "Secret123")
    origin.claim_free_plan(acct.id, now=past)
    original = origin.get_by_id(acct.id).free_plan_expires_at

    replica = AccountStore()
    stripped = dump_state(origin)
    stripped["accounts"][acct.id]["free_plan_claimed_at"] = None
    stripped["accounts"][acct.id]["free_plan_expires_at"] = None
    load_state(replica, stripped)
    assert replica.get_by_id(acct.id).free_plan_claimed_at is None
    with pytest.raises(ValueError, match="ended"):
        replica.claim_free_plan(acct.id)
    restored = replica.get_by_id(acct.id)
    assert restored.free_plan_claimed_at == pytest.approx(past, abs=0.001)
    assert restored.free_plan_expires_at == pytest.approx(original, abs=0.001)
    assert len(fake.hashes[FREE_CLAIM_KEY]) == 1


def _fresh_store(monkeypatch, *, mode: str, limit: str = "5") -> AccountStore:
    monkeypatch.setenv("DEPLOY_MODE", mode)
    monkeypatch.setenv("FREE_PLAN_SEAT_LIMIT", limit)
    monkeypatch.setenv("FREE_PLAN_OFFER_START", "1")
    monkeypatch.setenv("FREE_PLAN_OFFER_DAYS", "36500")
    return AccountStore()


@pytest.mark.parametrize("mode", ["cloud", "production", "prod", "staging", "edge"])
def test_nonlocal_without_redis_refuses_the_claim(monkeypatch, mode):
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = _fresh_store(monkeypatch, mode=mode, limit="100")
    acct = store.create(f"noredis-{mode}-{time.time_ns()}@example.com", "Secret123")
    with pytest.raises(FreeClaimUnavailable, match="cannot be claimed"):
        store.claim_free_plan(acct.id)
    assert store.get_by_id(acct.id).free_plan_claimed_at is None
    assert store.free_claim_count() == 0


def test_cloud_with_unreachable_redis_refuses_the_claim(monkeypatch):
    """A configured Redis that cannot be reached must not fall back in-process."""
    import sys
    import types

    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    store = _fresh_store(monkeypatch, mode="cloud", limit="100")

    class _Unreachable:
        def ping(self):
            raise ConnectionError("redis unreachable")

    redis_mod = sys.modules.get("redis")
    if redis_mod is None:
        try:
            import redis as redis_mod
        except ImportError:
            redis_mod = types.ModuleType("redis")
            monkeypatch.setitem(sys.modules, "redis", redis_mod)
    monkeypatch.setattr(redis_mod, "from_url", lambda *_a, **_k: _Unreachable(), raising=False)

    acct = store.create(f"down-{time.time_ns()}@example.com", "Secret123")
    with pytest.raises(FreeClaimUnavailable, match="cannot be claimed"):
        store.claim_free_plan(acct.id)
    assert store.get_by_id(acct.id).free_plan_claimed_at is None
    assert store.free_claim_count() == 0


@pytest.mark.parametrize("mode", ["local", "dev", "development", "test", "debug"])
def test_local_modes_without_redis_grant_a_seat(monkeypatch, mode):
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = _fresh_store(monkeypatch, mode=mode, limit="2")
    acct = store.create(f"mem-{mode}-{time.time_ns()}@example.com", "Secret123")
    granted = store.claim_free_plan(acct.id)
    assert granted.free_plan_claimed_at is not None
    assert store.free_claim_count() == 1


def test_local_without_redis_claims_atomically_in_process(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = _fresh_store(monkeypatch, mode="local", limit="5")
    ids = [
        store.create(f"atomic-{i}-{time.time_ns()}@example.com", "Secret123").id
        for i in range(16)
    ]
    ok: list[str] = []
    errors: list[BaseException] = []
    guard = threading.Lock()
    barrier = threading.Barrier(len(ids))

    def claim(account_id: str) -> None:
        barrier.wait()
        try:
            store.claim_free_plan(account_id)
        except BaseException as exc:
            with guard:
                errors.append(exc)
            return
        with guard:
            ok.append(account_id)

    threads = [threading.Thread(target=claim, args=(account_id,)) for account_id in ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(ok) == 5
    assert store.free_claim_count() == 5
    assert errors
    assert all(isinstance(exc, ValueError) and "full" in str(exc).lower() for exc in errors)
