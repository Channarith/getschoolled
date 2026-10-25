"""Durable, account-bound record of course purchases (web card/PayPal, Apple, Google).

Why this exists: the course studio's own disk (/tmp/course-studio) is erased on every restart, and the old pay store keyed a
purchase to a browser-chosen learner id. A purchase now belongs to a VERIFIED ACCOUNT and lives in Redis (the cluster's
StatefulSet, 40Gi volume), so buying on the web or on a phone unlocks the course everywhere and survives deploys.

Guarantees
  * idempotent: the same provider reference (Stripe session, PayPal order, Apple transaction, Google purchase token) is
    recorded once; a replay or duplicate webhook returns the same order;
  * one reference, one account: a reference already bound to another account/course is refused (PurchaseConflict);
  * refunds and revocations flip the order and remove the entitlement; they never re-activate on a replay;
  * every change appends to an audit list.
Cloud never falls back to memory silently: with PURCHASES_BACKEND=auto and no Redis in a non-local DEPLOY_MODE the store
raises PurchaseStoreUnavailable and callers answer 503 instead of granting or losing a paid course.

Config (names only): PURCHASES_BACKEND (auto|redis|memory|file), PURCHASES_FILE (file backend path), REDIS_URL/REDIS_PASSWORD.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

PREFIX = "aoep:purchases:v1:"
STATUS_PAID = "paid"
STATUS_REFUNDED = "refunded"
STATUS_REVOKED = "revoked"


class PurchaseConflict(Exception):
    """The provider reference is already bound to a different account or course."""


class PurchaseStoreUnavailable(RuntimeError):
    """No durable backend is available (cloud without Redis)."""


class _MemoryBackend:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}
        self._counters: dict[str, int] = {}

    def incr(self, key: str) -> int:
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + 1
            return self._counters[key]

    def hget(self, h: str, f: str) -> Optional[str]:
        with self._lock:
            return self._hashes.get(h, {}).get(f)

    def hset(self, h: str, f: str, v: str) -> None:
        with self._lock:
            self._hashes.setdefault(h, {})[f] = v

    def hsetnx(self, h: str, f: str, v: str) -> bool:
        with self._lock:
            row = self._hashes.setdefault(h, {})
            if f in row:
                return False
            row[f] = v
            return True

    def hdel(self, h: str, f: str) -> None:
        with self._lock:
            self._hashes.get(h, {}).pop(f, None)

    def hgetall(self, h: str) -> dict[str, str]:
        with self._lock:
            return dict(self._hashes.get(h, {}))

    def rpush(self, key: str, value: str) -> None:
        with self._lock:
            self._lists.setdefault(key, []).append(value)

    def lrange(self, key: str) -> list[str]:
        with self._lock:
            return list(self._lists.get(key, []))


class _FileBackend(_MemoryBackend):
    """Memory backend that snapshots to one JSON file (local development only)."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._hashes = {k: dict(v) for k, v in data.get("hashes", {}).items()}
                self._lists = {k: list(v) for k, v in data.get("lists", {}).items()}
                self._counters = {k: int(v) for k, v in data.get("counters", {}).items()}
            except (OSError, ValueError, TypeError):
                pass

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"hashes": self._hashes, "lists": self._lists, "counters": self._counters}), encoding="utf-8")
        os.replace(tmp, self._path)

    def incr(self, key: str) -> int:
        with self._lock:
            n = super().incr(key)
            self._flush()
            return n

    def hset(self, h: str, f: str, v: str) -> None:
        with self._lock:
            super().hset(h, f, v)
            self._flush()

    def hsetnx(self, h: str, f: str, v: str) -> bool:
        with self._lock:
            ok = super().hsetnx(h, f, v)
            if ok:
                self._flush()
            return ok

    def hdel(self, h: str, f: str) -> None:
        with self._lock:
            super().hdel(h, f)
            self._flush()

    def rpush(self, key: str, value: str) -> None:
        with self._lock:
            super().rpush(key, value)
            self._flush()


class _RedisBackend:
    def __init__(self, client: Any) -> None:
        self._r = client

    @staticmethod
    def _s(value: Any) -> Optional[str]:
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, (bytes, bytearray)) else str(value)

    def incr(self, key: str) -> int:
        return int(self._r.incr(key))

    def hget(self, h: str, f: str) -> Optional[str]:
        return self._s(self._r.hget(h, f))

    def hset(self, h: str, f: str, v: str) -> None:
        self._r.hset(h, f, v)

    def hsetnx(self, h: str, f: str, v: str) -> bool:
        return bool(self._r.hsetnx(h, f, v))

    def hdel(self, h: str, f: str) -> None:
        self._r.hdel(h, f)

    def hgetall(self, h: str) -> dict[str, str]:
        return {self._s(k) or "": self._s(v) or "" for k, v in (self._r.hgetall(h) or {}).items()}

    def rpush(self, key: str, value: str) -> None:
        self._r.rpush(key, value)

    def lrange(self, key: str) -> list[str]:
        return [self._s(x) or "" for x in self._r.lrange(key, 0, -1)]


def _json_load(raw: Optional[str]) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


class PurchaseStore:
    def __init__(self, backend: Any, *, clock: Callable[[], float] = time.time) -> None:
        self._b = backend
        self._now = clock

    # ---- keys
    @staticmethod
    def _ref_key(provider: str, provider_ref: str) -> str:
        return f"{provider.strip().lower()}:{provider_ref.strip()}"

    def _paid_hash(self, account: str) -> str:
        return f"{PREFIX}paid:{account}"

    def _acct_hash(self, account: str) -> str:
        return f"{PREFIX}acct:{account}"

    # ---- reads
    def get(self, order_id: str) -> Optional[dict[str, Any]]:
        return _json_load(self._b.hget(PREFIX + "orders", order_id))

    def get_by_ref(self, provider: str, provider_ref: str) -> Optional[dict[str, Any]]:
        order_id = self._b.hget(PREFIX + "refs", self._ref_key(provider, provider_ref))
        return self.get(order_id) if order_id else None

    def is_paid(self, account_id: str, course_id: str) -> bool:
        order_id = self._b.hget(self._paid_hash(account_id), course_id)
        order = self.get(order_id) if order_id else None
        return bool(order and order.get("status") == STATUS_PAID)

    def list_for_account(self, account_id: str) -> list[dict[str, Any]]:
        rows = [self.get(oid) for oid in self._b.hgetall(self._acct_hash(account_id))]
        return sorted((r for r in rows if r), key=lambda r: r.get("created_at", 0), reverse=True)

    def find_orders(self, predicate: Callable[[dict[str, Any]], bool]) -> list[dict[str, Any]]:
        """Orders matching a predicate (webhook lookups by processor ids; a linear scan is fine at this volume)."""
        rows = (_json_load(raw) for raw in self._b.hgetall(PREFIX + "orders").values())
        return [row for row in rows if row and predicate(row)]

    def audit_log(self) -> list[dict[str, Any]]:
        return [row for row in (_json_load(x) for x in self._b.lrange(PREFIX + "audit")) if row]

    # ---- writes
    def audit(self, event: str, **fields: Any) -> None:
        self._audit(event, **fields)

    def _audit(self, event: str, **fields: Any) -> None:
        self._b.rpush(PREFIX + "audit", json.dumps({"event": event, "at": self._now(), **fields}, sort_keys=True))

    def _save(self, order: dict[str, Any]) -> None:
        order["updated_at"] = self._now()
        self._b.hset(PREFIX + "orders", order["order_id"], json.dumps(order, sort_keys=True))

    def record_paid(
        self,
        *,
        account_id: str,
        course_id: str,
        amount_cents: int,
        provider: str,
        provider_ref: str,
        currency: str = "usd",
        tax_cents: int = 0,
        email: str = "",
        last4: str = "",
        meta: Optional[dict[str, Any]] = None,
    ) -> tuple[dict[str, Any], bool]:
        """Record a paid order once. Returns (order, created); a replay returns the existing order and created=False."""
        account_id, course_id = (account_id or "").strip(), (course_id or "").strip()
        provider, provider_ref = (provider or "").strip().lower(), (provider_ref or "").strip()
        if not (account_id and course_id and provider and provider_ref):
            raise ValueError("account, course, provider and provider reference are required")
        ref = self._ref_key(provider, provider_ref)
        order_id = f"SAL-{time.strftime('%Y', time.gmtime(self._now()))}-{self._b.incr(PREFIX + 'order_seq'):06d}"
        if not self._b.hsetnx(PREFIX + "refs", ref, order_id):
            existing_id = self._b.hget(PREFIX + "refs", ref) or ""
            existing = self.get(existing_id)
            if existing is None:
                order_id = existing_id  # a crash between the reference and the order: complete the record
            else:
                if existing["account_id"] != account_id or existing["course_id"] != course_id:
                    self._audit("conflict", ref=ref, account_id=account_id, course_id=course_id, owner=existing["account_id"])
                    raise PurchaseConflict("this purchase belongs to another account")
                return existing, False
        total = int(amount_cents) + int(tax_cents or 0)
        order = {
            "order_id": order_id, "account_id": account_id, "email": email, "course_id": course_id,
            "amount_cents": int(amount_cents), "tax_cents": int(tax_cents or 0), "total_cents": total,
            "currency": currency.lower(), "provider": provider, "provider_ref": provider_ref, "last4": last4[-4:],
            "status": STATUS_PAID, "created_at": self._now(), "meta": dict(meta or {}),
        }
        self._save(order)
        self._b.hset(self._paid_hash(account_id), course_id, order_id)
        self._b.hset(self._acct_hash(account_id), order_id, "1")
        self._audit("paid", order_id=order_id, account_id=account_id, course_id=course_id, provider=provider, ref=ref)
        return order, True

    def _end(self, order: Optional[dict[str, Any]], status: str, reason: str, by: str, amount_cents: Optional[int]) -> Optional[dict[str, Any]]:
        if order is None:
            return None
        if order["status"] != STATUS_PAID:
            return order  # already refunded or revoked: idempotent
        order["status"] = status
        order[status] = {"reason": reason, "by": by, "at": self._now(), "amount_cents": amount_cents if amount_cents is not None else order["total_cents"]}
        self._save(order)
        if self._b.hget(self._paid_hash(order["account_id"]), order["course_id"]) == order["order_id"]:
            self._b.hdel(self._paid_hash(order["account_id"]), order["course_id"])
        self._audit(status, order_id=order["order_id"], account_id=order["account_id"], reason=reason, by=by)
        return order

    def set_meta(self, order_id: str, **fields: Any) -> Optional[dict[str, Any]]:
        """Attach small facts to an order (receipt emailed, refund requested). Never changes the status."""
        order = self.get(order_id)
        if order is None:
            return None
        order.setdefault("meta", {}).update(fields)
        self._save(order)
        return order

    def mark_started(self, account_id: str, course_id: str) -> None:
        """Remember that this account opened the full class (the refund rules read it as 'progress unknown')."""
        self._b.hsetnx(PREFIX + "started", f"{account_id}:{course_id}", str(self._now()))

    def has_started(self, account_id: str, course_id: str) -> bool:
        return self._b.hget(PREFIX + "started", f"{account_id}:{course_id}") is not None

    def mark_refunded(self, order_id: str, *, reason: str, by: str, amount_cents: Optional[int] = None) -> Optional[dict[str, Any]]:
        return self._end(self.get(order_id), STATUS_REFUNDED, reason, by, amount_cents)

    def revoke_by_ref(self, provider: str, provider_ref: str, *, reason: str, by: str = "provider") -> Optional[dict[str, Any]]:
        return self._end(self.get_by_ref(provider, provider_ref), STATUS_REVOKED, reason, by, None)


_DEFAULT: Optional[PurchaseStore] = None


def _local_mode() -> bool:
    return os.environ.get("DEPLOY_MODE", "local").strip().lower() in {"local", "dev", "development", "test", "debug"}


def build_store(data_dir: Optional[Path] = None) -> PurchaseStore:
    """Pick the backend. Cloud without Redis raises instead of falling back to a store that forgets."""
    choice = os.environ.get("PURCHASES_BACKEND", "auto").strip().lower()
    if choice == "memory":
        return PurchaseStore(_MemoryBackend())
    if choice == "file":
        path = Path(os.environ.get("PURCHASES_FILE", "") or ((data_dir or Path("/tmp")) / "payments" / "purchases.json"))
        return PurchaseStore(_FileBackend(path))
    try:
        from aoep_shared.redis_url import open_redis, runtime_redis_url

        url = runtime_redis_url()
        if url:
            return PurchaseStore(_RedisBackend(open_redis(url, decode_responses=True)))
    except Exception as exc:  # noqa: BLE001 - any Redis failure is "no durable backend"
        if choice == "redis" or not _local_mode():
            raise PurchaseStoreUnavailable(f"purchases need Redis: {exc}") from exc
    if choice == "redis" or not _local_mode():
        raise PurchaseStoreUnavailable("purchases need Redis (REDIS_URL) in this deploy mode")
    path = (data_dir or Path("/tmp")) / "payments" / "purchases.json"
    return PurchaseStore(_FileBackend(path))


def default_store(data_dir: Optional[Path] = None) -> PurchaseStore:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = build_store(data_dir)
    return _DEFAULT


def reset_default_store(store: Optional[PurchaseStore] = None) -> None:
    """Tests only: install or clear the process-wide store."""
    global _DEFAULT
    _DEFAULT = store
