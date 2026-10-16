"""Free-plan claims stop after the seat cap, the window, or a used trial."""

import time

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _signup(email: str) -> str:
    return client.post("/auth/signup", json={
        "email": email, "password": "Secret123", "display_name": "Free User",
    }).json()["token"]


def test_free_plan_offer_reports_the_cap_and_exclusions():
    body = client.get("/onboarding/free-plan").json()
    assert body["group_classes"] is False
    assert body["ai_agents"] is False
    assert body["trial_days"] > 0
    assert "seats_remaining" in body


def test_first_claim_starts_a_trial_and_the_next_person_is_refused_at_the_cap(monkeypatch):
    claimed = client.get("/onboarding/free-plan").json()["seats_claimed"]
    monkeypatch.setenv("FREE_PLAN_SEAT_LIMIT", str(claimed + 1))
    token = _signup(f"free-cap-{time.time_ns()}@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    chosen = client.post("/onboarding/plan", headers=headers, json={"tier": "free"})
    assert chosen.status_code == 200
    me = client.get("/auth/me", headers=headers).json()
    assert me["tier"] == "free"
    assert me["free_plan"]["active"] is True
    assert me["free_plan"]["group_classes"] is False
    assert me["free_plan"]["ai_agents"] is False

    other = _signup(f"free-cap-next-{time.time_ns()}@example.com")
    refused = client.post(
        "/onboarding/plan",
        headers={"Authorization": f"Bearer {other}"},
        json={"tier": "free"},
    )
    assert refused.status_code == 403
    assert "100" in refused.json()["detail"] or "full" in refused.json()["detail"].lower()


def test_free_plan_window_closed_refuses_a_new_claim(monkeypatch):
    monkeypatch.setenv("FREE_PLAN_OFFER_START", "1")
    monkeypatch.setenv("FREE_PLAN_OFFER_DAYS", "1")
    token = _signup(f"free-closed-{time.time_ns()}@example.com")
    refused = client.post(
        "/onboarding/plan",
        headers={"Authorization": f"Bearer {token}"},
        json={"tier": "free"},
    )
    assert refused.status_code == 403
    assert "ended" in refused.json()["detail"].lower()


def test_cloud_claim_without_redis_returns_503(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.delenv("REDIS_URL", raising=False)
    token = _signup(f"cloud-noredis-{time.time_ns()}@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    refused = client.post("/onboarding/plan", headers=headers, json={"tier": "free"})
    assert refused.status_code == 503
    assert "cannot be claimed" in refused.json()["detail"].lower()
    me = client.get("/auth/me", headers=headers).json()
    assert me["free_plan"]["active"] is False


def test_cloud_claim_with_unreachable_redis_returns_503(monkeypatch):
    import sys
    import types

    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")

    class _Unreachable:
        def ping(self):
            raise ConnectionError("redis unreachable")

    redis_mod = sys.modules.get("redis")
    if redis_mod is None:
        try:
            import redis as redis_mod
        except ImportError:
            redis_mod = types.ModuleType("redis")
            monkeypatch.setitem(sys.modules, "redis", redis_mod)
    monkeypatch.setattr(redis_mod, "from_url", lambda *_a, **_k: _Unreachable(), raising=False)

    token = _signup(f"cloud-down-{time.time_ns()}@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    refused = client.post("/onboarding/plan", headers=headers, json={"tier": "free"})
    assert refused.status_code == 503
    me = client.get("/auth/me", headers=headers).json()
    assert me["free_plan"]["active"] is False


def test_expired_trial_cannot_be_claimed_again(monkeypatch):
    past = time.time() - 20 * 86400
    monkeypatch.setenv("FREE_PLAN_OFFER_START", str(past - 86400))
    monkeypatch.setenv("FREE_PLAN_OFFER_DAYS", "36500")
    token = _signup(f"free-expired-{time.time_ns()}@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    account_id = client.get("/auth/me", headers=headers).json()["id"]
    app.state.accounts.claim_free_plan(account_id, now=past)
    refused = client.post("/onboarding/plan", headers=headers, json={"tier": "free"})
    assert refused.status_code == 403
    assert "ended" in refused.json()["detail"].lower()
