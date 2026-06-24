"""Startup bootstrap for admin + QA seed accounts."""

from __future__ import annotations

import os

from identity.bootstrap import bootstrap_accounts, env_seed_password
from identity.store import AccountStore


def test_env_seed_password_blank_uses_default():
    os.environ["QA_ACCOUNTS_PASSWORD"] = "   "
    try:
        assert env_seed_password("QA_ACCOUNTS_PASSWORD", "QaTest123") == "QaTest123"
    finally:
        os.environ.pop("QA_ACCOUNTS_PASSWORD", None)


def test_bootstrap_seeds_qa_and_admin():
    os.environ["SEED_DEFAULT_ADMIN"] = "1"
    os.environ["SEED_QA_ACCOUNTS"] = "1"
    os.environ["QA_ACCOUNTS_PASSWORD"] = "QaTest123"
    store = AccountStore()
    stats = bootstrap_accounts(store)
    assert stats["admin"] is True
    assert stats["qa_count"] == 3
    assert store.authenticate("qa-pro@salareen.com", "QaTest123") is not None
    assert store.authenticate("admin@salareen.com", "88888888") is not None
