"""Token-bucket rate limiter."""

from __future__ import annotations

import time

import pytest

from aoep_shared.ratelimit import (
    Decision, InMemoryTokenBucket, RateLimit, build_rate_limiter,
)


def test_allows_burst_up_to_capacity_then_denies():
    limiter = InMemoryTokenBucket(RateLimit(limit=5, window=1.0))
    decisions = [limiter.allow("user-a") for _ in range(7)]
    allowed = [d for d in decisions if d.allowed]
    denied = [d for d in decisions if not d.allowed]
    assert len(allowed) == 5
    assert len(denied) == 2
    assert all(d.retry_after_seconds > 0 for d in denied)


def test_buckets_are_per_key():
    limiter = InMemoryTokenBucket(RateLimit(limit=2, window=1.0))
    a1 = limiter.allow("user-a")
    a2 = limiter.allow("user-a")
    b1 = limiter.allow("user-b")
    a3 = limiter.allow("user-a")
    assert a1.allowed and a2.allowed
    assert b1.allowed
    assert not a3.allowed


def test_refill_after_waiting():
    limiter = InMemoryTokenBucket(RateLimit(limit=2, window=0.2))
    assert limiter.allow("u").allowed
    assert limiter.allow("u").allowed
    assert not limiter.allow("u").allowed
    time.sleep(0.25)
    assert limiter.allow("u").allowed


def test_decision_remaining_decreases_monotonically():
    limiter = InMemoryTokenBucket(RateLimit(limit=10, window=10))
    last = float("inf")
    for _ in range(8):
        d = limiter.allow("u")
        assert d.allowed
        assert d.remaining < last
        last = d.remaining


def test_factory_falls_back_to_memory_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    limiter = build_rate_limiter(RateLimit(3, 1.0))
    assert limiter.name == "memory"
    d: Decision = limiter.allow("k")
    assert d.allowed and d.limit == 3


def test_factory_force_memory(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://nope:6379/0")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    limiter = build_rate_limiter(RateLimit(3, 1.0))
    assert limiter.name == "memory"


def test_factory_redis_unreachable_falls_back(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")  # closed port
    monkeypatch.delenv("RATE_LIMIT_BACKEND", raising=False)
    limiter = build_rate_limiter(RateLimit(3, 1.0))
    assert limiter.name == "memory"


def test_zero_window_is_safe():
    rule = RateLimit(limit=5, window=0)
    assert rule.refill_per_sec == 5.0
    limiter = InMemoryTokenBucket(rule)
    assert limiter.allow("u").allowed


@pytest.mark.parametrize("cost", [1, 2, 3])
def test_cost_consumes_multiple_permits(cost: int):
    limiter = InMemoryTokenBucket(RateLimit(limit=6, window=10))
    used = 0
    while True:
        d = limiter.allow("u", cost=cost)
        if not d.allowed:
            break
        used += cost
    assert used == 6 - (6 % cost)
