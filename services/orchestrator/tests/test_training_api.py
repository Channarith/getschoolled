"""Training agents API on the orchestrator."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)


def test_agents_roster_lists_training_coaches():
    r = client.get("/api/agents/roster")
    assert r.status_code == 200
    roles = {a["role_id"] for a in r.json()}
    assert "harvester" in roles
    assert "emergency_training" in roles


def test_training_catalog_has_hundreds():
    meta = client.get("/api/training/catalog").json()
    assert meta["count"] >= 400
    domains = client.get("/api/training/domains").json()
    assert len(domains) >= 15


def test_training_scenarios_paginated():
    body = client.get("/api/training/scenarios", params={"limit": 10, "offset": 0}).json()
    assert body["total"] >= 400
    assert body["limit"] == 10
    assert len(body["scenarios"]) == 10


def test_training_scenario_session_tick_respond():
    scenarios = client.get(
        "/api/training/scenarios",
        params={"domain": "aviation", "limit": 5},
    ).json()
    sid_scenario = scenarios["scenarios"][0]["scenario_id"]
    if sid_scenario != "aviation_emergency_landing":
        # ensure legacy id still works
        assert client.get("/api/training/scenarios", params={"q": "aviation_emergency"}).json()["total"] >= 1

    created = client.post(
        "/api/training/sessions",
        json={"scenario_id": "aviation_emergency_landing"},
    )
    assert created.status_code == 200
    sid = created.json()["session_id"]

    for _ in range(6):
        tick = client.post(f"/api/training/sessions/{sid}/tick")
        assert tick.status_code == 200

    respond = client.post(
        f"/api/training/sessions/{sid}/respond",
        json={"text": "Aviate — maintain glide and pick a field."},
    )
    assert respond.status_code == 200
    assert respond.json()["turns"]

    got = client.get(f"/api/training/sessions/{sid}")
    assert got.status_code == 200
    assert got.json()["cues_seen"]
