"""Round-trip persistence for the identity AccountStore."""

from identity.persistence import dump_state, load_state
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
