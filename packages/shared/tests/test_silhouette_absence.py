"""Silhouette + absence unit tests (no OpenCV required)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from aoep_shared.vision.absence import (
    PRESENCE_ABSENT,
    PRESENCE_LIVE,
    PRESENCE_SILHOUETTE,
    AbsencePolicy,
    AbsenceTracker,
    FramePresenceInput,
)
from aoep_shared.vision.silhouette_signals import (
    detect_silhouette,
    silhouette_from_counts,
)


def test_silhouette_from_counts():
    empty = silhouette_from_counts(person_count=0)
    assert empty.present is False
    assert empty.person_count == 0

    one = silhouette_from_counts(person_count=1, confidence=0.9)
    assert one.present is True
    assert one.person_count == 1
    assert one.confidence == 0.9
    assert one.primary_bbox is not None


def test_energy_silhouette_on_person_like_blob():
    # Synthetic frame: flat background + high-contrast mid blob ("person").
    frame = np.full((240, 320, 3), 30, dtype=np.uint8)
    frame[40:220, 100:220] = 200
    # Add texture so energy detector fires.
    rng = np.random.default_rng(0)
    frame[40:220, 100:220] = np.clip(
        frame[40:220, 100:220].astype(np.int16) + rng.integers(-40, 40, size=(180, 120, 3)),
        0,
        255,
    ).astype(np.uint8)
    signals = detect_silhouette(frame, prefer_hog=False)
    assert signals.present is True
    assert signals.person_count >= 1
    assert signals.observations[0].source == "energy"


def test_blank_frame_no_silhouette():
    frame = np.full((120, 160, 3), 40, dtype=np.uint8)
    signals = detect_silhouette(frame, prefer_hog=False)
    # Uniform frame should not claim a person.
    assert signals.present is False


def test_absence_face_then_silhouette_then_absent():
    tracker = AbsenceTracker("p1", policy=AbsencePolicy(grace_seconds=5.0))
    t0 = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)

    d = tracker.update(
        FramePresenceInput(
            face_count=1,
            attention=0.7,
            silhouette=silhouette_from_counts(person_count=1),
        ),
        now=t0,
    )
    assert d.state == PRESENCE_LIVE
    assert d.present is True
    assert d.hold is False

    d = tracker.update(
        FramePresenceInput(
            face_count=0,
            silhouette=silhouette_from_counts(person_count=1, confidence=0.6),
        ),
        now=t0 + timedelta(seconds=1),
    )
    assert d.state == PRESENCE_SILHOUETTE
    assert d.present is True
    assert d.should_reengage is True

    d = tracker.update(
        FramePresenceInput(face_count=0, silhouette=silhouette_from_counts(person_count=0)),
        now=t0 + timedelta(seconds=2),
    )
    assert d.state == PRESENCE_ABSENT
    assert d.hold is False  # still inside grace

    d = tracker.update(
        FramePresenceInput(face_count=0, silhouette=silhouette_from_counts(person_count=0)),
        now=t0 + timedelta(seconds=8),
    )
    assert d.state == PRESENCE_ABSENT
    assert d.hold is True
    assert d.absent_for_seconds >= 5.0


def test_mark_stale():
    tracker = AbsenceTracker("p2", policy=AbsencePolicy(stale_seconds=5.0, grace_seconds=3.0))
    t0 = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)
    tracker.update(
        FramePresenceInput(face_count=1, attention=0.5),
        now=t0,
    )
    d = tracker.mark_stale(now=t0 + timedelta(seconds=2))
    assert d.state == PRESENCE_LIVE
    d = tracker.mark_stale(now=t0 + timedelta(seconds=10))
    assert d.state == PRESENCE_ABSENT
    assert d.reason == "stale_signal"
