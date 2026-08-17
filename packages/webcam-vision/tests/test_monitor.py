"""WebcamMonitor tests with stub face/silhouette pipelines (no OpenCV needed)."""

from dataclasses import dataclass

from aoep_webcam_vision.monitor import WebcamMonitor
from aoep_webcam_vision.presence import (
    EVENT_ABSENT,
    EVENT_RETURNED,
    PresenceMonitor,
    PresenceState,
)
from aoep_webcam_vision.silhouette import PersonDetection


@dataclass
class StubFaceObservation:
    attention_score: float = 0.0
    gaze_frontal: float = 0.0
    expression: str | None = None
    matched_student_id: str | None = None


class StubSilhouette:
    """Stands in for SilhouetteDetector; scripted person_visible answers."""

    def __init__(self, answers):
        self._answers = list(answers)

    def detect(self, image):
        if not self._answers:
            return []
        visible = self._answers.pop(0)
        if not visible:
            return []
        return [
            PersonDetection(
                bbox=(10, 10, 80, 120), confidence=0.7, source="motion",
                frame_size=(320, 240),
            )
        ]


def face_analyzer(observations):
    def _analyze(participant_id, image):
        return observations
    return _analyze


class TestAnalyzeFrame:
    def test_face_observation_marks_present(self):
        monitor = WebcamMonitor(
            silhouette_detector=None,
            face_analyzer=face_analyzer([StubFaceObservation(attention_score=0.8)]),
        )
        analysis = monitor.analyze_frame("local", b"frame", at=0.0)
        assert analysis.state is PresenceState.PRESENT
        assert analysis.signals.face_visible is True
        assert analysis.signals.person_visible is True
        assert analysis.signals.attention == 0.8
        assert [e.kind for e in analysis.events] == ["user_present"]

    def test_silhouette_only_marks_person_without_face(self):
        monitor = WebcamMonitor(
            silhouette_detector=StubSilhouette([True]),
            face_analyzer=face_analyzer([]),
        )
        analysis = monitor.analyze_frame("local", b"frame", at=0.0)
        assert analysis.state is PresenceState.SILHOUETTE
        assert analysis.signals.face_visible is False
        assert analysis.signals.person_visible is True
        assert len(analysis.signals.silhouettes) == 1

    def test_empty_frame_stays_absent_silently(self):
        monitor = WebcamMonitor(
            silhouette_detector=StubSilhouette([False]),
            face_analyzer=face_analyzer([]),
        )
        analysis = monitor.analyze_frame("local", b"frame", at=0.0)
        assert analysis.state is PresenceState.ABSENT
        assert analysis.events == []

    def test_absence_event_after_grace(self):
        # No face pipeline and no silhouettes: a seeded-present participant who
        # stops producing detections is declared absent after the grace period.
        monitor = WebcamMonitor(
            silhouette_detector=None,
            face_analyzer=None,
            presence=PresenceMonitor(absence_grace_s=5.0),
        )
        monitor.presence.observe("local", face_visible=True, person_visible=True, at=0.0)
        analysis = monitor.analyze_frame("local", b"frame", at=10.0)
        assert analysis.state is PresenceState.ABSENT
        assert [e.kind for e in analysis.events] == [EVENT_ABSENT]

    def test_best_face_wins_for_attention(self):
        monitor = WebcamMonitor(
            silhouette_detector=None,
            face_analyzer=face_analyzer([
                StubFaceObservation(attention_score=0.3),
                StubFaceObservation(attention_score=0.9, matched_student_id="stu-7"),
            ]),
        )
        analysis = monitor.analyze_frame("local", b"frame", at=0.0)
        assert analysis.signals.face_count == 2
        assert analysis.signals.attention == 0.9
        assert analysis.signals.matched_student_id == "stu-7"

    def test_no_face_pipeline_runs_on_silhouettes_alone(self):
        monitor = WebcamMonitor(silhouette_detector=StubSilhouette([True]))
        analysis = monitor.analyze_frame("local", b"frame", at=0.0)
        assert analysis.signals.face_count == 0
        assert analysis.state is PresenceState.SILHOUETTE


class TestVisionProviderWiring:
    def test_consent_gated_provider_path(self):
        class StubVision:
            def __init__(self):
                self.calls = []

            def analyze_image(self, image, *, consented_student_ids):
                self.calls.append((image, tuple(consented_student_ids)))
                return [StubFaceObservation(attention_score=0.5)]

        vision = StubVision()
        monitor = WebcamMonitor.with_vision_provider(
            vision, consented_student_ids=["stu-1"]
        )
        analysis = monitor.analyze_frame("local", b"frame", at=0.0)
        assert analysis.signals.face_visible is True
        assert vision.calls == [(b"frame", ("stu-1",))]

    def test_unimplemented_backend_degrades_to_silhouette_only(self):
        class OfflineVision:
            def analyze_image(self, image, *, consented_student_ids):
                raise NotImplementedError("no model here")

        monitor = WebcamMonitor.with_vision_provider(
            OfflineVision(), silhouette_detector=StubSilhouette([True])
        )
        analysis = monitor.analyze_frame("local", b"frame", at=0.0)
        assert analysis.signals.face_visible is False
        assert analysis.state is PresenceState.SILHOUETTE

    def test_group_snapshot_covers_all_participants(self):
        monitor = WebcamMonitor(silhouette_detector=None, face_analyzer=None)
        monitor.presence.observe("a", face_visible=True, person_visible=True, at=0.0)
        monitor.presence.observe("b", face_visible=False, person_visible=True, at=0.0)
        monitor.analyze_frame("a", b"f1", at=1.0)
        assert monitor.snapshot() == {"a": "present", "b": "silhouette"}
        assert EVENT_RETURNED not in [
            e.kind for e in monitor.analyze_frame("b", b"f2", at=2.0).events
        ]
