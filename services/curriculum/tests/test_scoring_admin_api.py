"""Course scoring admin API: review, edit config, override, telemetry."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


_SECTIONS = [
    {"heading": "Introduction", "body": "welcome and objectives"},
    {"heading": "Core concept", "body": "the main theory"},
    {"heading": "Worked example", "body": "example problem"},
    {"heading": "Practice exercise", "body": "try it yourself"},
    {"heading": "Knowledge check quiz", "body": "quick quiz"},
    {"heading": "Summary", "body": "wrap up"},
]


def test_scoring_breakdown_explains_score():
    r = client.post("/scoring/breakdown", json={
        "course_id": "chem-101", "subject": "chemistry", "sections": _SECTIONS,
    })
    assert r.status_code == 200
    body = r.json()["breakdown"]
    assert isinstance(body["composition_score"], int)
    f = body["pcs_formula"]
    assert f["raw_before_modulus"] % f["modulus"] == body["composition_score"]
    assert 0 <= body["quality_index"] <= 100


def test_scoring_config_edit_roundtrip():
    original = client.get("/scoring/config").json()
    assert "normalized_weights" in original

    updated = client.put("/scoring/config", json={
        "quality_weights": {"coverage": 0.1, "balance": 0.1, "interactivity": 0.7, "depth": 0.1},
        "notes": "favor interactivity",
    }).json()
    assert updated["notes"] == "favor interactivity"
    assert updated["normalized_weights"]["interactivity"] > 0.5

    # Breakdown now reflects the new weights.
    body = client.post("/scoring/breakdown", json={"sections": _SECTIONS}).json()["breakdown"]
    assert body["config_version"] == updated["version"]

    # Restore defaults for other tests.
    client.put("/scoring/config", json={
        "quality_weights": {"coverage": 0.30, "balance": 0.20,
                            "interactivity": 0.30, "depth": 0.20},
        "notes": "",
    })


def test_manual_override_adjusts_label_and_score():
    client.put("/scoring/overrides/chem-101", json={
        "label": "flagship-128", "score": 128, "quality_index": 92.0,
        "note": "hand-tuned", "author": "admin",
    })
    body = client.post("/scoring/breakdown", json={
        "course_id": "chem-101", "subject": "chemistry", "sections": _SECTIONS,
    }).json()
    eff = body["effective"]
    assert eff["overridden"] is True
    assert eff["score"] == 128
    assert eff["label"] == "flagship-128"
    # Computed score is preserved alongside the override.
    assert eff["computed"]["score"] == body["breakdown"]["composition_score"]

    assert client.delete("/scoring/overrides/chem-101").json()["deleted"] is True


def test_telemetry_record_compare_and_recommend():
    samples = [
        ("A", 128, 80, 0.9, {"coverage": 0.6, "balance": 0.5, "interactivity": 0.9, "depth": 0.4}),
        ("B", 247, 60, 0.5, {"coverage": 0.6, "balance": 0.5, "interactivity": 0.3, "depth": 0.4}),
        ("C", 311, 70, 0.7, {"coverage": 0.6, "balance": 0.5, "interactivity": 0.6, "depth": 0.4}),
    ]
    for cid, score, qi, happ, metrics in samples:
        assert client.post("/scoring/telemetry", json={
            "course_id": cid, "composition_score": score, "quality_index": qi,
            "subject": "chem", "happiness": happ, "metrics": metrics,
        }).json()["recorded"] is True

    assert client.get("/scoring/telemetry/A").json()["avg_happiness"] == 0.9
    cmp = client.get("/scoring/compare", params={"a": "A", "b": "B"}).json()
    assert cmp["winner"] == "A"
    board = client.get("/scoring/leaderboard", params={"subject": "chem"}).json()
    assert board[0]["course_id"] == "A"

    rec = client.get("/scoring/recommend").json()
    assert rec["status"] == "ok"
    assert rec["correlations"]["interactivity"] > 0
