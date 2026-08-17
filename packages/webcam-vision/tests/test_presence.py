"""Presence state machine tests (deterministic fake clocks)."""

from aoep_webcam_vision.presence import (
    EVENT_ABSENT,
    EVENT_PRESENT,
    EVENT_RETURNED,
    EVENT_SILHOUETTE,
    PresenceMonitor,
    PresenceState,
    PresenceTracker,
)


def kinds(events):
    return [e.kind for e in events]


class TestTrackerTransitions:
    def test_first_face_is_present(self):
        t = PresenceTracker("learner-1")
        events = t.observe(face_visible=True, person_visible=True, at=0.0)
        assert t.state is PresenceState.PRESENT
        assert kinds(events) == [EVENT_PRESENT]

    def test_first_silhouette_is_silhouette_not_returned(self):
        t = PresenceTracker("learner-1")
        events = t.observe(face_visible=False, person_visible=True, at=0.0)
        assert t.state is PresenceState.SILHOUETTE
        assert kinds(events) == [EVENT_SILHOUETTE]

    def test_empty_frames_at_start_stay_silent(self):
        t = PresenceTracker("learner-1")
        for i in range(5):
            assert t.observe(face_visible=False, person_visible=False, at=float(i)) == []
        assert t.state is PresenceState.ABSENT

    def test_face_implies_person(self):
        t = PresenceTracker("learner-1")
        t.observe(face_visible=True, person_visible=False, at=0.0)
        assert t.state is PresenceState.PRESENT
        assert t.last_person_at == 0.0

    def test_silhouette_requires_grace_after_face_loss(self):
        t = PresenceTracker("learner-1", silhouette_grace_s=5.0)
        t.observe(face_visible=True, person_visible=True, at=0.0)
        # Face lost but person still in frame: no transition before grace.
        for at in (1.0, 2.0, 4.9):
            events = t.observe(face_visible=False, person_visible=True, at=at)
            assert events == []
            assert t.state is PresenceState.PRESENT
        events = t.observe(face_visible=False, person_visible=True, at=5.0)
        assert kinds(events) == [EVENT_SILHOUETTE]
        assert t.state is PresenceState.SILHOUETTE

    def test_absence_requires_sustained_gap(self):
        t = PresenceTracker("learner-1", absence_grace_s=10.0)
        t.observe(face_visible=True, person_visible=True, at=0.0)
        # A single dropped frame must not declare absence.
        assert t.observe(face_visible=False, person_visible=False, at=3.0) == []
        assert t.state is PresenceState.PRESENT
        # Person reappears before the grace elapses: no absence ever fired.
        assert kinds(t.observe(face_visible=True, person_visible=True, at=6.0)) == []
        # Now a real walk-away.
        assert t.observe(face_visible=False, person_visible=False, at=10.0) == []
        events = t.observe(face_visible=False, person_visible=False, at=16.0)
        assert kinds(events) == [EVENT_ABSENT]
        assert t.state is PresenceState.ABSENT

    def test_return_with_face_emits_returned_then_present(self):
        t = PresenceTracker("learner-1", absence_grace_s=5.0)
        t.observe(face_visible=True, person_visible=True, at=0.0)
        t.observe(face_visible=False, person_visible=False, at=10.0)
        assert t.state is PresenceState.ABSENT
        events = t.observe(face_visible=True, person_visible=True, at=12.0)
        assert kinds(events) == [EVENT_RETURNED, EVENT_PRESENT]
        assert t.state is PresenceState.PRESENT

    def test_return_as_silhouette_emits_returned(self):
        t = PresenceTracker("learner-1", absence_grace_s=5.0)
        t.observe(face_visible=True, person_visible=True, at=0.0)
        t.observe(face_visible=False, person_visible=False, at=10.0)
        events = t.observe(face_visible=False, person_visible=True, at=12.0)
        assert kinds(events) == [EVENT_RETURNED]
        assert t.state is PresenceState.SILHOUETTE

    def test_away_duration_tracks_continuous_absence(self):
        t = PresenceTracker("learner-1", absence_grace_s=2.0)
        t.observe(face_visible=True, person_visible=True, at=0.0)
        t.observe(face_visible=False, person_visible=False, at=5.0)
        assert t.state is PresenceState.ABSENT
        assert t.away_duration(5.0) == 0.0
        assert t.away_duration(8.5) == 3.5
        t.observe(face_visible=True, person_visible=True, at=9.0)
        assert t.away_duration(9.0) == 0.0

    def test_time_in_state(self):
        t = PresenceTracker("learner-1")
        assert t.time_in_state(3.0) == 0.0
        t.observe(face_visible=True, person_visible=True, at=1.0)
        assert t.time_in_state(4.5) == 3.5


class TestMonitor:
    def test_per_participant_isolation(self):
        m = PresenceMonitor(absence_grace_s=5.0)
        m.observe("a", face_visible=True, person_visible=True, at=0.0)
        m.observe("b", face_visible=False, person_visible=True, at=0.0)
        assert m.state_of("a") is PresenceState.PRESENT
        assert m.state_of("b") is PresenceState.SILHOUETTE
        assert m.snapshot() == {"a": "present", "b": "silhouette"}

    def test_all_absent_and_absent_listing(self):
        m = PresenceMonitor(absence_grace_s=2.0)
        m.observe("a", face_visible=True, person_visible=True, at=0.0)
        m.observe("b", face_visible=True, person_visible=True, at=0.0)
        assert m.all_absent() is False
        m.observe("a", face_visible=False, person_visible=False, at=10.0)
        assert m.all_absent() is False
        m.observe("b", face_visible=False, person_visible=False, at=10.0)
        assert m.all_absent() is True
        assert sorted(m.absent_participants()) == ["a", "b"]

    def test_unknown_participant_is_absent(self):
        m = PresenceMonitor()
        assert m.state_of("ghost") is PresenceState.ABSENT

    def test_remove_participant(self):
        m = PresenceMonitor()
        m.observe("a", face_visible=True, person_visible=True, at=0.0)
        m.remove("a")
        assert m.snapshot() == {}

    def test_event_serialization(self):
        m = PresenceMonitor()
        events = m.observe("a", face_visible=True, person_visible=True, at=1.0)
        d = events[0].to_dict()
        assert d == {
            "participant_id": "a",
            "kind": EVENT_PRESENT,
            "state": "present",
            "at": 1.0,
            "detail": "face visible",
        }
