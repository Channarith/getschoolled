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
from typing import TYPE_CHECKING, Optional

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

    from aoep_shared.passkeys import PasskeyCredential

    from .store import Account, BillingAddress, Enrollment, LoginEvent, ProfileShareGrant, StudentProfile

    ledger_raw = raw.pop("points_ledger", [])
    redemptions = raw.pop("redemptions", [])
    enrollments_raw = raw.pop("enrollments", {})
    students_raw = raw.pop("students", {})
    grants_raw = raw.pop("profile_share_grants", {})
    login_events_raw = raw.pop("login_events", [])
    passkeys_raw = raw.pop("passkeys", [])
    billing_raw = raw.pop("billing_address", None)

    acct = Account(
        id=raw["id"],
        email=raw["email"],
        display_name=raw.get("display_name", ""),
        password_hash=raw.get("password_hash", ""),
        tier=PlanTier(raw.get("tier", PlanTier.FREE.value)),
        region=Region(raw.get("region", Region.US.value)),
        membership_class=raw.get("membership_class", "standard"),
        is_admin=bool(raw.get("is_admin", False)),
        created_at=float(raw.get("created_at", 0)),
        subscription_started_at=raw.get("subscription_started_at"),
        billing_anchor_day=raw.get("billing_anchor_day"),
        next_billing_at=raw.get("next_billing_at"),
        billing_amount_usd=raw.get("billing_amount_usd"),
        last_login_at=raw.get("last_login_at"),
        failed_logins=int(raw.get("failed_logins", 0)),
        login_count=int(raw.get("login_count", 0)),
        locked_until=raw.get("locked_until"),
        totp_secret=raw.get("totp_secret", ""),
        totp_enabled=bool(raw.get("totp_enabled", False)),
        oauth_subject=raw.get("oauth_subject", ""),
        onboarding_completed_at=raw.get("onboarding_completed_at"),
        card_last4=raw.get("card_last4", ""),
        billing_validated_at=raw.get("billing_validated_at"),
        redemptions=list(redemptions),
    )
    if billing_raw:
        acct.billing_address = BillingAddress.model_validate(billing_raw)
    acct.enrollments = {
        k: Enrollment.model_validate(v) for k, v in enrollments_raw.items()
    }
    acct.students = {
        k: StudentProfile.model_validate(v) for k, v in students_raw.items()
    }
    acct.profile_share_grants = {
        k: ProfileShareGrant.model_validate(v) for k, v in grants_raw.items()
    }
    acct.login_events = [LoginEvent.model_validate(e) for e in login_events_raw]
    acct.passkeys = [PasskeyCredential.model_validate(e) for e in passkeys_raw]
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


def load_from_redis_with_retry(store: "AccountStore", *, attempts: int = 5, delay_s: float = 0.4) -> bool:
    """Load with short retries so pods that start before Redis is ready still hydrate."""
    if not redis_configured():
        return False
    for attempt in range(1, attempts + 1):
        if load_from_redis(store):
            return True
        if attempt < attempts:
            time.sleep(delay_s)
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


GAME_ROUND_TTL_S = 4 * 3600


def save_game_round(round_json: str, game_id: str) -> None:
    """Persist an arcade round so submit works across identity replicas."""
    client = _redis_client()
    if client is None:
        return
    try:
        client.setex(f"aoep:identity:game:{game_id}", GAME_ROUND_TTL_S, round_json)
    except Exception as exc:
        logger.warning("failed to persist game round %s (%s)", game_id, exc)


def load_game_round(game_id: str) -> Optional[str]:
    client = _redis_client()
    if client is None:
        return None
    try:
        return client.get(f"aoep:identity:game:{game_id}")
    except Exception as exc:
        logger.warning("failed to load game round %s (%s)", game_id, exc)
        return None


def persist_hook(store: "AccountStore") -> None:
    """Call after any AccountStore mutation when Redis is configured."""
    save_to_redis(store)
