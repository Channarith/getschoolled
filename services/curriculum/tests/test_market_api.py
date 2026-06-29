"""Market intelligence + investor value-projection API."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def test_market_meta_and_regions():
    m = client.get("/market/meta").json()
    assert m["count"] >= 25
    assert m["regions"] >= 8
    assert "disclaimer" in m
    regions = client.get("/market/regions").json()
    assert "us" in regions["regions"]
    assert any(s["source"] == "NCES" for s in regions["sources"])


def test_market_references_filter():
    us = client.get("/market/references", params={"region": "us"}).json()
    assert us and all(r["region"] == "us" for r in us)
    for r in us:
        assert r["source"] and r["reference"] and r["note"]


def test_market_projection_endpoint():
    body = client.post("/market/projection", json={
        "users_by_region": {"us": 1_000_000, "india": 1_000_000},
        "arpu_usd_per_year": 96, "paid_conversion": 0.05,
    }).json()
    assert body["totals"]["projected_annual_revenue_usd"] > 0
    assert "disclaimer" in body
    by_region = {r["region"]: r for r in body["regions"]}
    assert by_region["us"]["tam_capture_pct"] is not None
