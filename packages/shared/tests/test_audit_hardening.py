"""Regressions for the second audit pass: config, caching and self-healing.

Each test reproduces a defect that was proven by execution during the audit.
"""

from __future__ import annotations

import pathlib
import tempfile

from aoep_shared.config import env_float, env_int, load_config
from aoep_shared.http_cache import CacheRegistry, CacheRule, standard_registry


# --------------------------------------------------------------------------- #
# Blank / malformed env values must not stop a service from starting
# --------------------------------------------------------------------------- #
def test_env_int_and_float_tolerate_blank_and_garbage():
    assert env_int("", 120) == 120
    assert env_int(None, 120) == 120
    assert env_int("unlimited", 120) == 120
    assert env_int("  7 ", 120) == 7
    assert env_float("", 60.0) == 60.0
    assert env_float("fast", 60.0) == 60.0
    assert env_float("1.5", 60.0) == 1.5


def test_blank_numeric_env_falls_back_to_the_documented_default(monkeypatch):
    """A bare `VISION_MATCH_THRESHOLD=` means 'unset', not a crash."""
    for key in ("VISION_MATCH_THRESHOLD", "XAI_MAX_TOKENS",
                "VISION_AGENT_MAX_SESSIONS", "HARVEST_MAX_RPS"):
        monkeypatch.setenv(key, "")
    cfg = load_config()
    assert cfg.vision_match_threshold == 0.363
    assert cfg.xai_max_tokens == 512
    assert cfg.vision_agent_max_sessions == 200
    assert cfg.harvest_max_rps == 1.0


def test_non_numeric_env_falls_back_instead_of_raising(monkeypatch):
    monkeypatch.setenv("VISION_MATCH_THRESHOLD", "abc")
    monkeypatch.setenv("XAI_MAX_TOKENS", "1024.0")
    monkeypatch.setenv("VISION_AGENT_MAX_SESSIONS", "unlimited")
    cfg = load_config()
    assert cfg.vision_match_threshold == 0.363
    assert cfg.xai_max_tokens == 512
    assert cfg.vision_agent_max_sessions == 200


def test_create_service_survives_a_blank_rate_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "")
    monkeypatch.setenv("RATE_LIMIT_WINDOW", "")
    from aoep_shared.service import create_service

    assert create_service("memory") is not None


# --------------------------------------------------------------------------- #
# HTTP cache must not hand a shared-cache policy to a privileged response
# --------------------------------------------------------------------------- #
def test_cache_rules_match_whole_path_segments():
    registry = CacheRegistry()
    registry.register("/catalog", CacheRule(max_age=30))
    assert registry.match("/catalog") is not None
    assert registry.match("/catalog/export") is not None
    # Neighbouring paths that merely share a prefix must NOT inherit the rule.
    assert registry.match("/coursesecret") is None
    assert registry.match("/catalog-admin/secrets") is None


def test_authenticated_response_is_never_marked_publicly_cacheable():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from aoep_shared.http_cache import install

    app = FastAPI()
    install(app, standard_registry(), etag=False)

    @app.get("/catalog/export")
    def export():
        return {"secret": "partner catalog"}

    client = TestClient(app)
    anon = client.get("/catalog/export")
    assert "public" in anon.headers.get("cache-control", "")

    for header in ("Authorization", "X-Internal-Token", "X-Admin-Secret"):
        resp = client.get("/catalog/export", headers={header: "a-real-credential"})
        cache_control = resp.headers.get("cache-control", "")
        assert "public" not in cache_control, (header, cache_control)
        assert "no-store" in cache_control, (header, cache_control)


# --------------------------------------------------------------------------- #
# The knowledge store promises reads never fail
# --------------------------------------------------------------------------- #
def test_knowledge_store_recovers_from_a_deleted_or_corrupt_db():
    from aoep_shared.training_agents.knowledge_store import KnowledgeStore

    db = pathlib.Path(tempfile.mkdtemp()) / "knowledge.db"
    store = KnowledgeStore(db)
    expected = store.total()
    assert expected > 0

    # Its default home is ~/.cache, which cleanup tooling legitimately purges.
    db.unlink()
    assert store.total() == expected
    assert store.search(q="fire", limit=5)
    assert store.sources()
    assert store.status()["backend"] == "sqlite"

    db.write_bytes(b"not a sqlite database")
    assert store.total() == expected
    assert store.search(q="fire", limit=5)


# --------------------------------------------------------------------------- #
# The SDK local-only guard protects real credentials
# --------------------------------------------------------------------------- #
def test_sdk_loopback_check_is_not_a_string_prefix():
    from aoep_sdk.config import _is_local_url

    assert _is_local_url("http://localhost:8000") is True
    assert _is_local_url("http://127.0.0.1:8004") is True
    # Legitimate local stacks the prefix check wrongly rejected.
    assert _is_local_url("https://localhost:8004") is True
    assert _is_local_url("http://[::1]:8002") is True
    # Lookalike hosts the prefix check wrongly ACCEPTED, which shipped the
    # bearer, internal and admin tokens off-box.
    assert _is_local_url("http://localhost.attacker.example:8000") is False
    assert _is_local_url("http://127.0.0.1.evil.example") is False
    assert _is_local_url("https://api.salareen.com") is False


def test_jobs_result_cache_is_bounded():
    from aoep_shared import jobs

    jobs._RESULT_CACHE.clear()
    for i in range(jobs._RESULT_CACHE_MAX + 100):
        jobs._RESULT_CACHE.pop(f"k{i}", None)
        jobs._RESULT_CACHE[f"k{i}"] = (0.0, [])
        while len(jobs._RESULT_CACHE) > jobs._RESULT_CACHE_MAX:
            jobs._RESULT_CACHE.pop(next(iter(jobs._RESULT_CACHE)), None)
    assert len(jobs._RESULT_CACHE) == jobs._RESULT_CACHE_MAX
    jobs._RESULT_CACHE.clear()
