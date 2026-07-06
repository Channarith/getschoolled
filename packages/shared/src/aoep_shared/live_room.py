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

QUEUE_WAITING = "waiting"
QUEUE_SPEAKING = "speaking"
QUEUE_DONE = "done"


@dataclass
class QueueEntry:
    """A learner waiting for or holding the floor to ask a question."""

    id: str
    participant_id: str
    name: str
    question: str = ""
    status: str = QUEUE_WAITING
    position: int = 1
    enqueued_at: str = ""

    def __post_init__(self) -> None:
        self.name = (self.name or "").strip()
        if not self.name:
            raise LiveRoomError("queue entry name is required")
        if self.status not in (QUEUE_WAITING, QUEUE_SPEAKING, QUEUE_DONE):
            raise LiveRoomError(f"invalid queue status {self.status!r}")
        if not self.enqueued_at:
            self.enqueued_at = _ts()

    def to_dict(self) -> dict:
        return asdict(self)

class LiveRoomError(ValueError):
    """Invalid live-room request (maps to HTTP 400)."""


class RoomFullError(LiveRoomError):
    """No learner seats left in this room."""


class NotInRoomError(LiveRoomError):
    """Participant is not in this room."""


class BannedError(LiveRoomError):
    """Identity is banned from this room."""


@dataclass
class BannedUser:
    identity: str
    name: str
    reason: str = ""
    banned_at: str = ""
    banned_by: str = AI_HOST_NAME

    def __post_init__(self) -> None:
        self.identity = (self.identity or "").strip()
        self.name = (self.name or "").strip() or self.identity
        self.reason = (self.reason or "").strip()
        if not self.identity:
            raise LiveRoomError("banned identity is required")
        if not self.banned_at:
            self.banned_at = _ts()

    def to_dict(self) -> dict:
        return asdict(self)

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
    banned: Dict[str, BannedUser] = field(default_factory=dict)
    moderator_key: str = ""
    speaking_queue: List[QueueEntry] = field(default_factory=list)
    floor_participant_id: str = ""

    def __post_init__(self) -> None:
        self.room_size = validate_room_size(self.room_size)
        self.title = (self.title or "").strip() or "Live class"
        if not self.opened_at:
            self.opened_at = _ts()
        if not self.moderator_key:
            self.moderator_key = uuid.uuid4().hex[:16]

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
        """Learners waiting in the speaking queue (legacy alias for UI badges)."""
        waiting = {e.participant_id for e in self.waiting_queue()}
        return [p for p in self.participants.values() if p.id in waiting and not p.is_host]

    def waiting_queue(self) -> List[QueueEntry]:
        return [e for e in self.speaking_queue if e.status == QUEUE_WAITING]

    def active_queue(self) -> List[QueueEntry]:
        return [e for e in self.speaking_queue if e.status in (QUEUE_WAITING, QUEUE_SPEAKING)]

    def floor_holder(self) -> Optional[Participant]:
        if not self.floor_participant_id:
            return None
        return self.participants.get(self.floor_participant_id)

    def queue_entry_for(self, participant_id: str) -> Optional[QueueEntry]:
        for entry in reversed(self.speaking_queue):
            if entry.participant_id == participant_id and entry.status != QUEUE_DONE:
                return entry
        return None

    def queue_position(self, participant_id: str) -> int:
        entry = self.queue_entry_for(participant_id)
        if entry is None or entry.status != QUEUE_WAITING:
            return 0
        waiting = self.waiting_queue()
        for i, e in enumerate(waiting, start=1):
            if e.participant_id == participant_id:
                return i
        return 0

    def _reindex_waiting(self) -> None:
        for i, entry in enumerate(self.waiting_queue(), start=1):
            entry.position = i

    def is_banned(self, identity: str) -> bool:
        ident = (identity or "").strip()
        return bool(ident and ident in self.banned)

    def banned_list(self) -> List[BannedUser]:
        return list(self.banned.values())

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
            "banned": [b.to_dict() for b in self.banned_list()],
            "speaking_queue": [e.to_dict() for e in self.active_queue()],
            "floor_participant_id": self.floor_participant_id,
            "floor_holder": (
                self.floor_holder().to_dict() if self.floor_holder() else None
            ),
        }

    def to_moderator_dict(self) -> dict:
        """Full room state plus moderator_key (educator/operator only)."""
        d = self.to_dict()
        d["moderator_key"] = self.moderator_key
        return d

    def verify_moderator(self, key: str) -> None:
        if not key or key != self.moderator_key:
            raise LiveRoomError("invalid moderator key")


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
                "Tap Join Q&A queue when you have a question — I'll call on you in turn."
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
        if room.is_banned(ident):
            banned = room.banned[ident]
            detail = banned.reason or "You have been removed from this class."
            raise BannedError(detail)
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
        self._remove_from_queue(room_id, participant_id)
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
        if room.is_banned(p.identity):
            raise BannedError("you are blocked from this room")
        if p.muted or p.muted_by_host:
            raise LiveRoomError("you are muted and cannot chat")
        if room.floor_participant_id and room.floor_participant_id != participant_id:
            raise LiveRoomError("wait for your turn to speak before chatting live")
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

    def _remove_from_queue(self, room_id: str, participant_id: str) -> None:
        room = self.require(room_id)
        if room.floor_participant_id == participant_id:
            room.floor_participant_id = ""
        room.speaking_queue = [
            e for e in room.speaking_queue
            if e.participant_id != participant_id or e.status == QUEUE_DONE
        ]
        p = room.participants.get(participant_id)
        if p is not None:
            p.hand_raised = False
        room._reindex_waiting()

    def _mute_all_learners(self, room: LiveRoom) -> None:
        for p in room.participants.values():
            if not p.is_host:
                p.muted_by_host = True
                p.muted = True
                p.can_publish = False

    def _grant_floor(self, room: LiveRoom, participant_id: str) -> Participant:
        speaker = room.get_participant(participant_id)
        if speaker.is_host:
            raise LiveRoomError("the AI host already has the floor")
        self._mute_all_learners(room)
        speaker.muted_by_host = False
        speaker.muted = False
        speaker.can_publish = True
        speaker.hand_raised = False
        room.floor_participant_id = participant_id
        for entry in room.speaking_queue:
            if entry.participant_id == participant_id and entry.status == QUEUE_WAITING:
                entry.status = QUEUE_SPEAKING
        return speaker

    def join_queue(
        self,
        room_id: str,
        participant_id: str,
        *,
        question: str = "",
    ) -> QueueEntry:
        """Join the Q&A line to ask a question when called on."""
        room = self.require(room_id)
        p = room.get_participant(participant_id)
        if p.is_host:
            raise LiveRoomError("the host does not join the learner queue")
        if room.is_banned(p.identity):
            raise BannedError("you are blocked from this room")
        existing = room.queue_entry_for(participant_id)
        if existing and existing.status in (QUEUE_WAITING, QUEUE_SPEAKING):
            if question.strip():
                existing.question = question.strip()
            return existing
        entry = QueueEntry(
            id=uuid.uuid4().hex[:10],
            participant_id=participant_id,
            name=p.name,
            question=(question or "").strip(),
            status=QUEUE_WAITING,
            position=len(room.waiting_queue()) + 1,
        )
        room.speaking_queue.append(entry)
        p.hand_raised = True
        self._mute_all_learners(room)
        if room.floor_participant_id:
            holder = room.participants.get(room.floor_participant_id)
            if holder:
                holder.muted_by_host = False
                holder.muted = False
                holder.can_publish = True
        room._reindex_waiting()
        pos = room.queue_position(participant_id)
        q_preview = f': "{entry.question}"' if entry.question else ""
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id="system",
                from_name="Room",
                text=f"✋ {p.name} joined the Q&A queue (#{pos}){q_preview}.",
            )
        )
        return entry

    def leave_queue(self, room_id: str, participant_id: str) -> None:
        room = self.require(room_id)
        p = room.get_participant(participant_id)
        if p.is_host:
            raise LiveRoomError("the host is not in the learner queue")
        if room.floor_participant_id == participant_id:
            self.finish_turn(room_id, participant_id)
            return
        self._remove_from_queue(room_id, participant_id)
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id="system",
                from_name="Room",
                text=f"{p.name} left the Q&A queue.",
            )
        )

    def call_next(self, room_id: str, *, moderator_key: str = "") -> Optional[Participant]:
        """Give the floor to the next learner in the Q&A queue."""
        room = self.require(room_id)
        if moderator_key:
            room.verify_moderator(moderator_key)
        if room.floor_participant_id:
            raise LiveRoomError("someone is already speaking — end their turn first")
        waiting = room.waiting_queue()
        if not waiting:
            raise LiveRoomError("the Q&A queue is empty")
        next_entry = waiting[0]
        speaker = self._grant_floor(room, next_entry.participant_id)
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id=AI_HOST_ID,
                from_name=AI_HOST_NAME,
                text=(
                    f"🎤 {speaker.name}, you're up! "
                    + (f'Your question: "{next_entry.question}". ' if next_entry.question else "")
                    + "Go ahead — we're listening."
                ),
            )
        )
        return speaker

    def finish_turn(self, room_id: str, participant_id: str, *, moderator_key: str = "") -> None:
        """End the current speaker's turn and release the floor."""
        room = self.require(room_id)
        if moderator_key:
            room.verify_moderator(moderator_key)
        if room.floor_participant_id != participant_id:
            if moderator_key:
                raise LiveRoomError("this learner does not have the floor")
            return
        p = room.get_participant(participant_id)
        for entry in room.speaking_queue:
            if entry.participant_id == participant_id and entry.status == QUEUE_SPEAKING:
                entry.status = QUEUE_DONE
        room.floor_participant_id = ""
        p.muted_by_host = True
        p.muted = True
        p.can_publish = False
        p.hand_raised = False
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id="system",
                from_name="Room",
                text=f"✓ {p.name} finished their turn.",
            )
        )
        room._reindex_waiting()

    def toggle_hand(self, room_id: str, participant_id: str, *, question: str = "") -> Participant:
        """Toggle Q&A queue membership (raise hand / leave queue)."""
        room = self.require(room_id)
        p = room.get_participant(participant_id)
        if p.is_host:
            raise LiveRoomError("the host does not raise a hand")
        if room.queue_entry_for(participant_id):
            self.leave_queue(room_id, participant_id)
        else:
            self.join_queue(room_id, participant_id, question=question)
        return room.get_participant(participant_id)

    def ask_when_ready(
        self,
        room_id: str,
        participant_id: str,
        question: str,
    ) -> tuple[str, Optional[QueueEntry]]:
        """Enqueue or answer immediately depending on floor / queue rules.

        Returns ``("answered", None)`` when Theodore responds now, or
        ``("queued", entry)`` when the learner must wait for their turn.
        """
        room = self.require(room_id)
        q = (question or "").strip()
        if not q:
            raise LiveRoomError("question is required")
        if room.floor_participant_id == participant_id:
            return "answered", None
        if not room.floor_participant_id and not room.waiting_queue():
            self._grant_floor(room, participant_id)
            entry = room.queue_entry_for(participant_id)
            if entry is None:
                entry = QueueEntry(
                    id=uuid.uuid4().hex[:10],
                    participant_id=participant_id,
                    name=room.get_participant(participant_id).name,
                    question=q,
                    status=QUEUE_SPEAKING,
                )
                room.speaking_queue.append(entry)
            elif entry.status == QUEUE_WAITING:
                entry.status = QUEUE_SPEAKING
                entry.question = q
            return "answered", None
        entry = self.join_queue(room_id, participant_id, question=q)
        return "queued", entry

    def set_mute(
        self,
        room_id: str,
        participant_id: str,
        *,
        muted: bool,
        by_host: bool = False,
        actor_id: str = "",
        moderator_key: str = "",
    ) -> Participant:
        room = self.require(room_id)
        target = room.get_participant(participant_id)
        if target.is_host:
            raise LiveRoomError("cannot mute the AI host")
        if by_host:
            if moderator_key:
                room.verify_moderator(moderator_key)
            else:
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

    def ban_participant(
        self,
        room_id: str,
        participant_id: str,
        *,
        actor_id: str = "",
        reason: str = "",
        moderator_key: str = "",
    ) -> BannedUser:
        """Remove a learner and block their identity from rejoining (moderator only)."""
        room = self.require(room_id)
        room.verify_moderator(moderator_key)
        target = room.get_participant(participant_id)
        if target.is_host:
            raise LiveRoomError("cannot ban the AI host")
        entry = BannedUser(
            identity=target.identity,
            name=target.name,
            reason=reason or "Removed for disruptive behavior.",
            banned_by=AI_HOST_NAME,
        )
        room.banned[target.identity] = entry
        name = target.name
        self._remove_from_queue(room_id, participant_id)
        del room.participants[participant_id]
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id="system",
                from_name="Room",
                text=f"🚫 {name} was blocked from this class.",
            )
        )
        return entry

    def unban(self, room_id: str, identity: str, *, actor_id: str = "", moderator_key: str = "") -> None:
        """Lift a ban so the learner can join again (moderator only)."""
        room = self.require(room_id)
        room.verify_moderator(moderator_key)
        ident = (identity or "").strip()
        if ident not in room.banned:
            raise LiveRoomError("this identity is not banned")
        entry = room.banned.pop(ident)
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id="system",
                from_name="Room",
                text=f"✅ {entry.name} may rejoin the class.",
            )
        )

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
