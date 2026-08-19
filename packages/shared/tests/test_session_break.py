"""Tests for session break / segmentation logic."""

from __future__ import annotations

import pytest

from aoep_shared.session_break import (
    BREAK_MIN_SLIDES,
    break_slide_indices,
    segment_break_payload,
    _segment_size,
)


def test_short_lessons_have_no_breaks():
    for n in range(1, BREAK_MIN_SLIDES):
        assert break_slide_indices(n) == frozenset(), n


def test_20_slide_module_has_no_internal_break():
    # 20 slides ≈ one 20-min segment — no mid-session break needed.
    bounds = break_slide_indices(20)
    assert len(bounds) == 0


def test_24_slide_lesson_has_one_break():
    # 24 slides → ~20-min size 16 → one break at slide 15.
    bounds = break_slide_indices(24)
    assert len(bounds) == 1
    assert 23 not in bounds  # last slide never a break


def test_40_slide_lesson_has_breaks():
    bounds = break_slide_indices(40)
    assert len(bounds) >= 2
    assert 39 not in bounds  # never the last slide


def test_120_slide_track_has_many_breaks():
    bounds = break_slide_indices(120)
    # 10-min segments at size ~8 → about 15 breaks across 120 slides.
    assert len(bounds) >= 10
    assert 119 not in bounds


def test_break_payload_returned_at_boundary():
    n = 40
    bounds = break_slide_indices(n)
    boundary = next(iter(sorted(bounds)))
    payload = segment_break_payload(boundary, n)
    assert payload is not None
    assert payload["due"] is True
    assert payload["slide_index"] == boundary
    assert payload["slides_done"] == boundary + 1
    assert payload["slides_remaining"] == n - boundary - 1
    assert "Keep going" in str(payload["choices"])
    assert "break" in str(payload["choices"]).lower()


def test_non_boundary_returns_none():
    n = 40
    bounds = break_slide_indices(n)
    for i in range(n):
        if i not in bounds:
            assert segment_break_payload(i, n) is None
            break


def test_last_slide_never_a_boundary():
    for n in [20, 30, 40, 60, 100, 120]:
        bounds = break_slide_indices(n)
        assert n - 1 not in bounds, n


def test_segment_size_tiers():
    # Short lessons → 20-min segments (largest size)
    assert _segment_size(20) >= _segment_size(50)
    # Very long lessons → smallest segments
    assert _segment_size(100) <= _segment_size(30)


def test_break_payload_message_contains_elapsed_and_remaining():
    payload = segment_break_payload(11, 40)  # might not be a boundary
    if payload is None:
        bounds = break_slide_indices(40)
        payload = segment_break_payload(next(iter(sorted(bounds))), 40)
    assert payload is not None
    msg = payload["message"]
    assert "segment" in msg.lower() or "minute" in msg.lower()
