"""End-to-end session harness tests: frames in -> events + actions out."""

from dataclasses import dataclass

from aoep_webcam_vision.monitor import WebcamMonitor
from aoep_webcam_vision.presence import PresenceMonitor
from aoep_webcam_vision.session import (
    MODE_SELF,
    MODE_THEODORE,
    WebcamTeachingSession,
)
from aoep_webcam_vision.silhouette import PersonDetection
from aoep_webcam_vision.xai_voice import VoiceAgentConfig, XAIVoiceAgent


@dataclass
class StubFace:
    attention_score: float = 0.7
    gaze_frontal: float = 0.8
    expression: str | None = "neutral"
    matched_student_id: str | None = None


class Script:
    """Scripted per-frame (faces, person_visible) answers for a participant."""

    def __init__(self):
        self.faces = []
        self.person = []

    def push(self, *, face: bool, person: bool):
        self.faces.append([StubFace()] if face else [])
        self.person.append(person)

    def analyzer(self):
        return lambda pid, image: self.faces.pop(0) if self.faces else []

    def detector(self):
        person = self.person
        class _Det:
            def detect(self, image):
                if not person or not person.pop(0):
                    return []
                return [PersonDetection((0, 0, 50, 100), 0.6, "motion", (320, 240))]
        return _Det()


def build(mode, script, **kwargs):
    monitor = WebcamMonitor(
        silhouette_detector=script.detector(),
        face_analyzer=script.analyzer(),
        presence=PresenceMonitor(silhouette_grace_s=5.0, absence_grace_s=10.0),
    )
    if mode == MODE_THEODORE:
        return WebcamTeachingSession.solo_theodore(monitor=monitor, **kwargs)
    return WebcamTeachingSession.self_teaching(monitor=monitor, **kwargs)


class TestSoloTheodore:
    def test_full_leave_and_return_arc(self):
        script = Script()
        script.push(face=True, person=True)          # t=0 present
        script.push(face=False, person=True)         # t=3 (within grace)
        script.push(face=False, person=True)         # t=6 -> silhouette
        for _ in range(3):
            script.push(face=False, person=False)    # t=9, t=12, t=16 -> absent
        script.push(face=True, person=True)          # t=20 -> returned
        session = build(MODE_THEODORE, script)

        u0 = session.ingest_frame("local", b"f", at=0.0)
        assert u0.analysis.state.value == "present"

        u1 = session.ingest_frame("local", b"f", at=3.0)
        assert u1.events == []  # anti-flicker: still present

        u2 = session.ingest_frame("local", b"f", at=6.0)
        assert [e.kind for e in u2.events] == ["user_silhouette"]

        assert session.ingest_frame("local", b"f", at=9.0).events == []
        assert session.ingest_frame("local", b"f", at=12.0).events == []
        u5 = session.ingest_frame("local", b"f", at=16.0)
        assert [e.kind for e in u5.events] == ["user_absent"]
        assert [a.kind for a in u5.actions] == ["pause", "say", "log"]
        assert session.stats()["paused"] is True

        u6 = session.ingest_frame("local", b"f", at=20.0)
        assert [e.kind for e in u6.events] == ["user_returned", "user_present"]
        assert [a.kind for a in u6.actions] == ["resume", "say"]
        assert session.spoken_lines(u6) == [
            "Welcome back! Let's pick up right where we left off."
        ]
        assert session.stats()["paused"] is False

    def test_silhouette_nudge_flows_through_tick(self):
        script = Script()
        script.push(face=False, person=True)
        session = build(MODE_THEODORE, script)
        session.ingest_frame("local", b"f", at=0.0)
        nudges = session.tick(at=100.0)
        assert [a.kind for a in nudges] == ["nudge"]
        assert "can't see your face" in nudges[0].text

    def test_voice_availability(self):
        script = Script()
        session = build(MODE_THEODORE, script, voice=None)
        assert session.voice_available() is False
        session = build(
            MODE_THEODORE, script,
            voice=XAIVoiceAgent(VoiceAgentConfig(api_key="k")),
        )
        assert session.voice_available() is True


class TestGroupTheodore:
    def test_group_pause_only_when_room_empty(self):
        faces = {"a": [StubFace()], "b": [StubFace()]}

        def analyzer(pid, image):
            return faces.get(pid, [])

        monitor = WebcamMonitor(
            silhouette_detector=None,
            face_analyzer=analyzer,
            presence=PresenceMonitor(absence_grace_s=5.0),
        )
        session = WebcamTeachingSession.group_theodore(
            ["a", "b"], monitor=monitor,
            participant_names={"a": "Ana", "b": "Bo"},
        )
        assert session.presence_snapshot() == {"a": "absent", "b": "absent"}

        session.ingest_frame("a", b"f", at=0.0)
        session.ingest_frame("b", b"f", at=0.0)
        assert session.presence_snapshot() == {"a": "present", "b": "present"}

        # "a" walks away: class continues.
        faces["a"] = []
        ua = session.ingest_frame("a", b"f", at=10.0)
        assert [e.kind for e in ua.events] == ["user_absent"]
        assert session.policy.paused is False

        # "b" walks away too: empty room -> pause.
        faces["b"] = []
        ub = session.ingest_frame("b", b"f", at=11.0)
        assert [e.kind for e in ub.events] == ["user_absent"]
        assert session.policy.paused is True

        # "Bo" returns: resume + named welcome.
        faces["b"] = [StubFace()]
        ub2 = session.ingest_frame("b", b"f", at=20.0)
        assert "user_returned" in [e.kind for e in ub2.events]
        says = [a.text for a in ub2.actions if a.kind == "say"]
        assert any("Bo" in line for line in says)


class TestSelfTeaching:
    def test_focus_stats_and_recap_offer(self):
        script = Script()
        script.push(face=True, person=True)    # t=0 present
        script.push(face=True, person=True)    # t=50 still present
        script.push(face=False, person=False)  # t=55 within grace, no event
        script.push(face=False, person=False)  # t=61 -> absent (gap 11 >= 10)
        script.push(face=True, person=True)    # t=241 -> returned after 180s
        session = build(MODE_SELF, script)

        session.ingest_frame("local", b"f", at=0.0)
        session.ingest_frame("local", b"f", at=50.0)
        session.ingest_frame("local", b"f", at=55.0)
        u1 = session.ingest_frame("local", b"f", at=61.0)
        assert [e.kind for e in u1.events] == ["user_absent"]

        u2 = session.ingest_frame("local", b"f", at=241.0)
        nudges = [a for a in u2.actions if a.kind == "nudge"]
        assert nudges and "3 minutes" in nudges[0].text

        stats = session.stats(at=241.0)
        assert stats["mode"] == "self"
        # Focus accrues until absence is DECLARED (grace-period semantics), so
        # the full 0->61s span counts as focused; 61->241s counts as away.
        assert stats["focused_s"] == 61.0
        assert stats["away_s"] == 180.0
        assert stats["away_count"] == 1

    def test_update_serialization(self):
        script = Script()
        script.push(face=True, person=True)
        session = build(MODE_SELF, script)
        update = session.ingest_frame("local", b"f", at=0.0)
        d = update.to_dict()
        assert d["participant_id"] == "local"
        assert d["state"] == "present"
        assert d["events"][0]["kind"] == "user_present"
