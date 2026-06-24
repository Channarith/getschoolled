#!/usr/bin/env python3
"""Force admin + QA seed accounts into Redis (stdin: kubectl exec -i pod -- python3 -).

Works on identity images back to ~0.3.82 (no identity.persistence module).
After a successful Redis write, restart identity so every replica reloads:

  kubectl -n aoep rollout restart deployment/identity
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

for candidate in (
    Path(__file__).resolve().parents[1] / "services" / "identity" / "src",
    Path("/app/services/identity/src"),
):
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

REDIS_KEY = "aoep:identity:v1:state"


def _env_password(key: str, default: str) -> str:
    raw = os.environ.get(key, default)
    val = str(raw or "").strip()
    return val or default


def _redis_client():
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return None
    try:
        import redis  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        client = redis.from_url(url, decode_responses=True, socket_connect_timeout=5)
        client.ping()
        return client
    except Exception:
        return None


def _inline_dump_state(store) -> dict:
    accounts = {}
    for aid, acct in store._by_id.items():
        d = acct.model_dump(mode="json")
        d["points_ledger"] = [
            {"delta": e.delta, "reason": e.reason, "ref": e.ref, "ts": e.ts}
            for e in acct.points.entries
        ]
        accounts[aid] = d
    return {
        "accounts": accounts,
        "id_by_email": dict(store._id_by_email),
        "game_stats": getattr(store, "_game_stats", {}),
        "used_grant_nonces": sorted(getattr(store, "_used_grant_nonces", set())),
    }


def _inline_load_state(store, payload: dict) -> None:
    from aoep_shared.rewards import PointsEntry, PointsLedger
    from aoep_shared.schemas import PlanTier, Region
    from identity.store import Account, Enrollment, ProfileShareGrant, StudentProfile

    store._by_id.clear()
    store._id_by_email.clear()
    if hasattr(store, "_game_stats"):
        store._game_stats.clear()
    if hasattr(store, "_used_grant_nonces"):
        store._used_grant_nonces.clear()

    for aid, raw in payload.get("accounts", {}).items():
        row = dict(raw)
        ledger_raw = row.pop("points_ledger", [])
        redemptions = row.pop("redemptions", [])
        enrollments_raw = row.pop("enrollments", {})
        students_raw = row.pop("students", {})
        grants_raw = row.pop("profile_share_grants", {})
        acct = Account(
            id=row["id"],
            email=row["email"],
            display_name=row.get("display_name", ""),
            password_hash=row.get("password_hash", ""),
            tier=PlanTier(row.get("tier", PlanTier.FREE.value)),
            region=Region(row.get("region", Region.US.value)),
            is_admin=bool(row.get("is_admin", False)),
            created_at=float(row.get("created_at", 0)),
            last_login_at=row.get("last_login_at"),
            failed_logins=int(row.get("failed_logins", 0)),
            redemptions=list(redemptions),
        )
        acct.enrollments = {k: Enrollment.model_validate(v) for k, v in enrollments_raw.items()}
        acct.students = {k: StudentProfile.model_validate(v) for k, v in students_raw.items()}
        acct.profile_share_grants = {
            k: ProfileShareGrant.model_validate(v) for k, v in grants_raw.items()
        }
        acct.points = PointsLedger()
        for entry in ledger_raw:
            acct.points.entries.append(PointsEntry(**entry))
        store._by_id[aid] = acct
    store._id_by_email.update(payload.get("id_by_email", {}))
    if hasattr(store, "_game_stats"):
        store._game_stats.update(payload.get("game_stats", {}))
    if hasattr(store, "_used_grant_nonces"):
        store._used_grant_nonces.update(payload.get("used_grant_nonces", []))


def _load_store(store) -> bool:
    try:
        from identity.persistence import load_from_redis

        return load_from_redis(store)
    except ImportError:
        client = _redis_client()
        if client is None:
            return False
        try:
            raw = client.get(REDIS_KEY)
            if not raw:
                return False
            _inline_load_state(store, json.loads(raw))
            return True
        except Exception as exc:
            print("warn: redis load failed:", exc, file=sys.stderr)
            return False


def _save_store(store, *, attempts: int = 5) -> bool:
    if not os.environ.get("REDIS_URL", "").strip():
        return True
    try:
        from identity.persistence import save_to_redis_with_retry

        return save_to_redis_with_retry(store, attempts=attempts)
    except ImportError:
        for attempt in range(1, attempts + 1):
            client = _redis_client()
            if client is None:
                return False
            try:
                client.set(REDIS_KEY, json.dumps(_inline_dump_state(store)))
                return True
            except Exception as exc:
                print("warn: redis save failed:", exc, file=sys.stderr)
            if attempt < attempts:
                time.sleep(0.4)
        return False


def _force_passwords(store, emails: list[str], password: str) -> None:
    from aoep_shared.auth import hash_password

    h = hash_password(password)
    for email in emails:
        acct = store.by_email(email)
        if acct is not None:
            acct.password_hash = h


def _seed_account_compat(store, email: str, password: str, **kwargs) -> None:
    try:
        store.seed_account(email, password, **kwargs, force_password=True)
    except TypeError:
        store.seed_account(email, password, **{k: v for k, v in kwargs.items() if k != "force_password"})
        aliases = [email]
        u = kwargs.get("username")
        if u:
            aliases.append(u)
        _force_passwords(store, aliases, password)


def _bootstrap(store) -> dict:
    admin_email = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@salareen.com")
    admin_pw = _env_password("DEFAULT_ADMIN_PASSWORD", "88888888")
    admin_user = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
    qa_pw = _env_password("QA_ACCOUNTS_PASSWORD", "QaTest123")

    try:
        from identity.bootstrap import bootstrap_accounts

        return bootstrap_accounts(store)
    except ImportError:
        pass

    stats: dict = {"admin": False, "qa_count": 0}
    if os.environ.get("SEED_DEFAULT_ADMIN", "1").lower() in ("1", "true", "yes"):
        if hasattr(store, "seed_admin"):
            store.seed_admin(admin_email, admin_pw, username=admin_user)
        elif hasattr(store, "seed_account"):
            _seed_account_compat(
                store, admin_email, admin_pw,
                display_name="Administrator", username=admin_user, is_admin=True,
            )
        else:
            if store.by_email(admin_email) is None:
                store.create(admin_email, admin_pw, display_name="Administrator")
            acct = store.by_email(admin_email)
            if acct is not None:
                acct.is_admin = True
            _force_passwords(store, [admin_email, admin_user], admin_pw)
        stats["admin"] = True

    if os.environ.get("SEED_QA_ACCOUNTS", "1").lower() in ("1", "true", "yes"):
        try:
            from identity.qa_seed import seed_qa_accounts

            seeded = seed_qa_accounts(store, qa_pw)
            stats["qa_count"] = len(seeded)
        except ImportError:
            qa_emails = [
                "qa-learner@salareen.com",
                "qa-parent@salareen.com",
                "qa-pro@salareen.com",
            ]
            for email in qa_emails:
                if store.by_email(email) is None:
                    store.create(email, qa_pw, display_name=email.split("@")[0])
            _force_passwords(store, qa_emails + ["qa1", "qa2", "qa3"], qa_pw)
            stats["qa_count"] = 3

    return stats


def main() -> int:
    from identity.store import AccountStore

    store = AccountStore()
    loaded = _load_store(store)
    stats = _bootstrap(store)
    persisted = _save_store(store)
    qa_pw = _env_password("QA_ACCOUNTS_PASSWORD", "QaTest123")
    admin_pw = _env_password("DEFAULT_ADMIN_PASSWORD", "88888888")
    checks = {
        "admin@salareen.com": store.authenticate("admin@salareen.com", admin_pw) is not None,
        "qa-pro@salareen.com": store.authenticate("qa-pro@salareen.com", qa_pw) is not None,
        "qa3": store.authenticate("qa3", qa_pw) is not None,
    }
    out = {
        "loaded_from_redis": loaded,
        "stats": stats,
        "persisted": persisted,
        "accounts": len(store._by_id),
        "login_ok": checks,
        "next_step": "kubectl -n aoep rollout restart deployment/identity",
    }
    print(out)
    ok = all(checks.values()) and (persisted or not os.environ.get("REDIS_URL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
