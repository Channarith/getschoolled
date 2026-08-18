"""Regression tests for audit findings in shared packages."""

from __future__ import annotations

import time

import pytest

from aoep_shared.language_learning import practice_xp
from aoep_shared.vision.gallery import FaceGallery


def test_practice_xp_clamps_correct_to_total():
    assert practice_xp("vocabulary", 1_000_000, 0) == 0
    assert practice_xp("vocabulary", 10, 5) == practice_xp("vocabulary", 5, 5)


def test_gallery_rejects_mismatched_embedding_dimensions():
    gallery = FaceGallery()
    gallery.enroll("alice", [0.1, 0.2, 0.3])
    with pytest.raises(ValueError, match="dimension"):
        gallery.enroll("alice", [0.5, 0.5])


def test_return_event_fires_after_presence_threshold():
    from aoep_shared.vision.webcam_presence import PresenceState, WebcamPresenceTracker

    returned = []
    t = WebcamPresenceTracker(
        absence_threshold_s=0.01,
        return_threshold_s=0.05,
        on_return=lambda m: returned.append(m.return_events),
    )
    t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    time.sleep(0.02)
    t.update(face_count=0, silhouette_confidence=0.0, warming_up=False)
    assert t.state == PresenceState.ABSENT
    t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    assert len(returned) == 0
    time.sleep(0.06)
    t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    assert len(returned) == 1
