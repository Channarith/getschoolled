"""Group-class webcam recognition lab helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from aoep_shared.meeting_agents.simulation import VideoFrameEvent

from .presence import PresenceDecision, WebcamObservation, WebcamPresenceAnalyzer


@dataclass(frozen=True)
class GroupPresenceReport:
    room_id: str
    decision: PresenceDecision

    def endpoint_path(self) -> str:
        return f"/api/live-rooms/{self.room_id}/presence-report"

    def payload(self) -> dict:
        return self.decision.to_presence_payload()

    def to_video_event(self) -> VideoFrameEvent:
        return VideoFrameEvent(
            student_id=self.decision.participant_id,
            attention=self.decision.attention_score
            if self.decision.present else 0.0,
            looking_away=not self.decision.verified_live,
        )


@dataclass
class GroupRecognitionLabResult:
    room_id: str
    reports: list[GroupPresenceReport] = field(default_factory=list)

    def payloads(self) -> list[dict]:
        return [report.payload() for report in self.reports]

    def video_events(self) -> list[VideoFrameEvent]:
        return [report.to_video_event() for report in self.reports]

    def summary(self) -> dict:
        return {
            "room_id": self.room_id,
            "ticks": len(self.reports),
            "verified_live": sum(
                1 for report in self.reports if report.decision.verified_live
            ),
            "silhouette_only": sum(
                1
                for report in self.reports
                if report.decision.reason == "silhouette_without_face"
            ),
            "absent": sum(
                1 for report in self.reports if not report.decision.present
            ),
        }


def run_group_recognition_lab(
    *,
    room_id: str,
    observations: Iterable[WebcamObservation],
    analyzer: WebcamPresenceAnalyzer | None = None,
) -> GroupRecognitionLabResult:
    """Analyze group-class observations and build replayable presence reports."""

    engine = analyzer or WebcamPresenceAnalyzer()
    reports = [
        GroupPresenceReport(room_id=room_id, decision=engine.analyze(obs))
        for obs in observations
    ]
    return GroupRecognitionLabResult(room_id=room_id, reports=reports)
