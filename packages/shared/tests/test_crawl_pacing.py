"""Long/hourly crawl pacing + stop policy (pure decision function)."""

from __future__ import annotations

from aoep_shared.harvest.crawl import CrawlLimits, next_crawl_action


def _decide(**kw):
    base = dict(
        pages_total=10, made_progress=True, queue_pending=50,
        elapsed_s=100.0, hour_pages=5, hour_elapsed_s=100.0,
    )
    base.update(kw)
    limits = base.pop("limits")
    return next_crawl_action(limits=limits, **base)


def test_stops_at_max_total():
    limits = CrawlLimits(daemon=True, max_total=100)
    assert _decide(pages_total=100, limits=limits)[:2] == ("stop", "max_total")
    assert _decide(pages_total=99, limits=limits)[0] == "sleep"


def test_stops_at_max_hours():
    limits = CrawlLimits(daemon=True, max_seconds=3600)
    assert _decide(elapsed_s=3600.0, limits=limits)[:2] == ("stop", "max_hours")
    assert _decide(elapsed_s=10.0, limits=limits)[0] == "sleep"


def test_stops_when_drained_unless_keep_waiting():
    drained = dict(queue_pending=0, made_progress=False)
    assert _decide(**drained, limits=CrawlLimits(daemon=True))[:2] == ("stop", "drained")
    # keep_waiting keeps the daemon alive to wait for new seeds.
    assert _decide(**drained, limits=CrawlLimits(daemon=True, keep_waiting=True))[0] == "sleep"
    # still-pending queue is not drained.
    assert _decide(queue_pending=5, made_progress=False, limits=CrawlLimits(daemon=True))[0] == "sleep"


def test_non_daemon_single_pass():
    assert _decide(limits=CrawlLimits(daemon=False))[:2] == ("stop", "single_pass")


def test_hourly_cap_sleeps_until_hour_resets():
    limits = CrawlLimits(daemon=True, per_hour=50, interval_s=60, hour_s=3600)
    action, reason, secs = _decide(hour_pages=50, hour_elapsed_s=1200.0, limits=limits)
    assert action == "sleep" and reason == "hourly_cap"
    assert abs(secs - (3600 - 1200)) < 1     # sleep the rest of the hour
    # under the cap -> normal interval pacing
    a2, r2, s2 = _decide(hour_pages=10, limits=limits)
    assert a2 == "sleep" and r2 == "interval" and s2 == 60


def test_default_interval_pacing():
    action, reason, secs = _decide(limits=CrawlLimits(daemon=True, interval_s=90))
    assert (action, reason, secs) == ("sleep", "interval", 90.0)
