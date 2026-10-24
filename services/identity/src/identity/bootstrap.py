"""Startup seeding for default admin + QA personas (env-gated)."""

from __future__ import annotations

import os
from typing import Dict

from .store import AccountStore


def env_seed_password(key: str, default: str) -> str:
    """Read a seed password from env; treat blank as the documented default."""
    raw = os.environ.get(key, default)
    if raw is None:
        return default
    val = str(raw).strip()
    return val or default


_PUBLIC_WEAK_VALUES = {"88888888", "dev-admin-secret", "QaTest123", "password", "admin", "changeme"}


def weak_operator_secrets() -> list:
    """Names of operator credentials that are unset, short, or a value published in the repo."""
    weak = []
    for name in ("ADMIN_SECRET", "DEFAULT_ADMIN_PASSWORD"):
        value = (os.environ.get(name) or "").strip()
        if not value or value in _PUBLIC_WEAK_VALUES or len(value) < 12 or len(set(value)) == 1:
            weak.append(name)
    return weak


def _truthy(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


def bootstrap_accounts(store: AccountStore) -> Dict[str, object]:
    """Idempotently seed admin + QA accounts; force-sync known passwords."""
    stats: Dict[str, object] = {"admin": False, "qa_count": 0}

    if _truthy("SEED_DEFAULT_ADMIN", "1"):
        store.seed_admin(
            os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@salareen.com"),
            env_seed_password("DEFAULT_ADMIN_PASSWORD", "88888888"),
            username=os.environ.get("DEFAULT_ADMIN_USERNAME", "admin"),
        )
        stats["admin"] = True

    if _truthy("SEED_QA_ACCOUNTS", "1"):
        from .qa_seed import seed_qa_accounts

        seeded = seed_qa_accounts(
            store,
            env_seed_password("QA_ACCOUNTS_PASSWORD", "QaTest123"),
        )
        stats["qa_count"] = len(seeded)

    return stats
