"""Teaching policy tests: Theodore (AI-led) and self-teaching modes."""

from aoep_webcam_vision.modes import (
    ACTION_LOG,
    ACTION_NUDGE,
    ACTION_PAUSE,
    ACTION_RESUME,
    ACTION_SAY,
    LINE_PAUSE_EMPTY_ROOM,
    LINE_WELCOME_BACK,
    SelfTeachingPolicy,
    TheodoreTeachingPolicy,
)
from aoep_webcam_vision.presence import PresenceEvent, PresenceState


def ev(pid, kind, state, at, detail=""):
    return PresenceEvent(participant_id=pid, kind=kind, state=state, at=at, detail=detail)


def kinds(actions):
    return [a.kind for a in actions]


class TestTheodoreSolo:
    def test_absence_pauses_and_speaks_once(self):
        policy = TheodoreTeachingPolicy()
        actions = policy.on_event(ev("solo", "user_absent", PresenceState.ABSENT, 10.0))
        assert policy.paused is True
        assert kinds(actions) == [ACTION_PAUSE, ACTION_SAY, ACTION_LOG]
        assert actions[1].text == LINE_PAUSE_EMPTY_ROOM
        # A second absence event (e.g. another tracker reporting) doesn't
        # double-pause.
        again = policy.on_event(ev("solo", "user_absent", PresenceState.ABSENT, 20.0))
        assert ACTION_PAUSE not in kinds(again)

    def test_return_resumes_and_welcomes_back(self):
        policy = TheodoreTeachingPolicy()
        policy.on_event(ev("solo", "user_absent", PresenceState.ABSENT, 10.0))
        actions = policy.on_event(
            ev("solo", "user_returned", PresenceState.PRESENT, 30.0)
        )
        assert policy.paused is False
        assert kinds(actions) == [ACTION_RESUME, ACTION_SAY]
        assert actions[1].text == LINE_WELCOME_BACK

    def test_long_absence_offers_recap(self):
        policy = TheodoreTeachingPolicy(recap_after_s=60.0)
        policy.on_event(ev("solo", "user_absent", PresenceState.ABSENT, 0.0))
        actions = policy.on_event(
            ev("solo", "user_returned", PresenceState.PRESENT, 300.0)
        )
        say = [a for a in actions if a.kind == ACTION_SAY][0]
        assert "5 minutes" in say.text
        assert "recap" in say.text.lower()

    def test_silhouette_nudge_after_prolonged_stretch(self):
        policy = TheodoreTeachingPolicy(silhouette_nudge_after_s=45.0)
        policy.on_event(ev("solo", "user_silhouette", PresenceState.SILHOUETTE, 0.0))
        assert policy.tick(now=30.0) == []
        nudges = policy.tick(now=50.0)
        assert kinds(nudges) == [ACTION_NUDGE]
        assert nudges[0].participant_id == "solo"
        # One nudge per silhouette stretch.
        assert policy.tick(now=90.0) == []
        # Face returns -> the stretch resets.
        policy.on_event(ev("solo", "user_present", PresenceState.PRESENT, 95.0))
        policy.on_event(ev("solo", "user_silhouette", PresenceState.SILHOUETTE, 100.0))
        assert policy.tick(now=140.0) == []
        assert kinds(policy.tick(now=146.0)) == [ACTION_NUDGE]


class TestTheodoreGroup:
    def test_group_continues_while_one_learner_present(self):
        policy = TheodoreTeachingPolicy()
        policy.on_event(ev("a", "user_present", PresenceState.PRESENT, 0.0))
        policy.on_event(ev("b", "user_present", PresenceState.PRESENT, 0.0))
        # One learner stepping away never pauses a group class.
        policy.on_event(ev("a", "user_absent", PresenceState.ABSENT, 5.0))
        assert policy.paused is False
        # Only when the room is fully empty does Theodore pause.
        policy.on_event(ev("b", "user_absent", PresenceState.ABSENT, 7.0))
        assert policy.paused is True

    def test_group_return_uses_name(self):
        policy = TheodoreTeachingPolicy()
        policy.on_event(ev("a", "user_present", PresenceState.PRESENT, 0.0))
        policy.on_event(ev("b", "user_present", PresenceState.PRESENT, 0.0))
        policy.on_event(ev("b", "user_absent", PresenceState.ABSENT, 5.0))
        actions = policy.on_event(
            ev("b", "user_returned", PresenceState.SILHOUETTE, 20.0),
            participant_names={"b": "Maya"},
        )
        say = [a for a in actions if a.kind == ACTION_SAY][0]
        assert "Maya" in say.text

    def test_present_while_paused_resumes_defensively(self):
        policy = TheodoreTeachingPolicy()
        policy.on_event(ev("a", "user_absent", PresenceState.ABSENT, 0.0))
        assert policy.paused is True
        actions = policy.on_event(ev("a", "user_present", PresenceState.PRESENT, 3.0))
        assert policy.paused is False
        assert kinds(actions) == [ACTION_RESUME]


class TestSelfTeaching:
    def test_focus_and_away_time_accrue(self):
        policy = SelfTeachingPolicy()
        policy.on_event(ev("me", "user_present", PresenceState.PRESENT, 0.0))
        policy.tick(now=60.0)  # 60s focused
        policy.on_event(ev("me", "user_absent", PresenceState.ABSENT, 60.0))
        policy.tick(now=90.0)  # 30s away
        stats = policy.stats(now=90.0)
        assert stats["focused_s"] == 60.0
        assert stats["away_s"] == 30.0
        assert stats["away_count"] == 1
        assert stats["mode"] == "self"

    def test_silhouette_counts_in_room_not_focused(self):
        policy = SelfTeachingPolicy()
        policy.on_event(ev("me", "user_silhouette", PresenceState.SILHOUETTE, 0.0))
        stats = policy.stats(now=30.0)
        assert stats["in_room_s"] == 30.0
        assert stats["focused_s"] == 0.0

    def test_recap_offer_after_long_absence(self):
        policy = SelfTeachingPolicy(recap_after_s=60.0)
        policy.on_event(ev("me", "user_present", PresenceState.PRESENT, 0.0))
        policy.on_event(ev("me", "user_absent", PresenceState.ABSENT, 10.0))
        actions = policy.on_event(ev("me", "user_returned", PresenceState.PRESENT, 200.0))
        assert kinds(actions) == [ACTION_NUDGE]
        assert "3 minutes" in actions[0].text

    def test_short_absence_is_quiet(self):
        policy = SelfTeachingPolicy(recap_after_s=120.0)
        policy.on_event(ev("me", "user_present", PresenceState.PRESENT, 0.0))
        policy.on_event(ev("me", "user_absent", PresenceState.ABSENT, 10.0))
        actions = policy.on_event(ev("me", "user_returned", PresenceState.PRESENT, 40.0))
        assert actions == []
