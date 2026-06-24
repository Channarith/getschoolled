"""Optional Redis snapshot persistence for the in-memory AccountStore.

Identity keeps accounts in RAM for speed, but with multiple replicas a login on
pod A and the next request on pod B yields 401 (account not found). When
REDIS_URL is set we snapshot the full store after every mutation so every pod
shares the same accounts, rewards ledgers, and student profiles.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .store import Account, AccountStore

logger = logging.getLogger(__name__)

REDIS_KEY = "aoep:identity:v1:state"


def redis_configured() -> bool:
    return bool(os.environ.get("REDIS_URL", "").strip())


def _redis_client():
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return None
    try:
        import redis  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("REDIS_URL set but redis package not installed; identity stays in-memory")
        return None
    try:
        client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis unavailable for identity persistence (%s); in-memory only", exc)
        return None


def _serialize_account(acct: "Account") -> dict:
    d = acct.model_dump(mode="json")
    d["points_ledger"] = [
        {"delta": e.delta, "reason": e.reason, "ref": e.ref, "ts": e.ts}
        for e in acct.points.entries
    ]
    return d


def _deserialize_account(raw: dict) -> "Account":
    from aoep_shared.rewards import PointsEntry, PointsLedger
    from aoep_shared.schemas import PlanTier, Region

    from .store import Account, ClassContext, Enrollment, ProfileShareGrant, StudentProfile

    ledger_raw = raw.pop("points_ledger", [])
    redemptions = raw.pop("redemptions", [])
    enrollments_raw = raw.pop("enrollments", {})
    students_raw = raw.pop("students", {})
    grants_raw = raw.pop("profile_share_grants", {})

    acct = Account(
        id=raw["id"],
        email=raw["email"],
        display_name=raw.get("display_name", ""),
        password_hash=raw.get("password_hash", ""),
        tier=PlanTier(raw.get("tier", PlanTier.FREE.value)),
        region=Region(raw.get("region", Region.US.value)),
        is_admin=bool(raw.get("is_admin", False)),
        created_at=float(raw.get("created_at", 0)),
        last_login_at=raw.get("last_login_at"),
        failed_logins=int(raw.get("failed_logins", 0)),
        redemptions=list(redemptions),
    )
    acct.enrollments = {
        k: Enrollment.model_validate(v) for k, v in enrollments_raw.items()
    }
    acct.students = {
        k: StudentProfile.model_validate(v) for k, v in students_raw.items()
    }
    acct.profile_share_grants = {
        k: ProfileShareGrant.model_validate(v) for k, v in grants_raw.items()
    }
    acct.points = PointsLedger()
    for entry in ledger_raw:
        acct.points.entries.append(PointsEntry(**entry))
    return acct


def dump_state(store: "AccountStore") -> dict:
    return {
        "accounts": {aid: _serialize_account(a) for aid, a in store._by_id.items()},
        "id_by_email": dict(store._id_by_email),
        "game_stats": store._game_stats,
        "used_grant_nonces": sorted(store._used_grant_nonces),
    }


def load_state(store: "AccountStore", payload: dict) -> None:
    store._by_id.clear()
    store._id_by_email.clear()
    store._game_stats.clear()
    store._used_grant_nonces.clear()

    for aid, raw in payload.get("accounts", {}).items():
        acct = _deserialize_account(dict(raw))
        store._by_id[aid] = acct
    store._id_by_email.update(payload.get("id_by_email", {}))
    store._game_stats.update(payload.get("game_stats", {}))
    store._used_grant_nonces.update(payload.get("used_grant_nonces", []))


def load_from_redis(store: "AccountStore") -> bool:
    client = _redis_client()
    if client is None:
        return False
    try:
        raw = client.get(REDIS_KEY)
        if not raw:
            return False
        load_state(store, json.loads(raw))
        logger.info("identity store loaded from Redis (%d accounts)", len(store._by_id))
        return True
    except Exception as exc:
        logger.warning("failed to load identity store from Redis (%s)", exc)
        return False


def save_to_redis(store: "AccountStore") -> bool:
    client = _redis_client()
    if client is None:
        return not redis_configured()
    try:
        client.set(REDIS_KEY, json.dumps(dump_state(store)))
        return True
    except Exception as exc:
        logger.warning("failed to persist identity store to Redis (%s)", exc)
        return False


def save_to_redis_with_retry(store: "AccountStore", *, attempts: int = 5, delay_s: float = 0.4) -> bool:
    """Persist with short retries so multi-replica pods share seeded QA/admin accounts."""
    if not redis_configured():
        return True
    for attempt in range(1, attempts + 1):
        if save_to_redis(store):
            return True
        if attempt < attempts:
            time.sleep(delay_s)
    return False


def persist_hook(store: "AccountStore") -> None:
    """Call after any AccountStore mutation when Redis is configured."""
    save_to_redis(store)
