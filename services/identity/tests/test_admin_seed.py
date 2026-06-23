"""Default admin account: seedable, idempotent, login by email OR 'admin' alias."""

from __future__ import annotations

from identity.store import AccountStore


def test_seed_admin_login_by_email_and_username_alias():
    store = AccountStore()
    admin = store.seed_admin("admin@salareen.com", "88888888", username="admin")
    assert admin.is_admin is True
    assert admin.public()["is_admin"] is True

    # Login works with the full email...
    assert store.authenticate("admin@salareen.com", "88888888") is not None
    # ...and with the bare "admin" username alias.
    assert store.authenticate("admin", "88888888") is not None
    # Wrong password rejected.
    assert store.authenticate("admin", "nope") is None


def test_seed_admin_is_idempotent():
    store = AccountStore()
    a = store.seed_admin("admin@salareen.com", "88888888")
    b = store.seed_admin("admin@salareen.com", "88888888")
    assert a.id == b.id
    assert len([x for x in store._by_id.values() if x.is_admin]) == 1


def test_regular_accounts_are_not_admin():
    store = AccountStore()
    u = store.create("learner@example.com", "password123")
    assert u.is_admin is False
    assert u.public()["is_admin"] is False
