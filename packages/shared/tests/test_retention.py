"""Retention/deletion enforcement helpers."""

from datetime import datetime, timedelta, timezone

from aoep_shared.retention import is_expired

NOW = datetime(2026, 6, 18, tzinfo=timezone.utc)


def test_no_retention_means_kept():
    old = NOW - timedelta(days=10_000)
    assert is_expired(old, None, now=NOW) is False
    # ...unless a default window is supplied.
    assert is_expired(old, None, now=NOW, default_days=30) is True


def test_expired_after_window():
    rec = NOW - timedelta(days=31)
    assert is_expired(rec, 30, now=NOW) is True


def test_within_window_kept():
    rec = NOW - timedelta(days=10)
    assert is_expired(rec, 30, now=NOW) is False


def test_naive_datetime_treated_as_utc():
    naive = datetime(2026, 1, 1)  # no tzinfo
    assert is_expired(naive, 30, now=NOW) is True
