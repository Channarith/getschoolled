"""Shared-package regressions for audit-2026-08-16 CRITICAL/HIGH fixes."""

from __future__ import annotations

import time

import pytest


def test_practice_xp_clamps_forged_correct_counts():
    from aoep_shared.language_learning import practice_xp

    assert practice_xp("pronunciation", 1_000_000, 0) == 0
    assert practice_xp("pronunciation", 1_000_000, 5) == practice_xp("pronunciation", 5, 5)
    assert practice_xp("vocabulary", -3, 10) == 0
    assert 0 < practice_xp("pronunciation", 50, 50) <= 500
    assert practice_xp("pronunciation", 999, 999) <= 500


def test_on_return_fires_after_real_absence():
    from aoep_shared.vision.webcam_presence import PresenceState, WebcamPresenceTracker

    returned = []
    t = WebcamPresenceTracker(
        absence_threshold_s=0.01,
        return_threshold_s=0.01,
        on_return=lambda m: returned.append(m.return_events),
    )
    t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    time.sleep(0.03)
    t.update(face_count=0, silhouette_confidence=0.0, warming_up=False)
    assert t.state == PresenceState.ABSENT
    time.sleep(0.03)
    t.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
    assert t.state == PresenceState.PRESENT_FACE
    assert len(returned) >= 1
    assert t.metrics.return_events >= 1


def test_gallery_rejects_short_embedding_poison():
    from aoep_shared.vision.gallery import FaceGallery

    g = FaceGallery()
    g.enroll("alice", [0.1] * 128)
    with pytest.raises(ValueError):
        g.enroll("alice", [0.5, 0.5, 0.5])
    proto = g.prototype("alice")
    assert proto is not None and len(proto) == 128


def test_gallery_rejects_empty_embedding():
    from aoep_shared.vision.gallery import FaceGallery

    g = FaceGallery()
    with pytest.raises(ValueError):
        g.enroll("alice", [])


def test_catalog_deep_link_avoids_gated_watch():
    from aoep_shared.learnable.index import _from_catalog_course

    item = _from_catalog_course({
        "course_id": "algebra-101",
        "title": "Algebra",
        "media_format": "video",
        "core_skill": True,
        "tags": [],
    })
    assert item.deep_link.startswith("/class?lesson=")
    assert "/watch" not in item.deep_link
    assert item.core_skill is True


def test_core_skill_filter_honours_explicit_flag():
    from aoep_shared.learnable.index import search_learnable
    from aoep_shared.learnable.models import LearnableItem

    items = [
        LearnableItem(
            id="catalog:obscure",
            source="catalog",
            source_id="obscure-course",
            title="Obscure Specialty",
            subject="specialty",
            core_skill=True,
        ),
        LearnableItem(
            id="catalog:other",
            source="catalog",
            source_id="other-course",
            title="Other",
            subject="specialty",
            core_skill=False,
        ),
    ]
    hit = search_learnable(items, core_skill=True, limit=50)
    ids = {c.source_id for c in hit["items"]}
    assert "obscure-course" in ids
    assert "other-course" not in ids
