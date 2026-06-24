#!/usr/bin/env python3
"""Force admin + QA seed accounts into Redis (run inside an identity pod).

Usage:
  ./scripts/k8s_reseed_accounts.sh

Works on older identity images (falls back when identity.bootstrap is absent).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

for candidate in (
    Path(__file__).resolve().parents[1] / "services" / "identity" / "src",
    Path("/app/services/identity/src"),
):
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def _env_password(key: str, default: str) -> str:
    raw = os.environ.get(key, default)
    val = str(raw or "").strip()
    return val or default


def _bootstrap(store) -> dict:
    try:
        from identity.bootstrap import bootstrap_accounts

        return bootstrap_accounts(store)
    except ImportError:
        from identity.qa_seed import seed_qa_accounts

        store.seed_admin(
            os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@salareen.com"),
            _env_password("DEFAULT_ADMIN_PASSWORD", "88888888"),
            username=os.environ.get("DEFAULT_ADMIN_USERNAME", "admin"),
        )
        seeded = seed_qa_accounts(store, _env_password("QA_ACCOUNTS_PASSWORD", "QaTest123"))
        return {"admin": True, "qa_count": len(seeded)}


def main() -> int:
    from identity.persistence import load_from_redis, save_to_redis_with_retry
    from identity.store import AccountStore

    store = AccountStore()
    load_from_redis(store)
    stats = _bootstrap(store)
    persisted = save_to_redis_with_retry(store)
    qa_pw = _env_password("QA_ACCOUNTS_PASSWORD", "QaTest123")
    admin_pw = _env_password("DEFAULT_ADMIN_PASSWORD", "88888888")
    checks = {
        "admin@salareen.com": store.authenticate("admin@salareen.com", admin_pw) is not None,
        "qa-pro@salareen.com": store.authenticate("qa-pro@salareen.com", qa_pw) is not None,
        "qa3": store.authenticate("qa3", qa_pw) is not None,
    }
    out = {"stats": stats, "persisted": persisted, "accounts": len(store._by_id), "login_ok": checks}
    print(out)
    return 0 if persisted and all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
