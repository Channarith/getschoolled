"""Tests for the ecosystem capacity projection model + chart rendering."""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

cap = importlib.import_module("capacity_projection")


def test_service_shares_sum_to_one():
    assert abs(sum(cap.SERVICE_SHARES.values()) - 1.0) < 1e-9


def test_concurrency_follows_littles_law():
    # 1,000,000 DAU * (30/60)/16 = 31,250 concurrent.
    assert cap.concurrent_users(1_000_000) == 31_250
    assert cap.concurrent_users(0) == 0


def test_project_tiers_scale_monotonically():
    rows = cap.build_projection([10, 100, 1_000, 1_000_000])
    peaks = [r["peak_aggregate_rps"] for r in rows]
    assert peaks == sorted(peaks)
    concurrents = [r["concurrent_users"] for r in rows]
    assert concurrents == sorted(concurrents)


def test_small_tiers_sit_at_ha_floor():
    r = cap.project(10)
    # 7 services * 3-pod HA floor.
    assert r["total_pods_peak"] == 7 * cap.HPA_MIN_PODS
    assert r["single_region_ok"] is True
    assert r["p95_ms"] == cap.BASE_P95_MS


def test_one_million_users_fits_single_region():
    r = cap.project(1_000_000)
    assert r["peak_aggregate_rps"] == 81_250
    assert r["single_region_ok"] is True
    # Every service stays within the per-region HPA ceiling.
    for svc in r["services"].values():
        assert svc["pods_needed"] <= cap.HPA_MAX_PODS
    # Orchestrator is the busiest origin service.
    assert r["services"]["orchestrator"]["pods_needed"] >= 20


def test_cdn_offload_reduces_curriculum_pods():
    r = cap.project(1_000_000)
    curr = r["services"]["curriculum"]
    orch = r["services"]["orchestrator"]
    # Curriculum carries more raw RPS but needs fewer pods due to CDN offload.
    assert curr["peak_rps"] > orch["peak_rps"]
    assert curr["pods_needed"] < orch["pods_needed"]


def test_renderers_produce_output():
    rows = cap.build_projection()
    table = cap.render_table(rows)
    assert "PROJECTED ECOSYSTEM PERFORMANCE" in table
    assert "1,000,000" in table
    svg = cap.render_svg(rows)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "Concurrent users" in svg and "Peak aggregate RPS" in svg
