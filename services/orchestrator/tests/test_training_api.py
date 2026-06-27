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


def test_training_scenario_session_tick_respond():
    scenarios = client.get("/api/training/scenarios").json()
    assert any(s["scenario_id"] == "aviation_emergency_landing" for s in scenarios)

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
