"""Round-trip persistence for the identity AccountStore."""

import pytest

from identity.persistence import PersistenceConflict, dump_state, load_state
from identity.store import AccountStore


def test_account_store_roundtrip_via_persistence():
    store = AccountStore()
    store.create("a@test.com", "Secret123", display_name="Alice")
    store.create("b@test.com", "Secret456", display_name="Bob")
    payload = dump_state(store)

    other = AccountStore()
    load_state(other, payload)
    assert len(other.list_all_accounts()) == 2
    assert other.by_email("a@test.com") is not None
    assert other.by_email("b@test.com") is not None


def test_stalled_redis_write_keeps_the_account(monkeypatch):
    from identity import persistence

    calls = {"n": 0}
    monkeypatch.setattr(persistence, "redis_configured", lambda: True)

    class _Stalled:
        def eval(self, *_args, **_kwargs):
            calls["n"] += 1
            raise TimeoutError("timed out")

        def close(self):
            pass

    monkeypatch.setattr(persistence, "_redis_client", lambda: _Stalled())
    store = AccountStore()
    email = "busy-redis@example.com"
    acct = store.create(email, "Secret123")
    assert acct.email == email
    assert store.by_email(email) is acct
    assert calls["n"] == 2


def test_plan_change_serializes_only_that_account(monkeypatch):
    from identity import persistence
    from aoep_shared.schemas import PlanTier

    store = AccountStore()
    alice = store.create("plan-a@example.com", "Secret123")
    for n in range(20):
        store.create(f"plan-other-{n}@example.com", "Secret123")

    seen: list[str] = []
    real_blob = persistence._blob

    def spy(st, aid):
        seen.append(aid)
        return real_blob(st, aid)

    class _Ok:
        def eval(self, *_args, **_kwargs):
            return 1

    monkeypatch.setattr(persistence, "redis_configured", lambda: True)
    monkeypatch.setattr(persistence, "_redis_client", lambda: _Ok())
    monkeypatch.setattr(persistence, "_blob", spy)
    store.set_tier(alice.id, PlanTier.FREE)
    store.authenticate("plan-a@example.com", "Secret123")
    assert set(seen) == {alice.id}


def test_persistence_conflict_is_not_treated_as_a_storage_outage(monkeypatch):
    from identity import persistence

    monkeypatch.setattr(persistence, "redis_configured", lambda: True)

    class _Racer:
        def eval(self, *_args, **_kwargs):
            return 0

        def get(self, *_args, **_kwargs):
            return None

        def hget(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(persistence, "_redis_client", lambda: _Racer())
    store = AccountStore()
    with pytest.raises(PersistenceConflict):
        store.create("race-redis@example.com", "Secret123")


def test_a_save_serializes_the_account_once(monkeypatch):
    from identity import persistence
    from aoep_shared.schemas import PlanTier

    store = AccountStore()
    alice = store.create("once-a@example.com", "Secret123")

    sent: list[str] = []
    seen: list[str] = []
    real_blob = persistence._blob

    def spy(st, aid):
        seen.append(aid)
        return real_blob(st, aid)

    class _Ok:
        def eval(self, _script, _n, _rev, _key, _idx, _email_idx, _aid, _expected, blob, _email):
            sent.append(blob)
            return 7

    monkeypatch.setattr(persistence, "redis_configured", lambda: True)
    monkeypatch.setattr(persistence, "_redis_client", lambda: _Ok())
    monkeypatch.setattr(persistence, "_blob", spy)
    store.set_tier(alice.id, PlanTier.FREE)
    assert seen == [alice.id]
    assert len(sent) == 1
    assert store._persisted_blobs[alice.id] == sent[0]
    assert store._account_revs[alice.id] == 7


def test_slow_identity_write_is_logged_with_its_duration(caplog, monkeypatch):
    import logging

    from fastapi.testclient import TestClient

    from identity import main

    monkeypatch.setattr(main, "_SLOW_REQUEST_MS", -1)
    with caplog.at_level(logging.WARNING, logger="identity.slow"):
        TestClient(main.app).post("/onboarding/complete", json={"learner_name": "x", "age_band": "adult"})
    assert any("slow identity write: POST /onboarding/complete" in r.message for r in caplog.records)
