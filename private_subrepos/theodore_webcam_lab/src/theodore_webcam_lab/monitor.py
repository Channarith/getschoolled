from __future__ import annotations

from dataclasses import dataclass

from .models import ClassMode, MonitoringDecision, MonitoringEvent, WebcamFrameInput


@dataclass
class _SessionMonitorState:
    consecutive_absent_frames: int = 0
    was_absent: bool = False
    last_silhouette: bool = False


class WebcamSessionMonitor:
    """Classroom webcam state monitor for solo and group lessons."""

    def __init__(
        self,
        *,
        absence_frame_threshold: int = 3,
        silhouette_foreground_threshold: float = 0.18,
        silhouette_motion_threshold: float = 0.03,
        min_attention: float = 0.28,
    ) -> None:
        self.absence_frame_threshold = max(1, absence_frame_threshold)
        self.silhouette_foreground_threshold = silhouette_foreground_threshold
        self.silhouette_motion_threshold = silhouette_motion_threshold
        self.min_attention = min_attention
        self._session_state: dict[str, _SessionMonitorState] = {}

    def analyze(self, frame: WebcamFrameInput) -> MonitoringDecision:
        state = self._session_state.setdefault(frame.session_id, _SessionMonitorState())
        events: list[MonitoringEvent] = []

        expected = frame.expected_participants if frame.class_mode is ClassMode.group else 1
        active_participants = sum(
            1 for p in frame.participants if p.present and p.attention >= self.min_attention
        )
        face_count = frame.face_count if frame.face_count is not None else sum(
            1 for p in frame.participants if p.present
        )

        silhouette_detected = (
            face_count == 0
            and frame.foreground_ratio >= self.silhouette_foreground_threshold
            and frame.motion_ratio >= self.silhouette_motion_threshold
        )
        if silhouette_detected and not state.last_silhouette:
            events.append(
                MonitoringEvent(
                    code="silhouette_detected",
                    severity="medium",
                    message="Motion silhouette detected but no face is visible.",
                )
            )
        elif not silhouette_detected and state.last_silhouette:
            events.append(
                MonitoringEvent(
                    code="silhouette_cleared",
                    severity="info",
                    message="Silhouette cleared.",
                )
            )
        state.last_silhouette = silhouette_detected

        absent_now = active_participants == 0 and not silhouette_detected
        if absent_now:
            state.consecutive_absent_frames += 1
        else:
            state.consecutive_absent_frames = 0

        user_absent = state.was_absent
        if absent_now and state.consecutive_absent_frames >= self.absence_frame_threshold:
            if not state.was_absent:
                events.append(
                    MonitoringEvent(
                        code="user_absent",
                        severity="high",
                        message="No learner presence detected for consecutive frames.",
                    )
                )
            state.was_absent = True
            user_absent = True
        elif state.was_absent and active_participants > 0:
            state.was_absent = False
            user_absent = False
            events.append(
                MonitoringEvent(
                    code="user_returned",
                    severity="info",
                    message="Learner presence has resumed.",
                )
            )

        group_understaffed = (
            frame.class_mode is ClassMode.group and active_participants < expected
        )
        if group_understaffed:
            events.append(
                MonitoringEvent(
                    code="group_understaffed",
                    severity="medium",
                    message=f"Only {active_participants}/{expected} learners appear active.",
                )
            )

        return MonitoringDecision(
            session_id=frame.session_id,
            class_mode=frame.class_mode,
            active_participants=active_participants,
            expected_participants=expected,
            silhouette_detected=silhouette_detected,
            user_absent=user_absent,
            group_understaffed=group_understaffed,
            events=events,
        )
