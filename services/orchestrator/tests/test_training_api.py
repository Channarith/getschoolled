"""Cognitive training agents API (scenarios / sessions / forecast / decide)."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)

SCENARIO = "engine-out-emergency-landing"


def test_list_scenarios_includes_flagship():
    r = client.get("/api/training/scenarios")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()["scenarios"]}
    assert SCENARIO in ids


def test_start_session_returns_brief_with_premortem():
    r = client.post("/api/training/sessions", json={"scenario_id": SCENARIO})
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["done"] is False
    brief = view["brief"]
    assert brief["premortem"]["risks"]
    assert brief["situation_picture"]["projection"]
    assert brief["options"]


def test_unknown_scenario_404():
    r = client.post("/api/training/sessions", json={"scenario_id": "nope"})
    assert r.status_code == 404


def test_forecast_scores_situational_awareness():
    sid = client.post("/api/training/sessions", json={"scenario_id": SCENARIO}).json()["session_id"]
    r = client.post(
        f"/api/training/sessions/{sid}/forecast",
        json={"noticed": ["engine and prop went quiet", "altitude gives glide time"]},
    )
    assert r.status_code == 200, r.text
    sa = r.json()["brief"]["situation_picture"]
    assert sa["sa_score"] is not None
    assert 0.0 < sa["sa_score"] <= 1.0


def test_decide_flow_completes_and_passes_when_correct():
    start = client.post("/api/training/sessions", json={"scenario_id": SCENARIO}).json()
    sid = start["session_id"]
    brief = start["brief"]
    done = False
    summary = None
    guard = 0
    while not done and guard < 12:
        guard += 1
        # Pick the textbook option by re-reading the phase from the scenario list.
        # The correct option is the one whose feedback starts with "Correct";
        # the API does not expose scores, so we map by known ids per phase.
        correct_by_phase = {
            "engine_failure": "pitch_best_glide",
            "pick_field": "field_into_wind",
            "troubleshoot": "run_flow",
            "declare": "mayday_squawk",
            "secure_land": "secure_brace",
        }
        option_id = correct_by_phase[brief["phase_id"]]
        res = client.post(
            f"/api/training/sessions/{sid}/decide",
            json={"option_id": option_id, "elapsed_s": 2.0,
                  "rationale": "Textbook action because it keeps me ahead of the situation; "
                               "the alternative is worse given the cues."},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["correct"] is True
        assert body["rapid"]["score"] >= 0.7
        done = body["done"]
        summary = body["summary"]
        brief = body["next_brief"]
    assert done is True
    assert summary["passed"] is True
    assert summary["overall_score"] >= 0.9
    assert summary["per_skill"]


def test_decide_unknown_option_404():
    sid = client.post("/api/training/sessions", json={"scenario_id": SCENARIO}).json()["session_id"]
    r = client.post(
        f"/api/training/sessions/{sid}/decide",
        json={"option_id": "does-not-exist", "elapsed_s": 1.0},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "unknown option"


def test_unknown_session_404():
    r = client.get("/api/training/sessions/deadbeef")
    assert r.status_code == 404
