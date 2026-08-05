"""Tests for solo and group class sessions."""

from __future__ import annotations

from webcam_recognition.config import LabConfig
from webcam_recognition.presence import PresenceEvent
from webcam_recognition.session import (
    ClassMode,
    GroupSession,
    SoloSession,
    TeachingMode,
)
from webcam_recognition.silhouette import summarize_frame

CFG = LabConfig(absent_grace_s=2.0, present_grace_s=1.0)


def _present(face=1, attention=0.8):
    return summarize_frame([], face_count=face, attention=attention)


def _absent():
    return summarize_frame([], face_count=0)


def test_solo_session_arrival_and_absence():
    s = SoloSession("s1", TeachingMode.THEODORE, CFG)
    ev = s.observe(_present(), now=0.0)
    assert ev is not None and ev.event is PresenceEvent.ARRIVED
    assert s.observe(_absent(), now=1.0) is None       # within grace
    left = s.observe(_absent(), now=3.0)               # grace elapsed
    assert left is not None and left.event is PresenceEvent.LEFT
    status = s.status()
    assert status["mode"] == "solo"
    assert status["present"] is False


def test_solo_session_tracks_attention_ewma():
    s = SoloSession("s2", TeachingMode.SELF, CFG)
    s.observe(_present(attention=1.0), now=0.0)
    s.observe(_present(attention=0.0), now=1.0)
    assert 0.0 < s.attention_ewma < 1.0


def test_group_session_headcount_and_absence():
    g = GroupSession("g1", TeachingMode.THEODORE, CFG)
    g.observe(["alice", "bob"], now=0.0)   # both arrive
    assert set(g.present_ids()) == {"alice", "bob"}
    assert g.headcount() == 2
    # bob drops out of frame; alice stays.
    g.observe(["alice"], now=1.0)
    g.observe(["alice"], now=3.0)          # bob's absence grace elapses
    g.observe(["alice"], now=3.1)
    assert g.headcount() == 1
    assert "bob" in g.absent_ids()
    # Attendance is tracked per participant.
    status = g.status()
    roster_ids = {r["participant_id"] for r in status["roster"]}
    assert roster_ids == {"alice", "bob"}


def test_group_session_emits_left_and_returned():
    g = GroupSession("g2", TeachingMode.THEODORE, CFG)
    g.observe(["alice"], now=0.0)
    g.observe([], now=1.0)
    left = g.observe([], now=3.0)
    assert any(e.event is PresenceEvent.LEFT and e.participant_id == "alice" for e in left)
    g.observe(["alice"], now=4.0)
    returned = g.observe(["alice"], now=5.5)
    assert any(
        e.event is PresenceEvent.RETURNED and e.participant_id == "alice"
        for e in returned
    )


def test_group_auto_enrolls_seen_ids():
    g = GroupSession("g3", TeachingMode.THEODORE, CFG)
    g.observe(["carol"], now=0.0)
    assert "carol" in g.participants
