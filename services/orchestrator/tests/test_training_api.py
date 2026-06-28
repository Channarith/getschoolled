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


def test_training_knowledge_base_real_and_cited():
    meta = client.get("/api/training/knowledge/meta").json()
    assert meta["count"] >= 60
    assert meta["sources"] >= 30

    sources = client.get("/api/training/knowledge/sources").json()
    names = {s["source"] for s in sources}
    assert any("NHTSA" in n for n in names)
    assert any("FAA" in n for n in names)

    body = client.get("/api/training/knowledge", params={"domain": "marine", "limit": 50}).json()
    assert body["total"] >= 3
    for f in body["facts"]:
        assert f["fact"] and f["source"] and f["reference"]


def test_training_knowledge_status_persistent_db():
    status = client.get("/api/training/knowledge/status").json()
    assert status["backend"] in ("sqlite", "memory")
    assert status["count"] >= 60
    meta = client.get("/api/training/knowledge/meta").json()
    assert meta["store"]["backend"] in ("sqlite", "memory")


def test_scenario_detail_includes_real_references():
    detail = client.get("/api/training/scenarios/road_car__1000").json()
    assert detail["scenario_id"] == "road_car__1000"
    assert detail["references"]
    assert all(r["source"] and r["reference"] for r in detail["references"])


def test_session_view_includes_references():
    created = client.post(
        "/api/training/sessions",
        json={"scenario_id": "medical_triage_quick"},
    ).json()
    sid = created["session_id"]
    got = client.get(f"/api/training/sessions/{sid}").json()
    assert "references" in got
    assert got["references"]


def test_training_catalog_has_thousands():
    meta = client.get("/api/training/catalog").json()
    assert meta["count"] >= 3000
    domains = client.get("/api/training/domains").json()
    assert len(domains) >= 40


def test_training_capacity_in_millions():
    cap = client.get("/api/training/capacity").json()
    assert cap["procedural_capacity"] >= 1_000_000
    assert cap["total_addressable"] >= 1_000_000


def test_training_families_and_generate():
    fams = client.get("/api/training/families").json()
    fam_ids = {f["family_id"] for f in fams}
    for fid in ("road_car", "rail_train", "bicycle", "boat", "pedestrian", "police", "school_student"):
        assert fid in fam_ids

    gen = client.get("/api/training/generate", params={"family_id": "road_car", "index": 1000}).json()
    assert gen["scenario_id"] == "road_car__1000"
    assert gen["briefing"]
    assert gen["domain"] == "road"

    rnd = client.get("/api/training/generate/random", params={"family_id": "scooter", "seed": 3}).json()
    assert rnd["scenario_id"].startswith("scooter__")


def test_run_generated_scenario_session():
    created = client.post(
        "/api/training/sessions",
        json={"scenario_id": "road_motorcycle__250"},
    )
    assert created.status_code == 200
    sid = created.json()["session_id"]
    for _ in range(6):
        assert client.post(f"/api/training/sessions/{sid}/tick").status_code == 200
    got = client.get(f"/api/training/sessions/{sid}")
    assert got.json()["cues_seen"]


def test_training_scenarios_paginated():
    body = client.get("/api/training/scenarios", params={"limit": 10, "offset": 0}).json()
    assert body["total"] >= 1000
    assert body["limit"] == 10
    assert len(body["scenarios"]) == 10


def test_training_tracks_and_random():
    tracks = client.get("/api/training/tracks").json()
    assert len(tracks) >= 10
    pilot = next(t for t in tracks if t["track_id"] == "pilot_emergency")
    assert pilot["scenario_count"] >= 20

    track_body = client.get("/api/training/tracks/pilot_emergency").json()
    assert track_body["total"] >= 20
    assert track_body["scenarios"]

    rnd = client.get("/api/training/scenarios/random", params={"track_id": "pilot_emergency", "seed": 7})
    assert rnd.status_code == 200
    assert rnd.json()["scenario_id"]


def test_training_scenario_session_tick_respond():
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
