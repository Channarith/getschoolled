"""Bridge session engine: the platform-agnostic media-bridging orchestration.

The teaching brain (apps/agent-runtime) already runs inside a LiveKit room. A
bridge moves an external meeting's media in and out of that room. The actual
vendor media plumbing (Zoom/Teams/Meet SDKs) is isolated behind the
:class:`MediaTransport` boundary; this module owns everything platform-agnostic:

- the join -> bridge -> leave lifecycle state machine,
- which tracks to bridge in which direction (driven by capabilities),
- routing meeting chat questions to the Tutor,
- and surfacing the recording / data-retention disclosure the platforms' ToS
  require for automated bots.

Because the transport is injectable, the full orchestration runs and is tested
end-to-end with an in-memory :class:`FakeTransport`; only the native SDK call is
unavailable offline.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol, runtime_checkable

from .meeting import MeetingRef
from .registry import BridgeCapabilities


class TrackKind(str, enum.Enum):
    AUDIO = "audio"
    VIDEO = "video"
    SCREEN = "screen"


class Direction(str, enum.Enum):
    MEETING_TO_ROOM = "meeting_to_room"   # remote participants -> teaching brain
    ROOM_TO_MEETING = "room_to_meeting"   # teaching brain (agent) -> meeting


class BridgeState(str, enum.Enum):
    NEW = "new"
    JOINING = "joining"
    BRIDGING = "bridging"
    LEAVING = "leaving"
    CLOSED = "closed"
    FAILED = "failed"


@dataclass(frozen=True)
class LiveKitEndpoint:
    """Where the teaching brain's room lives + the token to join it."""

    room: str
    url: str = ""
    token: str = ""
    identity: str = "aoep-bridge"


@dataclass(frozen=True)
class DisclosureNotice:
    """Recording / data-retention notice surfaced into the meeting."""

    text: str
    recording: bool = False
    retention_days: Optional[int] = None


@dataclass(frozen=True)
class BridgedTrack:
    kind: TrackKind
    direction: Direction


@runtime_checkable
class MediaTransport(Protocol):
    """Vendor-specific media plumbing. One implementation per platform SDK.

    Implementations join the meeting, wire a single media track in one
    direction, deliver chat, and tear down. Everything they do is driven by the
    :class:`BridgeSession` so the platform-agnostic policy lives in one place.
    """

    def open(self, *, meeting: MeetingRef, room: LiveKitEndpoint) -> None: ...

    def bridge_track(self, kind: TrackKind, direction: Direction) -> None: ...

    def announce(self, notice: DisclosureNotice) -> None: ...

    def send_chat(self, text: str) -> None: ...

    def close(self) -> None: ...


def _planned_tracks(caps: BridgeCapabilities) -> List[BridgedTrack]:
    """Which tracks to bridge, in which direction, for these capabilities.

    Audio is always bidirectional (students <-> AI teacher). Students' video and
    screen-share flow into the room so perception/Tutor can use them; the agent
    publishes its screen-share (slides/avatar) back to the meeting.
    """
    plan: List[BridgedTrack] = [
        BridgedTrack(TrackKind.AUDIO, Direction.MEETING_TO_ROOM),
        BridgedTrack(TrackKind.AUDIO, Direction.ROOM_TO_MEETING),
    ]
    if caps.video:
        plan.append(BridgedTrack(TrackKind.VIDEO, Direction.MEETING_TO_ROOM))
    if caps.screen_share:
        plan.append(BridgedTrack(TrackKind.SCREEN, Direction.MEETING_TO_ROOM))
        plan.append(BridgedTrack(TrackKind.SCREEN, Direction.ROOM_TO_MEETING))
    return plan


def default_disclosure(
    platform_label: str, *, recording: bool, retention_days: Optional[int]
) -> DisclosureNotice:
    bits = [
        f"This session is assisted by an AI teacher joining via the {platform_label} bridge."
    ]
    if recording:
        bits.append("It is being recorded.")
    if retention_days is not None:
        bits.append(f"Media/transcripts are retained for {retention_days} days.")
    bits.append("See the Transparency page for details.")
    return DisclosureNotice(text=" ".join(bits), recording=recording, retention_days=retention_days)


class BridgeSession:
    """Owns one external-meeting <-> LiveKit-room bridge.

    Lifecycle: ``start()`` joins the meeting, announces the disclosure, and wires
    every planned track through the transport; ``stop()`` tears it down. Chat
    questions from the meeting are routed to a Tutor callback (if chat-capable).
    """

    def __init__(
        self,
        *,
        capabilities: BridgeCapabilities,
        meeting: MeetingRef,
        room: LiveKitEndpoint,
        transport: MediaTransport,
        recording: bool = False,
        retention_days: Optional[int] = None,
        tutor_router: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.capabilities = capabilities
        self.meeting = meeting
        self.room = room
        self._transport = transport
        self._recording = recording
        self._retention_days = retention_days
        self._tutor_router = tutor_router
        self.state = BridgeState.NEW
        self.bridged: List[BridgedTrack] = []
        self.disclosure: Optional[DisclosureNotice] = None
        self.chat_log: List[str] = []

    def start(self) -> "BridgeSession":
        if self.state is not BridgeState.NEW:
            raise RuntimeError(f"session already started (state={self.state.value})")
        self.state = BridgeState.JOINING
        try:
            self._transport.open(meeting=self.meeting, room=self.room)
            self.disclosure = default_disclosure(
                self.capabilities.platform.value,
                recording=self._recording,
                retention_days=self._retention_days,
            )
            self._transport.announce(self.disclosure)
            for track in _planned_tracks(self.capabilities):
                self._transport.bridge_track(track.kind, track.direction)
                self.bridged.append(track)
            self.state = BridgeState.BRIDGING
        except Exception:
            self.state = BridgeState.FAILED
            raise
        return self

    def route_chat_question(self, text: str) -> None:
        """A meeting chat message -> the Tutor agent (chat-capable platforms)."""
        if not self.capabilities.chat:
            raise RuntimeError(f"{self.capabilities.platform.value} bridge has no chat capability")
        self.chat_log.append(text)
        if self._tutor_router is not None:
            self._tutor_router(text)

    def post_to_chat(self, text: str) -> None:
        """Send a message (e.g. the Tutor's answer) into the meeting chat."""
        self._transport.send_chat(text)

    def stop(self) -> None:
        if self.state in (BridgeState.CLOSED, BridgeState.NEW):
            return
        self.state = BridgeState.LEAVING
        self._transport.close()
        self.state = BridgeState.CLOSED

    def status(self) -> dict:
        return {
            "platform": self.capabilities.platform.value,
            "runtime": self.capabilities.runtime,
            "state": self.state.value,
            "meeting_id": self.meeting.meeting_id,
            "room": self.room.room,
            "bridged_tracks": [
                {"kind": t.kind.value, "direction": t.direction.value} for t in self.bridged
            ],
            "disclosure": (self.disclosure.text if self.disclosure else None),
            "recording": self._recording,
            "retention_days": self._retention_days,
        }


@dataclass
class _Call:
    op: str
    args: dict = field(default_factory=dict)


class FakeTransport:
    """In-memory transport that records every call.

    Stands in for a real platform SDK so the bridge engine can be exercised
    end-to-end in tests and offline demos. It is a faithful ``MediaTransport``.
    """

    def __init__(self) -> None:
        self.calls: List[_Call] = []
        self.opened = False
        self.closed = False
        self.chat_sent: List[str] = []

    def open(self, *, meeting: MeetingRef, room: LiveKitEndpoint) -> None:
        self.opened = True
        self.calls.append(_Call("open", {"meeting_id": meeting.meeting_id, "room": room.room}))

    def bridge_track(self, kind: TrackKind, direction: Direction) -> None:
        self.calls.append(_Call("bridge_track", {"kind": kind.value, "direction": direction.value}))

    def announce(self, notice: DisclosureNotice) -> None:
        self.calls.append(_Call("announce", {"recording": notice.recording}))

    def send_chat(self, text: str) -> None:
        self.chat_sent.append(text)
        self.calls.append(_Call("send_chat", {"text": text}))

    def close(self) -> None:
        self.closed = True
        self.calls.append(_Call("close", {}))
