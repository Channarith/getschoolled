"""Simulated meeting transport: inject chat + video events for offline labs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from aoep_shared.bridges.session import (
    DisclosureNotice,
    Direction,
    FakeTransport,
    LiveKitEndpoint,
    TrackKind,
)
from aoep_shared.bridges.meeting import MeetingRef


@dataclass
class InboundChat:
    author: str
    text: str


@dataclass
class VideoFrameEvent:
    """Synthetic perception signal from the meeting video feed."""

    student_id: str
    attention: float  # 0..1
    hand_raised: bool = False
    looking_away: bool = False


class SimulatedMeetingTransport(FakeTransport):
    """FakeTransport plus inbound chat/video injection for agent labs."""

    def __init__(
        self,
        *,
        on_inbound_chat: Optional[Callable[[InboundChat], None]] = None,
        on_video_frame: Optional[Callable[[VideoFrameEvent], None]] = None,
    ) -> None:
        super().__init__()
        self._on_chat = on_inbound_chat
        self._on_video = on_video_frame
        self.inbound_chat: List[InboundChat] = []
        self.video_frames: List[VideoFrameEvent] = []

    def inject_chat(self, text: str, *, author: str = "student") -> None:
        msg = InboundChat(author=author, text=text)
        self.inbound_chat.append(msg)
        if self._on_chat:
            self._on_chat(msg)

    def inject_video(self, event: VideoFrameEvent) -> None:
        self.video_frames.append(event)
        if self._on_video:
            self._on_video(event)

    def drain_chat_script(self, script: List[tuple[str, str]]) -> None:
        """(author, text) pairs fired as if read from meeting chat."""
        for author, text in script:
            self.inject_chat(text, author=author)


@dataclass
class AgentEvent:
    agent: str
    kind: str
    detail: str
    meta: dict = field(default_factory=dict)
