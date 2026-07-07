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
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .live_room_backend import LiveRoomBackend
    from .live_room_social import HostFollowStore, LiveRoomGiftLedger

from .live_room_social import (
    GIFT_CATALOG,
    GIFT_FEED_SIZE,
    REACTION_BUFFER_SIZE,
    GiftEvent,
    LiveRoomSocialError,
    ReactionEvent,
    gift_by_id,
)

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

REPORT_CATEGORIES: tuple = ("spam", "harassment", "inappropriate", "disruptive", "other")
REPORT_OPEN = "open"
REPORT_DISMISSED = "dismissed"


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
class UserReport:
    """Learner flag that a participant is behaving badly (moderator reviews)."""

    id: str
    reporter_participant_id: str
    reporter_name: str
    reported_participant_id: str
    reported_name: str
    reported_identity: str
    category: str = "other"
    reason: str = ""
    status: str = REPORT_OPEN
    reported_at: str = ""

    def __post_init__(self) -> None:
        self.category = (self.category or "other").strip().lower()
        if self.category not in REPORT_CATEGORIES:
            raise LiveRoomError(
                f"report category must be one of {', '.join(REPORT_CATEGORIES)}"
            )
        self.reason = (self.reason or "").strip()
        if not self.reason:
            raise LiveRoomError("report reason is required")
        if not self.reported_at:
            self.reported_at = _ts()
        if self.status not in (REPORT_OPEN, REPORT_DISMISSED):
            raise LiveRoomError(f"invalid report status {self.status!r}")

    def to_dict(self) -> dict:
        return asdict(self)


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
    account_id: str = ""
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
    reports: List[UserReport] = field(default_factory=list)
    gift_feed: List[GiftEvent] = field(default_factory=list)
    reactions: List[ReactionEvent] = field(default_factory=list)
    viewer_count: int = 0

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

    def open_reports(self) -> List[UserReport]:
        return [r for r in self.reports if r.status == REPORT_OPEN]

    def report_count_for(self, participant_id: str) -> int:
        return sum(
            1
            for r in self.open_reports()
            if r.reported_participant_id == participant_id
        )

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
            "gift_feed": [g.to_dict() for g in self.gift_feed[-GIFT_FEED_SIZE:]],
            "reactions": [r.to_dict() for r in self.reactions[-REACTION_BUFFER_SIZE:]],
            "viewer_count": self.viewer_count or self.learner_count,
        }

    def to_moderator_dict(self) -> dict:
        """Full room state plus moderator_key and user reports (educator only)."""
        d = self.to_dict()
        d["moderator_key"] = self.moderator_key
        d["reports"] = [r.to_dict() for r in self.open_reports()]
        return d

    def verify_moderator(self, key: str) -> None:
        if not key or key != self.moderator_key:
            raise LiveRoomError("invalid moderator key")


class LiveRoomStore:
    """Registry of active Salareen live rooms.

    Uses an in-memory dict locally; on Vultr VKE (``REDIS_URL`` set) rooms are
    stored in Redis so every orchestrator replica serves the same chat session.
    """

    def __init__(
        self,
        backend: Optional["LiveRoomBackend"] = None,
        *,
        gift_ledger: Optional["LiveRoomGiftLedger"] = None,
        follow_store: Optional["HostFollowStore"] = None,
    ) -> None:
        if backend is None:
            from .live_room_backend import build_live_room_backend

            backend = build_live_room_backend()
        self._backend = backend
        if gift_ledger is None:
            from .live_room_social import LiveRoomGiftLedger

            gift_ledger = LiveRoomGiftLedger()
        if follow_store is None:
            from .live_room_social import HostFollowStore

            follow_store = HostFollowStore()
        self._gift_ledger = gift_ledger
        self._follow_store = follow_store

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def _commit(self, room: LiveRoom) -> None:
        self._backend.save(room)

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
        existing = self._backend.get(room_id)
        if existing is not None:
            return existing
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
        self._commit(room)
        return room

    def get(self, room_id: str) -> Optional[LiveRoom]:
        return self._backend.get(room_id)

    def require(self, room_id: str) -> LiveRoom:
        room = self._backend.get(room_id)
        if room is None:
            raise KeyError(room_id)
        return room

    def join(
        self,
        room_id: str,
        name: str,
        *,
        identity: str = "",
        account_id: str = "",
    ) -> Participant:
        room = self.require(room_id)
        if room.status != "live":
            raise LiveRoomError("this room is not live")
        ident = (identity or "").strip() or f"learner-{uuid.uuid4().hex[:8]}"
        acct = (account_id or "").strip()
        if room.is_banned(ident):
            banned = room.banned[ident]
            detail = banned.reason or "You have been removed from this class."
            raise BannedError(detail)
        for p in room.participants.values():
            if not p.is_host and p.identity == ident:
                if acct:
                    p.account_id = acct
                    self._commit(room)
                return p
        if room.is_full:
            raise RoomFullError("this live room is full")
        participant = Participant(
            id=uuid.uuid4().hex[:10],
            name=name,
            role=LEARNER_ROLE,
            identity=ident,
            account_id=acct,
        )
        room.participants[participant.id] = participant
        room.viewer_count = room.learner_count
        join_msg = ChatMessage(
            id=uuid.uuid4().hex[:10],
            from_id="system",
            from_name="Room",
            text=f"{name} joined the class.",
        )
        room.chat.append(join_msg)
        self._commit(room)
        return participant

    def leave(self, room_id: str, participant_id: str) -> None:
        room = self.require(room_id)
        p = room.get_participant(participant_id)
        if p.is_host:
            raise LiveRoomError("the AI host cannot leave")
        name = p.name
        self._remove_from_queue(room_id, participant_id)
        del room.participants[participant_id]
        room.viewer_count = room.learner_count
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id="system",
                from_name="Room",
                text=f"{name} left the class.",
            )
        )
        self._commit(room)

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
        self._commit(room)
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
        self._commit(room)
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
        self._commit(room)
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
        self._commit(room)

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
        self._commit(room)
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
        self._commit(room)

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
            self._commit(room)
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
            self._commit(room)
            return "answered", None
        entry = self.join_queue(room_id, participant_id, question=q)
        return "queued", entry

    def report_participant(
        self,
        room_id: str,
        reporter_participant_id: str,
        reported_participant_id: str,
        *,
        reason: str,
        category: str = "other",
    ) -> UserReport:
        """Learner flags another participant for moderator review."""
        room = self.require(room_id)
        reporter = room.get_participant(reporter_participant_id)
        if reporter.is_host:
            raise LiveRoomError("the host does not file learner reports")
        target = room.get_participant(reported_participant_id)
        if target.is_host:
            raise LiveRoomError("cannot report the AI host")
        if reporter_participant_id == reported_participant_id:
            raise LiveRoomError("cannot report yourself")
        if room.is_banned(reporter.identity):
            raise BannedError("you are blocked from this room")
        for existing in room.reports:
            if (
                existing.status == REPORT_OPEN
                and existing.reporter_participant_id == reporter_participant_id
                and existing.reported_participant_id == reported_participant_id
            ):
                existing.category = (category or "other").strip().lower()
                existing.reason = (reason or "").strip()
                existing.reported_at = _ts()
                self._commit(room)
                return existing
        report = UserReport(
            id=uuid.uuid4().hex[:10],
            reporter_participant_id=reporter.id,
            reporter_name=reporter.name,
            reported_participant_id=target.id,
            reported_name=target.name,
            reported_identity=target.identity,
            category=category,
            reason=reason,
        )
        room.reports.append(report)
        self._commit(room)
        return report

    def dismiss_report(
        self,
        room_id: str,
        report_id: str,
        *,
        moderator_key: str = "",
    ) -> UserReport:
        """Moderator clears a report without banning."""
        room = self.require(room_id)
        room.verify_moderator(moderator_key)
        for report in room.reports:
            if report.id == report_id and report.status == REPORT_OPEN:
                report.status = REPORT_DISMISSED
                self._commit(room)
                return report
        raise LiveRoomError("report not found or already reviewed")

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
        self._commit(room)
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
        self._commit(room)
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
        self._commit(room)

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
        self._commit(room)
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
        self._commit(room)
        return room.recording

    def stop_recording(self, room_id: str) -> RecordingState:
        room = self.require(room_id)
        if room.recording.status != RECORDING_ACTIVE:
            room.recording.status = RECORDING_STOPPED
            self._commit(room)
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
        self._commit(room)
        return room.recording

    def gift_catalog(self) -> List[dict]:
        return [g.to_dict() for g in GIFT_CATALOG]

    def gift_balance(self, identity: str) -> int:
        return self._gift_ledger.balance(identity)

    def gift_balance_for(
        self,
        participant: Participant,
        authorization: str = "",
    ) -> int:
        """Balance for gifts: identity rewards when linked, else sandbox ledger."""
        if participant.account_id and (authorization or "").strip():
            from .live_room_rewards import rewards_balance_from_auth

            bal = rewards_balance_from_auth(authorization)
            if bal is not None:
                return bal
        return self._gift_ledger.balance(participant.identity)

    def send_gift(
        self,
        room_id: str,
        sender_participant_id: str,
        *,
        gift_id: str,
        recipient_participant_id: str = "",
        authorization: str = "",
    ) -> tuple[GiftEvent, int]:
        """Send a virtual gift; deduct sender points and credit recipient/host."""
        room = self.require(room_id)
        sender = room.get_participant(sender_participant_id)
        if room.is_banned(sender.identity):
            raise BannedError("you are blocked from this room")
        item = gift_by_id(gift_id)
        if item is None:
            raise LiveRoomError("unknown gift")
        recipient_id = recipient_participant_id or AI_HOST_ID
        recipient = room.get_participant(recipient_id)
        credit_amount = max(1, item.cost_points // 2)
        auth = (authorization or "").strip()
        use_identity = bool(sender.account_id and auth)
        from .live_room_rewards import (
            LiveRoomRewardsError,
            earn_rewards_internal,
            spend_rewards_via_auth,
        )

        try:
            if use_identity:
                new_balance = spend_rewards_via_auth(
                    auth,
                    item.cost_points,
                    reason=f"live_gift:{item.id}",
                    ref=room_id,
                )
                if recipient.account_id:
                    earn_rewards_internal(
                        recipient.account_id,
                        credit_amount,
                        reason=f"live_gift_received:{item.id}",
                        ref=room_id,
                    )
                else:
                    self._gift_ledger.credit(
                        recipient.identity,
                        credit_amount,
                        reason=f"live_gift_received:{item.id}",
                        ref=room_id,
                    )
            else:
                new_balance = self._gift_ledger.spend(
                    sender.identity,
                    item.cost_points,
                    reason=f"live_gift:{item.id}",
                    ref=room_id,
                )
                self._gift_ledger.credit(
                    recipient.identity,
                    credit_amount,
                    reason=f"live_gift_received:{item.id}",
                    ref=room_id,
                )
        except LiveRoomRewardsError as exc:
            raise LiveRoomError(str(exc)) from exc
        except LiveRoomSocialError as exc:
            raise LiveRoomError(str(exc)) from exc
        event = GiftEvent(
            id=uuid.uuid4().hex[:10],
            gift_id=item.id,
            gift_name=item.name,
            emoji=item.emoji,
            cost_points=item.cost_points,
            sender_participant_id=sender.id,
            sender_name=sender.name,
            sender_identity=sender.identity,
            recipient_participant_id=recipient.id,
            recipient_name=recipient.name,
        )
        room.gift_feed.append(event)
        if len(room.gift_feed) > GIFT_FEED_SIZE:
            room.gift_feed = room.gift_feed[-GIFT_FEED_SIZE:]
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id="system",
                from_name="Room",
                text=(
                    f"{item.emoji} {sender.name} sent {item.name} "
                    f"to {recipient.name} ({item.cost_points} pts)"
                ),
            )
        )
        self._commit(room)
        return event, new_balance

    def send_reaction(
        self,
        room_id: str,
        participant_id: str,
        *,
        emoji: str,
    ) -> ReactionEvent:
        room = self.require(room_id)
        p = room.get_participant(participant_id)
        if room.is_banned(p.identity):
            raise BannedError("you are blocked from this room")
        try:
            event = ReactionEvent(
                id=uuid.uuid4().hex[:10],
                emoji=emoji,
                participant_id=p.id,
                participant_name=p.name,
            )
        except LiveRoomSocialError as exc:
            raise LiveRoomError(str(exc)) from exc
        room.reactions.append(event)
        if len(room.reactions) > REACTION_BUFFER_SIZE:
            room.reactions = room.reactions[-REACTION_BUFFER_SIZE:]
        self._commit(room)
        return event

    def follow_host(
        self,
        room_id: str,
        follower_identity: str,
        *,
        unfollow: bool = False,
    ) -> tuple[bool, int]:
        room = self.require(room_id)
        host = room.host()
        try:
            if unfollow:
                self._follow_store.unfollow(room_id, host.id, follower_identity)
            else:
                self._follow_store.follow(room_id, host.id, follower_identity)
        except LiveRoomSocialError as exc:
            raise LiveRoomError(str(exc)) from exc
        count = self._follow_store.follower_count(room_id, host.id)
        return self._follow_store.is_following(
            room_id, host.id, follower_identity
        ), count

    def host_follower_count(self, room_id: str) -> int:
        room = self.require(room_id)
        return self._follow_store.follower_count(room_id, room.host().id)

    def is_following_host(self, room_id: str, follower_identity: str) -> bool:
        room = self.require(room_id)
        return self._follow_store.is_following(
            room_id, room.host().id, follower_identity
        )

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
        self._commit(room)
        return room
