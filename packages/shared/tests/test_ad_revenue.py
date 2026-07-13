"""Tests for the ad revenue ledger (impressions/clicks/CPM/eCPM)."""

from aoep_shared.ad_revenue import (
    AdRevenueLedger,
    estimated_cpc,
    estimated_cpm,
)


def test_estimated_cpm_by_network_and_format():
    assert estimated_cpm("house", "display") == 0.50
    assert estimated_cpm("house", "video") == 1.00
    assert estimated_cpm("google_adsense", "video") == 8.00
    # Unknown network falls back to house; unknown format falls back to display.
    assert estimated_cpm("nope", "video") == estimated_cpm("house", "video")
    assert estimated_cpm("house", "banner") == estimated_cpm("house", "display")


def test_impression_revenue_is_cpm_over_1000():
    led = AdRevenueLedger()
    ev = led.record_impression("home-banner", network="google_adsense", fmt="display", tier="basic")
    assert ev.kind == "impression"
    # $2.50 CPM / 1000 = $0.0025 per impression.
    assert ev.revenue_usd == 0.0025


def test_click_revenue_is_cpc():
    led = AdRevenueLedger()
    ev = led.record_click("home-banner", network="google_adsense")
    assert ev.kind == "click"
    assert ev.revenue_usd == estimated_cpc("google_adsense")


def test_summary_aggregates_and_ctr_ecpm():
    led = AdRevenueLedger()
    for _ in range(1000):
        led.record_impression("class-preroll", network="house", fmt="video", tier="basic")
    led.record_click("class-preroll", network="house", fmt="video", tier="basic")

    s = led.summary()
    t = s["totals"]
    assert t["impressions"] == 1000
    assert t["clicks"] == 1
    assert t["ctr"] == 0.001
    # 1000 impressions * ($1.00/1000) = $1.00, plus one house click ($0.02).
    assert t["revenue_usd"] == 1.02
    # eCPM = revenue / impressions * 1000.
    assert t["ecpm_usd"] == 1.02

    placements = {r["key"]: r for r in s["by_placement"]}
    assert placements["class-preroll"]["impressions"] == 1000
    networks = {r["key"]: r for r in s["by_network"]}
    assert networks["house"]["clicks"] == 1
    assert s["by_day"]  # at least today's bucket
    assert len(s["recent"]) >= 1


def test_recent_is_capped_and_newest_first():
    led = AdRevenueLedger(max_events=10)
    for i in range(20):
        led.record_impression(f"p{i}", network="house")
    s = led.summary(recent_limit=5)
    # Ring buffer keeps only the last 10; totals still count all 20.
    assert s["totals"]["impressions"] == 20
    assert len(s["recent"]) == 5
    # Newest first.
    assert s["recent"][0]["placement"] == "p19"
