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
