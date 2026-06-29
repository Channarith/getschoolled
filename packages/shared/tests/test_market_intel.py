"""Market intelligence corpus, datamining extraction, and value projection."""

from aoep_shared import market_intel
from aoep_shared.harvest.market_bridge import extract_market_numbers, write_market_pack


def test_seed_corpus_is_cited_and_flagged():
    refs = market_intel.all_references()
    assert len(refs) >= 25
    for r in refs:
        assert r.metric and r.source and r.reference
        assert r.note  # every figure carries a verify/attribution note
    m = market_intel.meta()
    assert m["regions"] >= 8
    assert "disclaimer" in m


def test_search_by_region_and_category():
    us = market_intel.search_references(region="us")
    assert us and all(r.region == "us" for r in us)
    growth = market_intel.search_references(category="growth")
    assert growth and all(r.category == "growth" for r in growth)
    states = [r for r in market_intel.all_references() if r.region.startswith("us-")]
    assert states  # per-state per-pupil benchmarks present


def test_tam_for_region():
    tam = market_intel.tam_for_region("us")
    assert tam is not None
    assert tam.metric == "edtech_market_size"
    assert tam.value > 0


def test_value_projection_math_and_disclaimer():
    proj = market_intel.value_projection(
        {"us": 100_000, "india": 100_000},
        arpu_usd_per_year=100.0, paid_conversion=0.05,
    )
    # 100k users * 5% * $100 = $500k per region.
    by_region = {r["region"]: r for r in proj["regions"]}
    assert by_region["us"]["projected_annual_revenue_usd"] == 500_000.0
    assert proj["totals"]["projected_annual_revenue_usd"] == 1_000_000.0
    assert by_region["us"]["tam_capture_pct"] is not None
    assert "disclaimer" in proj


def test_extract_market_numbers_parses_money_and_percent():
    text = ("The global EdTech market reached $142.4 billion in 2023 and is "
            "projected to grow at 13.6% CAGR. US K-12 spend is about USD 870 billion.")
    recs = extract_market_numbers(text, source="Test Report", reference="t1", region="global")
    monies = [r for r in recs if r.unit == "USD"]
    pcts = [r for r in recs if r.unit == "percent"]
    assert any(abs(r.value - 142_400_000_000) < 1 for r in monies)
    assert any(abs(r.value - 870_000_000_000) < 1 for r in monies)
    assert any(abs(r.value - 13.6) < 1e-6 for r in pcts)
    assert all(r.year == 2023 for r in monies)  # nearest-year association


def test_datamined_pack_merges_into_corpus(tmp_path, monkeypatch):
    pack_dir = tmp_path / "market"
    pack_dir.mkdir()
    text = "A niche market worth $2 billion in 2024 growing 25%."
    recs = extract_market_numbers(text, source="Niche", reference="n1", region="latam",
                                  default_year=2024)
    n = write_market_pack(recs, pack_dir / "datamined.json")
    assert n >= 1
    monkeypatch.setenv("AOEP_CONTENT_PACKS", str(tmp_path))
    # Force cache refresh by clearing the combined cache.
    market_intel._CACHE["fingerprint"] = None
    refs = market_intel.search_references(region="latam")
    assert any(r.source == "Niche" for r in refs)
    # Restore for other tests.
    market_intel._CACHE["fingerprint"] = None
