"""Default admin account: seedable, idempotent, login by email OR 'admin' alias."""

from __future__ import annotations

from identity.store import AccountStore


def test_seed_admin_login_by_email_and_username_alias():
    store = AccountStore()
    admin = store.seed_admin("admin@salareen.com", "88888888", username="admin")
    assert admin.is_admin is True
    assert admin.public()["is_admin"] is True


def test_seed_admin_skips_onboarding_wizard():
    """Admin is pre-onboarded so it never hits the new-user payment/setup flow."""
    store = AccountStore()
    admin = store.seed_admin("admin@salareen.com", "88888888", username="admin")
    assert admin.onboarding_completed_at is not None
    assert admin.billing_validated_at is not None

    # Idempotent re-seed (every startup) must NOT reset the timestamps.
    ts = admin.onboarding_completed_at
    again = store.seed_admin("admin@salareen.com", "88888888", username="admin")
    assert again.onboarding_completed_at == ts


def test_seed_admin_defaults_to_vip_billing():
    """Admin operator accounts get the full ad-free VIP experience by default."""
    store = AccountStore()
    admin = store.seed_admin("admin@salareen.com", "88888888", username="admin")
    assert admin.tier.value == "premium"
    assert admin.membership_class == "vip"
    assert admin.public()["membership_class"] == "vip"
    # Re-seeding (every startup) keeps the admin on VIP, even if downgraded.
    admin.tier = admin.tier.__class__("free")
    admin.membership_class = "standard"
    again = store.seed_admin("admin@salareen.com", "88888888", username="admin")
    assert again.membership_class == "vip"

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


def test_seed_admin_resyncs_password_after_manual_signup():
    """Local dev: signing up as admin@ before seed runs must not brick login."""
    store = AccountStore()
    manual = store.create("admin@salareen.com", "wrongpass")
    assert manual.is_admin is False
    admin = store.seed_admin("admin@salareen.com", "88888888", username="admin")
    assert admin.id == manual.id
    assert admin.is_admin is True
    assert store.authenticate("admin@salareen.com", "88888888") is not None
    assert store.authenticate("admin", "88888888") is not None
    assert store.authenticate("admin@salareen.com", "wrongpass") is None
