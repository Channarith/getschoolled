"""User-absence state machine: transitions, timing, group aggregation."""

from __future__ import annotations

from webcam_classroom.absence import (
    ABSENT,
    BRIEFLY_ABSENT,
    LOOKING_AWAY,
    PRESENT_STATE,
    AbsenceConfig,
    AbsenceTracker,
    GroupPresence,
)
from webcam_classroom.silhouette import ABSENT as SIL_ABSENT
from webcam_classroom.silhouette import PRESENT as SIL_PRESENT
from webcam_classroom.silhouette import SilhouetteReading


def _present(cov: float = 0.2) -> SilhouetteReading:
    return SilhouetteReading(SIL_PRESENT, True, cov, (0.5, 0.5), 1, 0.9, "test")


def _absent() -> SilhouetteReading:
    return SilhouetteReading(SIL_ABSENT, False, 0.0, (0.5, 0.5), 0, 0.0, "test")


def _cfg() -> AbsenceConfig:
    return AbsenceConfig(looking_away_after=4.0, brief_absent_after=6.0, absent_after=20.0)


def test_first_present_reading_transitions_to_present():
    t = AbsenceTracker("u1", _cfg())
    ev = t.update(_present(), attention=0.9, now=0.0)
    assert ev is not None
    assert ev.previous == "unknown"
    assert ev.current == PRESENT_STATE
    assert t.is_present()


def test_momentary_drop_does_not_flip_state():
    t = AbsenceTracker("u1", _cfg())
    t.update(_present(), attention=0.9, now=0.0)
    # A single missing frame 2s later is below brief_absent_after -> stays present.
    ev = t.update(_absent(), now=2.0)
    assert ev is None
    assert t.is_present()


def test_absence_progression_brief_then_absent():
    t = AbsenceTracker("u1", _cfg())
    t.update(_present(), attention=0.9, now=0.0)
    # Gone since t=1. At t=8 (7s) -> briefly_absent.
    t.update(_absent(), now=1.0)
    ev_brief = t.update(_absent(), now=8.0)
    assert ev_brief is not None
    assert ev_brief.current == BRIEFLY_ABSENT
    assert ev_brief.became_absent is True
    # At t=22 (21s) -> absent.
    ev_absent = t.update(_absent(), now=22.0)
    assert ev_absent is not None
    assert ev_absent.current == ABSENT
    assert t.is_absent()
    assert t.absent_seconds(now=22.0) >= 20.0


def test_return_recovers_immediately():
    t = AbsenceTracker("u1", _cfg())
    t.update(_present(), attention=0.9, now=0.0)
    t.update(_absent(), now=1.0)
    t.update(_absent(), now=25.0)  # absent
    assert t.is_absent()
    ev = t.update(_present(), attention=0.9, now=27.0)
    assert ev is not None
    assert ev.current == PRESENT_STATE
    assert ev.returned is True


def test_low_attention_triggers_looking_away():
    t = AbsenceTracker("u1", _cfg())
    t.update(_present(), attention=0.9, now=0.0)
    # Present but distracted since t=0.5; sustained past 4s -> looking_away.
    t.update(_present(), attention=0.1, now=0.5)
    ev = t.update(_present(), attention=0.1, now=5.0)
    assert ev is not None
    assert ev.current == LOOKING_AWAY
    # A momentary low-attention reading (not sustained) should NOT flip.
    t2 = AbsenceTracker("u2", _cfg())
    t2.update(_present(), attention=0.9, now=0.0)
    assert t2.update(_present(), attention=0.1, now=1.0) is None


def test_group_presence_any_absent_and_all_present():
    g = GroupPresence(config=_cfg())
    g.update("ana", _present(), attention=0.9, now=0.0)
    g.update("ben", _present(), attention=0.9, now=0.0)
    assert g.all_present()
    assert not g.any_absent()
    # Ben disappears long enough to be absent.
    g.update("ben", _absent(), now=1.0)
    g.update("ben", _absent(), now=25.0)
    assert g.any_absent()
    assert g.absent_users() == ["ben"]
    assert "ana" in g.present_users()
    # Ben returns -> all present again.
    g.update("ben", _present(), attention=0.9, now=27.0)
    assert g.all_present()
