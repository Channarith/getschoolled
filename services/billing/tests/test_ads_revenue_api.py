"""API tests for the billing ad-revenue endpoints."""

from fastapi.testclient import TestClient

from billing.main import app


def _client():
    # Fresh ledger per test so counts are deterministic.
    from aoep_shared.ad_revenue import AdRevenueLedger

    app.state.ad_ledger = AdRevenueLedger()
    return TestClient(app)


def test_impression_then_revenue_report():
    c = _client()
    r = c.post("/ads/impression", json={
        "placement": "home-banner", "network": "google_adsense",
        "fmt": "display", "tier": "basic", "unit_id": "home-banner",
    })
    assert r.status_code == 200
    assert r.json()["revenue_usd"] == 0.0025

    rep = c.get("/ads/revenue").json()
    assert rep["totals"]["impressions"] == 1
    assert rep["totals"]["revenue_usd"] == 0.0025
    assert any(p["key"] == "home-banner" for p in rep["by_placement"])
    assert "active_network" in rep


def test_click_adds_cpc_revenue():
    c = _client()
    c.post("/ads/impression", json={"placement": "class-preroll", "network": "house", "fmt": "video", "tier": "basic"})
    r = c.post("/ads/click", json={"placement": "class-preroll", "network": "house", "fmt": "video", "tier": "basic"})
    assert r.status_code == 200
    rep = c.get("/ads/revenue").json()
    assert rep["totals"]["clicks"] == 1
    # video impression ($1/1000 = 0.001) + house click ($0.02) = 0.021
    assert rep["totals"]["revenue_usd"] == 0.021


def test_revenue_report_empty_ledger():
    c = _client()
    rep = c.get("/ads/revenue").json()
    assert rep["totals"]["impressions"] == 0
    assert rep["totals"]["revenue_usd"] == 0.0
    assert rep["by_placement"] == []
