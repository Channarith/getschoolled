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
FREE_CLAIM_KEY = "aoep:identity:v1:free_plan_claims"

# Atomic seat reservation. HSETNX backfill and the cap check run in one script
# so two replicas cannot both admit the 100th person. Keep this in lockstep
# with apply_free_claim() below.
_RESERVE_FREE_CLAIM_LUA = """
-- aoep-free-claim-reserve
local key = KEYS[1]
local account_id = ARGV[1]
local limit = tonumber(ARGV[2])
local record = ARGV[3] .. '|' .. ARGV[4]
local n = tonumber(ARGV[5]) or 0
local idx = 6
for i = 1, n do
  local aid = ARGV[idx]
  local rec = ARGV[idx + 1]
  if aid and aid ~= '' and rec and rec ~= '' and redis.call('HEXISTS', key, aid) == 0 then
    redis.call('HSETNX', key, aid, rec)
  end
  idx = idx + 2
end
local existing = redis.call('HGET', key, account_id)
if existing then
  return {'existing', existing}
end
local count = redis.call('HLEN', key)
if count >= limit then
  return {'full', ''}
end
redis.call('HSET', key, account_id, record)
return {'new', record}
"""

_COUNT_FREE_CLAIMS_LUA = """
-- aoep-free-claim-count
local key = KEYS[1]
local n = tonumber(ARGV[1]) or 0
local idx = 2
for i = 1, n do
  local aid = ARGV[idx]
  local rec = ARGV[idx + 1]
  if aid and aid ~= '' and rec and rec ~= '' and redis.call('HEXISTS', key, aid) == 0 then
    redis.call('HSETNX', key, aid, rec)
  end
  idx = idx + 2
end
return redis.call('HLEN', key)
"""


class FreeClaimUnavailable(RuntimeError):
    """The seat cap could not be reserved safely, so the claim is refused."""


def _optional_timestamp(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _millis(ts: float) -> str:
    return str(int(round(float(ts) * 1000.0)))


def format_claim_record(claimed_at: float, expires_at: float) -> str:
    return f"{_millis(claimed_at)}|{_millis(expires_at)}"


def parse_claim_record(record: str) -> tuple[float, float]:
    claimed_ms, expires_ms = str(record).split("|", 1)
    return int(claimed_ms) / 1000.0, int(expires_ms) / 1000.0


def _text(value) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return "" if value is None else str(value)


def apply_free_claim(
    claims: dict[str, str],
    account_id: str,
    limit: int,
    claimed_ms: str,
    expires_ms: str,
    backfill: list[tuple[str, str]],
) -> tuple[str, str]:
    """Same rules as _RESERVE_FREE_CLAIM_LUA, for the in-memory fallback and tests."""
    for aid, rec in backfill:
        if aid and rec and aid not in claims:
            claims[aid] = rec
    existing = claims.get(account_id)
    if existing:
        return "existing", existing
    if len(claims) >= int(limit):
        return "full", ""
    record = f"{claimed_ms}|{expires_ms}"
    claims[account_id] = record
    return "new", record


def _known_claim_args(known: list[tuple[str, str]]) -> list[str]:
    args: list[str] = [str(len(known))]
    for aid, rec in known:
        args.append(aid)
        args.append(rec)
    return args


# A per-process lock is a correct seat cap only while one process owns every
# claim. Cloud, production, and staging run more than one identity replica.
_LOCAL_CLAIM_MODES = frozenset({
    "local",
    "dev",
    "development",
    "test",
    "debug",
})


def free_claim_memory_fallback_allowed() -> bool:
    """Whether an unset REDIS_URL may fall back to the in-process seat lock.

    Unset DEPLOY_MODE matches the rest of identity and means local. Any other
    mode, including cloud, production, prod, and staging, must fail closed.
    """
    mode = os.environ.get("DEPLOY_MODE", "local").strip().lower()
    return mode in _LOCAL_CLAIM_MODES


def reserve_free_claim(
    account_id: str,
    claimed_at: float,
    expires_at: float,
    limit: int,
    known: list[tuple[str, str]],
) -> tuple[str, str]:
    """Reserve one durable seat.

    Returns ("local", "") only in local/dev/test when Redis is not configured —
    the caller then uses its in-memory lock. Returns ("new"|"existing"|"full",
    record). Raises FreeClaimUnavailable when a non-local deploy has no
    REDIS_URL, or when Redis is configured but the reservation cannot be
    completed, so a replica never admits a seat it could not record.
    """
    if not redis_configured():
        if free_claim_memory_fallback_allowed():
            return "local", ""
        mode = os.environ.get("DEPLOY_MODE", "").strip().lower() or "unset"
        logger.error(
            "free-plan claim refused: REDIS_URL is unset and DEPLOY_MODE=%s "
            "cannot use the in-process seat lock",
            mode,
        )
        raise FreeClaimUnavailable("The free plan cannot be claimed right now.")
    client = _redis_client()
    if client is None:
        raise FreeClaimUnavailable("The free plan cannot be claimed right now.")
    claimed_ms = _millis(claimed_at)
    expires_ms = _millis(expires_at)
    backfill = [(aid, rec) for aid, rec in known if aid and aid != account_id]
    try:
        raw = client.eval(
            _RESERVE_FREE_CLAIM_LUA,
            1,
            FREE_CLAIM_KEY,
            account_id,
            str(int(limit)),
            claimed_ms,
            expires_ms,
            *_known_claim_args(backfill),
        )
    except FreeClaimUnavailable:
        raise
    except Exception as exc:
        logger.warning("free-plan seat reservation failed (%s)", exc)
        raise FreeClaimUnavailable("The free plan cannot be claimed right now.") from exc
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        raise FreeClaimUnavailable("The free plan cannot be claimed right now.")
    status = _text(raw[0])
    record = _text(raw[1])
    if status not in {"new", "existing", "full"}:
        raise FreeClaimUnavailable("The free plan cannot be claimed right now.")
    return status, record


def durable_free_claim_count(known: list[tuple[str, str]]) -> Optional[int]:
    """Union of the Redis seat hash and this replica's known claims.

    None means Redis is not configured or could not be read; callers then use
    the in-memory count. A failed read does not grant seats.
    """
    if not redis_configured():
        return None
    client = _redis_client()
    if client is None:
        return None
    try:
        raw = client.eval(
            _COUNT_FREE_CLAIMS_LUA,
            1,
            FREE_CLAIM_KEY,
            *_known_claim_args(known),
        )
    except Exception as exc:
        logger.warning("free-plan seat count failed (%s)", exc)
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def hydrate_free_claims(store: "AccountStore") -> None:
    """Restore claim timestamps lost from a snapshot, then index local claims.

    The Redis hash is the cross-replica source of truth for the 100-seat cap.
    Loading a snapshot must not forget seats that the hash already recorded,
    and seats that exist only on the snapshot must be indexed before new claims.
    """
    if not redis_configured():
        return
    client = _redis_client()
    if client is None:
        return
    try:
        remote = client.hgetall(FREE_CLAIM_KEY) or {}
    except Exception as exc:
        logger.warning("free-plan claim hydrate failed (%s)", exc)
        return
    for aid, record in remote.items():
        acct = store._by_id.get(_text(aid))
        if acct is None or acct.free_plan_claimed_at:
            continue
        try:
            claimed, expires = parse_claim_record(_text(record))
        except (TypeError, ValueError):
            continue
        acct.free_plan_claimed_at = claimed
        acct.free_plan_expires_at = expires
    known: list[tuple[str, str]] = []
    for acct in store._by_id.values():
        if acct.free_plan_claimed_at and acct.free_plan_expires_at:
            known.append((
                acct.id,
                format_claim_record(acct.free_plan_claimed_at, acct.free_plan_expires_at),
            ))
    if known:
        durable_free_claim_count(known)


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
        preferred_language=raw.get("preferred_language", ""),
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
        free_plan_claimed_at=_optional_timestamp(raw.get("free_plan_claimed_at")),
        free_plan_expires_at=_optional_timestamp(raw.get("free_plan_expires_at")),
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
        "submitted_game_ids": {aid: list(gids) for aid, gids in store._submitted_game_ids.items()},
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
    store._submitted_game_ids = {
        aid: set(gids)
        for aid, gids in payload.get("submitted_game_ids", {}).items()
    }


def load_from_redis(store: "AccountStore") -> bool:
    client = _redis_client()
    if client is None:
        return False
    try:
        raw = client.get(REDIS_KEY)
        if not raw:
            return False
        load_state(store, json.loads(raw))
        hydrate_free_claims(store)
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
    # WARNING: last-writer-wins — concurrent replicas can overwrite each other's
    # state. Atomic updates would require Lua scripts with optimistic locking (WATCH/MULTI/EXEC).
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
