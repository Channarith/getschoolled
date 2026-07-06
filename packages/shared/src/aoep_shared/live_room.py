"""Salareen Live Room — multi-user teaching sessions (Bigo/Mico-style).

Built-in group-class rooms where Theodore (AI host) teaches up to 3, 5, or 8
learners in a synchronized grid (4, 6, or 9 total seats including the host).
Room state (participants, chat, raise-hand, mute, slide sync, recording) is
managed here; the orchestrator exposes it over HTTP for web and mobile clients.
LiveKit tokens are minted at join time for WebRTC when a media server is
configured.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

ROOM_SIZES: tuple = (4, 6, 9)
AI_HOST_ID = "theodore-ai"
AI_HOST_NAME = "Theodore (AI Host)"
AI_HOST_ROLE = "host"
LEARNER_ROLE = "learner"

RECORDING_IDLE = "idle"
RECORDING_ACTIVE = "recording"
RECORDING_STOPPED = "stopped"


class LiveRoomError(ValueError):
    """Invalid live-room request (maps to HTTP 400)."""


class RoomFullError(LiveRoomError):
    """No learner seats left in this room."""


class NotInRoomError(LiveRoomError):
    """Participant is not in this room."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _now().isoformat()


def learner_capacity(room_size: int) -> int:
    """Learner seats = total room size minus the AI host."""
    return max(0, int(room_size) - 1)


def validate_room_size(room_size: int) -> int:
    size = int(room_size)
    if size not in ROOM_SIZES:
        raise LiveRoomError(f"room_size must be one of {', '.join(str(s) for s in ROOM_SIZES)}")
    return size


@dataclass
class ChatMessage:
    id: str
    from_id: str
    from_name: str
    text: str
    sent_at: str = ""

    def __post_init__(self) -> None:
        self.text = (self.text or "").strip()
        if not self.text:
            raise LiveRoomError("chat message cannot be empty")
        if not self.sent_at:
            self.sent_at = _ts()


@dataclass
class Participant:
    id: str
    name: str
    role: str = LEARNER_ROLE
    identity: str = ""
    muted: bool = False
    muted_by_host: bool = False
    hand_raised: bool = False
    can_publish: bool = True
    joined_at: str = ""

    def __post_init__(self) -> None:
        self.name = (self.name or "").strip()
        if not self.name:
            raise LiveRoomError("participant name is required")
        if self.role not in (AI_HOST_ROLE, LEARNER_ROLE):
            raise LiveRoomError(f"invalid role {self.role!r}")
        if not self.identity:
            self.identity = self.id
        if not self.joined_at:
            self.joined_at = _ts()

    @property
    def is_host(self) -> bool:
        return self.role == AI_HOST_ROLE

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RecordingState:
    status: str = RECORDING_IDLE
    started_at: str = ""
    stopped_at: str = ""
    recording_id: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SlideSync:
    index: int = 0
    title: str = ""
    body: str = ""
    narration: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LiveRoom:
    room_id: str
    class_id: str
    session_id: str
    lesson_id: str
    title: str
    room_size: int = 6
    participants: Dict[str, Participant] = field(default_factory=dict)
    chat: List[ChatMessage] = field(default_factory=list)
    recording: RecordingState = field(default_factory=RecordingState)
    slide: SlideSync = field(default_factory=SlideSync)
    status: str = "live"
    opened_at: str = ""

    def __post_init__(self) -> None:
        self.room_size = validate_room_size(self.room_size)
        self.title = (self.title or "").strip() or "Live class"
        if not self.opened_at:
            self.opened_at = _ts()

    @property
    def learner_count(self) -> int:
        return sum(1 for p in self.participants.values() if not p.is_host)

    @property
    def seats_left(self) -> int:
        return max(0, learner_capacity(self.room_size) - self.learner_count)

    @property
    def is_full(self) -> bool:
        return self.seats_left <= 0

    def host(self) -> Participant:
        for p in self.participants.values():
            if p.is_host:
                return p
        raise LiveRoomError("room is missing AI host")

    def get_participant(self, participant_id: str) -> Participant:
        p = self.participants.get(participant_id)
        if p is None:
            raise NotInRoomError(f"unknown participant {participant_id!r}")
        return p

    def raised_hands(self) -> List[Participant]:
        return [p for p in self.participants.values() if p.hand_raised and not p.is_host]

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "class_id": self.class_id,
            "session_id": self.session_id,
            "lesson_id": self.lesson_id,
            "title": self.title,
            "room_size": self.room_size,
            "learner_capacity": learner_capacity(self.room_size),
            "learner_count": self.learner_count,
            "seats_left": self.seats_left,
            "status": self.status,
            "opened_at": self.opened_at,
            "host": self.host().to_dict(),
            "participants": [p.to_dict() for p in self.participants.values()],
            "chat": [asdict(m) for m in self.chat[-200:]],
            "recording": self.recording.to_dict(),
            "slide": self.slide.to_dict(),
            "raised_hands": [p.to_dict() for p in self.raised_hands()],
        }


class LiveRoomStore:
    """Process-local registry of active Salareen live rooms."""

    def __init__(self) -> None:
        self._rooms: Dict[str, LiveRoom] = {}

    def open_room(
        self,
        *,
        room_id: str,
        class_id: str,
        session_id: str,
        lesson_id: str,
        title: str,
        room_size: int = 6,
        slide_title: str = "",
        slide_body: str = "",
        slide_narration: str = "",
    ) -> LiveRoom:
        if room_id in self._rooms:
            return self._rooms[room_id]
        room = LiveRoom(
            room_id=room_id,
            class_id=class_id,
            session_id=session_id,
            lesson_id=lesson_id,
            title=title,
            room_size=room_size,
            slide=SlideSync(index=0, title=slide_title, body=slide_body, narration=slide_narration),
        )
        host = Participant(id=AI_HOST_ID, name=AI_HOST_NAME, role=AI_HOST_ROLE, can_publish=True)
        room.participants[host.id] = host
        welcome = ChatMessage(
            id=uuid.uuid4().hex[:10],
            from_id=AI_HOST_ID,
            from_name=AI_HOST_NAME,
            text=(
                f"Welcome! I'm Theodore, your AI teacher. "
                f"We have room for up to {learner_capacity(room_size)} learners today. "
                "Raise your hand when you have a question."
            ),
        )
        room.chat.append(welcome)
        self._rooms[room_id] = room
        return room

    def get(self, room_id: str) -> Optional[LiveRoom]:
        return self._rooms.get(room_id)

    def require(self, room_id: str) -> LiveRoom:
        room = self._rooms.get(room_id)
        if room is None:
            raise KeyError(room_id)
        return room

    def join(self, room_id: str, name: str, *, identity: str = "") -> Participant:
        room = self.require(room_id)
        if room.status != "live":
            raise LiveRoomError("this room is not live")
        ident = (identity or "").strip() or f"learner-{uuid.uuid4().hex[:8]}"
        for p in room.participants.values():
            if not p.is_host and p.identity == ident:
                return p
        if room.is_full:
            raise RoomFullError("this live room is full")
        participant = Participant(
            id=uuid.uuid4().hex[:10],
            name=name,
            role=LEARNER_ROLE,
            identity=ident,
        )
        room.participants[participant.id] = participant
        join_msg = ChatMessage(
            id=uuid.uuid4().hex[:10],
            from_id="system",
            from_name="Room",
            text=f"{name} joined the class.",
        )
        room.chat.append(join_msg)
        return participant

    def leave(self, room_id: str, participant_id: str) -> None:
        room = self.require(room_id)
        p = room.get_participant(participant_id)
        if p.is_host:
            raise LiveRoomError("the AI host cannot leave")
        name = p.name
        del room.participants[participant_id]
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id="system",
                from_name="Room",
                text=f"{name} left the class.",
            )
        )

    def post_chat(self, room_id: str, participant_id: str, text: str) -> ChatMessage:
        room = self.require(room_id)
        p = room.get_participant(participant_id)
        if p.muted or p.muted_by_host:
            raise LiveRoomError("you are muted and cannot chat")
        msg = ChatMessage(
            id=uuid.uuid4().hex[:10],
            from_id=p.id,
            from_name=p.name,
            text=text,
        )
        room.chat.append(msg)
        return msg

    def post_host_message(self, room_id: str, text: str) -> ChatMessage:
        room = self.require(room_id)
        host = room.host()
        msg = ChatMessage(
            id=uuid.uuid4().hex[:10],
            from_id=host.id,
            from_name=host.name,
            text=text,
        )
        room.chat.append(msg)
        return msg

    def toggle_hand(self, room_id: str, participant_id: str) -> Participant:
        room = self.require(room_id)
        p = room.get_participant(participant_id)
        if p.is_host:
            raise LiveRoomError("the host does not raise a hand")
        p.hand_raised = not p.hand_raised
        if p.hand_raised:
            room.chat.append(
                ChatMessage(
                    id=uuid.uuid4().hex[:10],
                    from_id="system",
                    from_name="Room",
                    text=f"✋ {p.name} raised their hand.",
                )
            )
        return p

    def set_mute(
        self,
        room_id: str,
        participant_id: str,
        *,
        muted: bool,
        by_host: bool = False,
        actor_id: str = "",
    ) -> Participant:
        room = self.require(room_id)
        target = room.get_participant(participant_id)
        if target.is_host:
            raise LiveRoomError("cannot mute the AI host")
        if by_host:
            actor = room.get_participant(actor_id) if actor_id else room.host()
            if not actor.is_host:
                raise LiveRoomError("only the host can mute learners")
            target.muted_by_host = muted
            target.muted = muted or target.muted
        else:
            if participant_id != actor_id and actor_id:
                raise LiveRoomError("learners can only mute themselves")
            target.muted = muted
            if not muted:
                target.muted_by_host = False
        return target

    def update_slide(
        self,
        room_id: str,
        *,
        index: int,
        title: str,
        body: str = "",
        narration: str = "",
    ) -> SlideSync:
        room = self.require(room_id)
        room.slide = SlideSync(index=index, title=title, body=body, narration=narration)
        return room.slide

    def start_recording(self, room_id: str) -> RecordingState:
        room = self.require(room_id)
        if room.recording.status == RECORDING_ACTIVE:
            return room.recording
        rec_id = uuid.uuid4().hex[:12]
        room.recording = RecordingState(
            status=RECORDING_ACTIVE,
            started_at=_ts(),
            recording_id=rec_id,
            note="Session recording started. Stored when the room ends.",
        )
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id="system",
                from_name="Room",
                text="🔴 Recording started.",
            )
        )
        return room.recording

    def stop_recording(self, room_id: str) -> RecordingState:
        room = self.require(room_id)
        if room.recording.status != RECORDING_ACTIVE:
            room.recording.status = RECORDING_STOPPED
            return room.recording
        room.recording.status = RECORDING_STOPPED
        room.recording.stopped_at = _ts()
        room.recording.note = (
            f"Recording {room.recording.recording_id} saved for class {room.class_id}."
        )
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id="system",
                from_name="Room",
                text="⏹ Recording stopped and queued for storage.",
            )
        )
        return room.recording

    def end_room(self, room_id: str) -> LiveRoom:
        room = self.require(room_id)
        if room.recording.status == RECORDING_ACTIVE:
            self.stop_recording(room_id)
        room.status = "ended"
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id=AI_HOST_ID,
                from_name=AI_HOST_NAME,
                text="Class dismissed. Great work today — see you next time!",
            )
        )
        return room
