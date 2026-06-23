"""The AI agent grants reward points (signed voucher) on substantive questions."""

from __future__ import annotations

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def _start():
    lessons = client.get("/api/lessons").json()
    lid = lessons[0]["lesson_id"]
    return client.post("/api/sessions", json={"lesson_id": lid, "class_type": "group"}) \
        .json()["session"]["session_id"]


def test_ask_grants_signed_reward_voucher(monkeypatch):
    key = "shared-internal-key"
    monkeypatch.setenv("INTERNAL_TOKEN_KEY", key)
    sid = _start()
    ans = client.post(f"/api/sessions/{sid}/ask",
                      json={"text": "What is the main idea of this lesson?"}).json()
    reward = ans.get("reward")
    assert reward and reward["points"] == 10
    # The voucher is a valid agent-signed reward token.
    from aoep_shared.auth import verify_token
    body = verify_token(reward["grant_token"], key.encode("utf-8"))
    assert body and body["scope"] == "reward" and body["points"] == 10
    assert body["nonce"]


def test_reward_capped_per_session(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN_KEY", "shared-internal-key")
    sid = _start()
    total = 0
    for _ in range(5):
        ans = client.post(f"/api/sessions/{sid}/ask",
                          json={"text": "What is the main idea of this lesson?"}).json()
        if ans.get("reward"):
            total += ans["reward"]["points"]
    assert total == 30   # AGENT_REWARD_SESSION_CAP (3 x 10)


def test_no_reward_without_key(monkeypatch):
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)
    sid = _start()
    ans = client.post(f"/api/sessions/{sid}/ask",
                      json={"text": "What is the main idea of this lesson?"}).json()
    assert ans.get("reward") in (None, {})


def test_no_reward_for_trivial_question(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN_KEY", "shared-internal-key")
    sid = _start()
    ans = client.post(f"/api/sessions/{sid}/ask", json={"text": "hi"}).json()
    assert ans.get("reward") in (None, {})
