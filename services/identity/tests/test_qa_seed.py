"""QA test accounts: seedable, idempotent, login by email OR username alias."""

from __future__ import annotations

from aoep_shared.schemas import PlanTier

from identity.qa_seed import QA_PERSONAS, seed_qa_accounts
from identity.store import AccountStore


def test_seed_qa_accounts_login_by_email_and_username():
    store = AccountStore()
    seeded = seed_qa_accounts(store, "QaTest123")
    assert len(seeded) == 3
    assert all(not a.is_admin for a in seeded)

    learner, parent, pro = seeded
    assert learner.email == "qa-learner@salareen.com"
    assert parent.email == "qa-parent@salareen.com"
    assert pro.email == "qa-pro@salareen.com"
    assert pro.tier == PlanTier.PRO

    assert store.authenticate("qa-learner@salareen.com", "QaTest123") is not None
    assert store.authenticate("qa1", "QaTest123") is not None
    assert store.authenticate("qa-parent@salareen.com", "QaTest123") is not None
    assert store.authenticate("qa2", "QaTest123") is not None
    assert store.authenticate("qa-pro@salareen.com", "QaTest123") is not None
    assert store.authenticate("qa3", "QaTest123") is not None
    assert store.authenticate("qa1", "wrong") is None


def test_seed_qa_parent_has_child_profile():
    store = AccountStore()
    seeded = seed_qa_accounts(store, "QaTest123")
    parent = next(a for a in seeded if a.email == "qa-parent@salareen.com")
    kids = store.list_students(parent.id)
    assert len(kids) == 1
    assert kids[0].display_name == "QA Kid"
    assert kids[0].age_band == "child"


def test_seed_qa_accounts_is_idempotent():
    store = AccountStore()
    first = seed_qa_accounts(store, "QaTest123")
    second = seed_qa_accounts(store, "QaTest123")
    assert [a.id for a in first] == [a.id for a in second]
    parent = next(a for a in second if a.email == "qa-parent@salareen.com")
    assert len(store.list_students(parent.id)) == 1
