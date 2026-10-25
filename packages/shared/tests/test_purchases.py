"""The purchase ledger: idempotent, one reference one account, refunds stick, backends behave alike."""

import json

import pytest

from aoep_shared.purchases import (
    PurchaseConflict, PurchaseStore, PurchaseStoreUnavailable, _FileBackend, _MemoryBackend, _RedisBackend, build_store,
)


def _paid(store, **over):
    args = dict(account_id="acct-1", course_id="drivers-ed", amount_cents=1999, provider="stripe", provider_ref="cs_1", email="a@example.com")
    args.update(over)
    return store.record_paid(**args)


def test_record_is_idempotent_and_numbers_orders():
    store = PurchaseStore(_MemoryBackend(), clock=lambda: 1_800_000_000.0)
    first, created = _paid(store)
    again, created_again = _paid(store)
    assert created and not created_again
    assert first["order_id"] == again["order_id"] and first["order_id"].startswith("SAL-2027-")
    assert first["total_cents"] == 1999 and first["status"] == "paid"
    second, _ = _paid(store, provider_ref="cs_2", account_id="acct-2")
    assert second["order_id"] != first["order_id"]
    assert store.is_paid("acct-1", "drivers-ed") and not store.is_paid("acct-3", "drivers-ed")


def test_tax_is_kept_apart_from_the_price():
    order, _ = _paid(PurchaseStore(_MemoryBackend()), tax_cents=145)
    assert (order["amount_cents"], order["tax_cents"], order["total_cents"]) == (1999, 145, 2144)


def test_a_reference_cannot_be_claimed_by_another_account_or_course():
    store = PurchaseStore(_MemoryBackend())
    _paid(store)
    with pytest.raises(PurchaseConflict):
        _paid(store, account_id="thief")
    with pytest.raises(PurchaseConflict):
        _paid(store, course_id="food-safety")
    assert any(row["event"] == "conflict" for row in store.audit_log())
    assert not store.is_paid("thief", "drivers-ed")


def test_provider_references_are_scoped_by_provider():
    store = PurchaseStore(_MemoryBackend())
    _, a = _paid(store, provider="stripe", provider_ref="X1")
    _, b = _paid(store, provider="paypal", provider_ref="X1", account_id="acct-2")
    assert a and b


def test_refund_and_revoke_stick_and_never_reactivate_on_replay():
    store = PurchaseStore(_MemoryBackend())
    order, _ = _paid(store)
    store.mark_refunded(order["order_id"], reason="requested", by="admin")
    assert not store.is_paid("acct-1", "drivers-ed")
    replay, created = _paid(store)  # a late duplicate webhook
    assert not created and replay["status"] == "refunded" and not store.is_paid("acct-1", "drivers-ed")
    other, _ = _paid(store, provider="apple", provider_ref="tx-9", account_id="acct-5")
    revoked = store.revoke_by_ref("apple", "tx-9", reason="REFUND")
    assert revoked["status"] == "revoked" and not store.is_paid("acct-5", "drivers-ed")
    assert store.revoke_by_ref("apple", "tx-9", reason="REFUND")["status"] == "revoked"  # idempotent


def test_list_for_account_and_find_orders():
    store = PurchaseStore(_MemoryBackend())
    _paid(store)
    _paid(store, provider_ref="cs_2", course_id="food-safety")
    assert {o["course_id"] for o in store.list_for_account("acct-1")} == {"drivers-ed", "food-safety"}
    assert len(store.find_orders(lambda o: o["course_id"] == "food-safety")) == 1


def test_file_backend_survives_a_restart(tmp_path):
    path = tmp_path / "p.json"
    _paid(PurchaseStore(_FileBackend(path)))
    reopened = PurchaseStore(_FileBackend(path))
    assert reopened.is_paid("acct-1", "drivers-ed")
    assert _paid(reopened)[1] is False


class _FakeRedis:
    def __init__(self):
        self.h, self.l, self.n = {}, {}, {}

    def incr(self, k): self.n[k] = self.n.get(k, 0) + 1; return self.n[k]
    def hget(self, h, f): return self.h.get(h, {}).get(f, "").encode() if f in self.h.get(h, {}) else None
    def hset(self, h, f, v): self.h.setdefault(h, {})[f] = v
    def hsetnx(self, h, f, v):
        row = self.h.setdefault(h, {})
        if f in row: return 0
        row[f] = v; return 1
    def hdel(self, h, f): self.h.get(h, {}).pop(f, None)
    def hgetall(self, h): return {k.encode(): v.encode() for k, v in self.h.get(h, {}).items()}
    def rpush(self, k, v): self.l.setdefault(k, []).append(v)
    def lrange(self, k, a, b): return [x.encode() for x in self.l.get(k, [])]


def test_redis_backend_matches_the_memory_backend():
    store = PurchaseStore(_RedisBackend(_FakeRedis()))
    order, created = _paid(store)
    assert created and store.is_paid("acct-1", "drivers-ed")
    assert _paid(store)[0]["order_id"] == order["order_id"]
    with pytest.raises(PurchaseConflict):
        _paid(store, account_id="thief")
    store.mark_refunded(order["order_id"], reason="r", by="admin")
    assert not store.is_paid("acct-1", "drivers-ed")


def test_cloud_without_redis_fails_closed_instead_of_forgetting(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.setenv("PURCHASES_BACKEND", "auto")
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(PurchaseStoreUnavailable):
        build_store()


def test_local_without_redis_uses_a_file(monkeypatch, tmp_path):
    monkeypatch.setenv("DEPLOY_MODE", "local")
    monkeypatch.setenv("PURCHASES_BACKEND", "auto")
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = build_store(tmp_path)
    _paid(store)
    assert json.loads((tmp_path / "payments" / "purchases.json").read_text())["hashes"]
