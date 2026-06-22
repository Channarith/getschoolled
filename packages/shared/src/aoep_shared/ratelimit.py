"""Distributed-friendly rate limiter for the AOEP HTTP services.

Two backends, same interface:

* InMemoryTokenBucket - a per-process token bucket for local dev / single
  replica. Zero dependencies, monotonically-clocked, thread-safe.
* RedisTokenBucket - same algorithm executed on Redis via a Lua script so
  it is consistent across N service replicas. Activates when ``REDIS_URL``
  is set and ``redis`` is importable (optional dep). Falls back to the
  in-memory bucket if Redis is unreachable so callers always get an
  answer (open-on-fail is the right default at the platform edge).

Why token bucket instead of fixed/leaky window? It allows short bursts up
to the bucket capacity while enforcing a long-run average rate, which is
what real users want (their first 5 requests shouldn't queue behind a
strict 1-rps drip). Redis-side limiter math runs in a single Lua call so
the worst-case extra latency added per request is the round-trip to
Redis - typically <1 ms in-cluster.

Public surface:
  * :class:`RateLimit` - dataclass with ``limit`` (capacity, integer
    permits) and ``window`` (refill window, seconds). The bucket refills
    at ``limit / window`` permits per second.
  * :class:`RateLimiter` - protocol exposing
    ``allow(key, cost=1) -> Decision``.
  * :func:`build_rate_limiter` - factory that picks the right backend
    based on env (``REDIS_URL`` / ``RATE_LIMIT_BACKEND``).
  * :class:`Decision` - allow/deny result + ``retry_after_seconds`` and
    ``remaining`` so the FastAPI middleware can set
    ``Retry-After`` + ``X-RateLimit-Remaining`` headers.

The FastAPI middleware lives in
:mod:`aoep_shared.service_extras` (see ``mount_rate_limit``).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional, Protocol


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimit:
    """Capacity + refill window for a token bucket.

    Examples:
      RateLimit(limit=60, window=60)   -> ~1 rps long-run, burst of 60
      RateLimit(limit=10, window=1)    -> 10 rps, burst of 10
    """

    limit: int
    window: float = 60.0

    @property
    def refill_per_sec(self) -> float:
        if self.window <= 0:
            return float(self.limit)
        return self.limit / self.window


@dataclass
class Decision:
    allowed: bool
    remaining: float
    retry_after_seconds: float
    limit: int


class RateLimiter(Protocol):
    name: str

    def allow(self, key: str, *, cost: int = 1, rule: Optional[RateLimit] = None) -> Decision:
        ...


# --------------------------------------------------------------------------- #
# In-memory backend
# --------------------------------------------------------------------------- #
class InMemoryTokenBucket:
    """Per-process token bucket. Thread-safe via a single lock.

    Memory footprint is one float-pair per active key. Idle keys aren't
    purged eagerly because a per-key clock skew of seconds is harmless;
    the worst case is a gradual O(unique_keys_per_TTL) growth which the
    callsite controls (we key by client-IP / user-id, not by request URL).
    """

    name = "memory"

    def __init__(self, default: RateLimit):
        self._default = default
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, *, cost: int = 1, rule: Optional[RateLimit] = None) -> Decision:
        rule = rule or self._default
        capacity = float(rule.limit)
        refill = rule.refill_per_sec
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (capacity, now))
            tokens = min(capacity, tokens + (now - last) * refill)
            if tokens >= cost:
                tokens -= cost
                self._buckets[key] = (tokens, now)
                return Decision(True, tokens, 0.0, rule.limit)
            self._buckets[key] = (tokens, now)
            need = cost - tokens
            retry = need / refill if refill > 0 else float("inf")
            return Decision(False, max(0.0, tokens), retry, rule.limit)

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


# --------------------------------------------------------------------------- #
# Redis backend (optional)
# --------------------------------------------------------------------------- #
# Atomic token-bucket in Lua. Keys: bucket-state hash. Args: capacity,
# refill_per_sec, cost, now_seconds. Returns: [allowed, remaining,
# retry_after_seconds]. Single round-trip, no race between read+write.
_LUA_TOKEN_BUCKET = r"""
local key       = KEYS[1]
local capacity  = tonumber(ARGV[1])
local refill    = tonumber(ARGV[2])
local cost      = tonumber(ARGV[3])
local now       = tonumber(ARGV[4])
local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts     = tonumber(data[2])
if tokens == nil then tokens = capacity end
if ts == nil then ts = now end
local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * refill)
local allowed = 0
local retry = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  if refill > 0 then
    retry = (cost - tokens) / refill
  else
    retry = -1
  end
end
redis.call('HSET', key, 'tokens', tokens, 'ts', now)
-- TTL the bucket so an inactive key can't grow memory forever.
local ttl = math.max(60, math.ceil(capacity / math.max(refill, 0.01)) * 2)
redis.call('EXPIRE', key, ttl)
return {allowed, tostring(tokens), tostring(retry)}
"""


class RedisTokenBucket:
    """Redis-backed token bucket; consistent across replicas.

    Failure mode: if Redis is unreachable for any reason we fall back to
    the in-memory limiter so the platform stays available. This is
    intentional - rate-limit infrastructure should never take down the
    public API.
    """

    name = "redis"

    def __init__(self, redis_client, default: RateLimit, *, prefix: str = "aoep:rl:") -> None:
        self._r = redis_client
        self._default = default
        self._prefix = prefix
        self._fallback = InMemoryTokenBucket(default)
        try:
            self._sha = self._r.script_load(_LUA_TOKEN_BUCKET)
        except Exception:
            self._sha = None

    def allow(self, key: str, *, cost: int = 1, rule: Optional[RateLimit] = None) -> Decision:
        rule = rule or self._default
        full_key = f"{self._prefix}{key}"
        try:
            res = self._r.evalsha(
                self._sha or self._r.script_load(_LUA_TOKEN_BUCKET),
                1, full_key,
                rule.limit, rule.refill_per_sec, cost, time.time(),
            )
            allowed_raw, tokens_raw, retry_raw = res
            allowed = int(allowed_raw) == 1
            return Decision(
                allowed=allowed,
                remaining=float(tokens_raw),
                retry_after_seconds=max(0.0, float(retry_raw)),
                limit=rule.limit,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("redis ratelimit failed (%s); falling back to in-memory", e)
            return self._fallback.allow(key, cost=cost, rule=rule)


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def build_rate_limiter(default: RateLimit) -> RateLimiter:
    """Pick the best backend for the current env.

    Priority:
      1. ``RATE_LIMIT_BACKEND=memory`` -> always in-memory (good for tests).
      2. ``REDIS_URL`` set + ``redis`` package installed -> Redis bucket.
      3. otherwise -> in-memory.
    """
    backend = (os.environ.get("RATE_LIMIT_BACKEND") or "").lower()
    if backend == "memory":
        return InMemoryTokenBucket(default)
    redis_url = os.environ.get("REDIS_URL")
    if redis_url and backend != "memory":
        try:
            import redis  # type: ignore[import-not-found]

            client = redis.from_url(redis_url, decode_responses=True,
                                    socket_connect_timeout=0.5,
                                    socket_timeout=0.5)
            client.ping()
            return RedisTokenBucket(client, default)
        except Exception as e:  # noqa: BLE001
            logger.warning("redis unavailable for rate limiting (%s); using memory", e)
    return InMemoryTokenBucket(default)
