"""Exhaustive feature-flag coverage: every registered public flag must resolve,
and the resolvable flag set must be stable across tier contexts. Data-driven off
the live flag registry so new flags are covered automatically.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from memory.main import app

client = TestClient(app)


def test_every_public_flag_resolves():
    flags = client.get("/flags/evaluate").json()["flags"]
    assert flags, "no public feature flags registered"
    for key in flags:
        r = client.get(f"/flags/{key}")
        assert r.status_code == 200, f"{key}: {r.text}"
        body = r.json()
        assert "value" in body and "spec" in body


def test_unknown_flag_returns_404():
    assert client.get("/flags/__does_not_exist__").status_code == 404


def test_flag_set_is_stable_across_tiers():
    free = client.get("/flags/evaluate", params={"tier": "free"}).json()["flags"]
    pro = client.get("/flags/evaluate", params={"tier": "pro"}).json()["flags"]
    assert set(free) == set(pro)
