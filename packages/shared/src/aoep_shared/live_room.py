"""Salareen Live Room — multi-user teaching sessions (Bigo/Mico-style).

Built-in group-class rooms where Theodore (AI host) teaches up to 3, 5, or 8
learners in a synchronized grid (4, 6, or 9 total seats including the host).
Room state (participants, chat, raise-hand, mute, slide sync, recording) is
managed here; the orchestrator exposes it over HTTP for web and mobile clients.
LiveKit tokens are minted at join time for WebRTC when a media server is
configured.
"""

from __future__ import annotations

import time
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

# 2 = solo 1:1 (AI host + one learner); 4/6/9 = small/medium/large group grids.
ROOM_SIZES: tuple = (2, 4, 6, 9)
AI_HOST_ID = "theodore-ai"
# Placeholder host slot for a human-taught class, held until the instructor joins
# and takes it over. It keeps LiveRoom.host() valid before they arrive.
HUMAN_HOST_ID = "human-host"
AI_HOST_NAME = "Theodore (AI Host)"
AI_HOST_ROLE = "host"
LEARNER_ROLE = "learner"
PRE_CLASS_WELCOME = (
    "Welcome, everyone. I'm Theodore, your AI host. Before we begin, I want to "
    "be transparent: I am an artificial-intelligence teacher, not a human. "
    "I'll guide today's lesson, explain my role clearly, and encourage you to "
    "question both the course material and my answers. Your ideas, corrections, "
    "and questions are always welcome. Please make yourself comfortable—we'll "
    "begin learning together shortly."
)


def human_class_welcome(instructor: str) -> str:
    """Waiting-room text for a class a person teaches (no AI host present)."""
    who = (instructor or "").strip() or "Your instructor"
    return (
        f"Welcome. {who} is teaching this class live. "
        "The session will begin when your instructor starts it."
    )

RECORDING_IDLE = "idle"
RECORDING_ACTIVE = "recording"
RECORDING_STOPPED = "stopped"

QUEUE_WAITING = "waiting"
QUEUE_SPEAKING = "speaking"
QUEUE_DONE = "done"

REPORT_CATEGORIES: tuple = ("spam", "harassment", "inappropriate", "disruptive", "other")
REPORT_OPEN = "open"
REPORT_DISMISSED = "dismissed"
PRESENCE_LIVE = "live"
PRESENCE_UNKNOWN = "unknown"
PRESENCE_SPOOF = "spoof"
PRESENCE_ABSENT = "absent"
PRESENCE_LIVENESS_STATES: tuple = (
    PRESENCE_LIVE,
    PRESENCE_UNKNOWN,
    PRESENCE_SPOOF,
    PRESENCE_ABSENT,
)


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


class RateLimitedError(LiveRoomError):
    """Participant is sending chat/questions too fast (maps to HTTP 429)."""


# Anti-spam guardrails for the live-room chat and "Ask Theodore" features. These
# are enforced server-side (authoritative) as a per-participant sliding window,
# so a client can't bypass them. Kept intentionally lenient for normal use.
CHAT_MAX_CHARS = 500
QUESTION_MAX_CHARS = 600
CHAT_RATE_MAX = 5            # at most 5 chat messages ...
CHAT_RATE_WINDOW_S = 10.0    # ... per rolling 10 seconds
ASK_RATE_MAX = 3            # at most 3 questions ...
ASK_RATE_WINDOW_S = 30.0    # ... per rolling 30 seconds
REACT_RATE_MAX = 10         # emoji reactions ...
REACT_RATE_WINDOW_S = 10.0  # ... per 10 seconds
GIFT_RATE_MAX = 8           # gifts ...
GIFT_RATE_WINDOW_S = 60.0   # ... per minute
REPORT_RATE_MAX = 5         # reports ...
REPORT_RATE_WINDOW_S = 60.0  # ... per minute
QUEUE_RATE_MAX = 5          # raise-hand / queue joins ...
QUEUE_RATE_WINDOW_S = 30.0  # ... per 30 seconds

# Display-name policy for learners joining a room. Guards against impersonating
# the AI teacher (Theodore / Salareen) or the system-message sender ("Room"),
# and against oversized names. Deliberately NARROW: generic role words like
# "administrator"/"teacher"/"host"/"support" are legitimate real account names
# (the seeded admin account is literally "Administrator"), so blocking them here
# produced a bogus "display name is reserved" 400 when those users joined a class.
DISPLAY_NAME_MAX_CHARS = 40
_RESERVED_NAME_TOKENS = frozenset({
    "theodore", "theodoreaihost", "aihost", "salareen", "salareenai",
    "system", "room",
})


def _normalize_name(name: str) -> str:
    """Lowercase + strip non-alphanumerics for reserved-name comparison."""
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def validate_display_name(name: str) -> str:
    """Return the trimmed name or raise ``LiveRoomError`` if it violates policy.

    Rejects empty/oversized names and reserved names that would let a learner
    impersonate the AI host, staff, or system messages (e.g. "Theodore",
    "Administrator", "AI Host").
    """
    clean = (name or "").strip()
    if not clean:
        raise LiveRoomError("participant name is required")
    if len(clean) > DISPLAY_NAME_MAX_CHARS:
        raise LiveRoomError(f"name is too long (max {DISPLAY_NAME_MAX_CHARS} characters)")
    if _normalize_name(clean) in _RESERVED_NAME_TOKENS:
        raise LiveRoomError("that display name is reserved — please choose another")
    return clean


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
    account_id: str = ""

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


def _parse_ts(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


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
    # The learner's preferred language (ISO 639-1, from their profile/device), so
    # the AI teacher answers this person in the language they speak.
    language: str = ""
    joined_at: str = ""
    # Presence heartbeat: refreshed by the client's tick. If a learner closes the
    # browser/app without leaving, their heartbeat stops and the server prunes
    # them once last_seen goes stale (see LiveRoomStore.prune_stale).
    last_seen: str = ""
    # The single class admin — the FIRST learner to join. Can start the class and
    # advance slides (holds moderator powers).
    is_admin: bool = False
    # Optional student profile id for readiness / XR lab scoring (not shown publicly).
    student_id: str = ""
    # Cached readiness band for host adaptation (no accommodations).
    readiness_band: str = ""
    readiness_score: float = 0.0
    # Learning style from identity profile (privacy-safe aggregate input for Theodore).
    primary_style: str = ""

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
        if not self.last_seen:
            self.last_seen = self.joined_at

    @property
    def is_host(self) -> bool:
        return self.role == AI_HOST_ROLE

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "identity": self.identity,
            "account_id": self.account_id,
            "muted": self.muted,
            "muted_by_host": self.muted_by_host,
            "hand_raised": self.hand_raised,
            "can_publish": self.can_publish,
            "language": self.language,
            "joined_at": self.joined_at,
            "last_seen": self.last_seen,
            "is_admin": self.is_admin,
            # Band only in public presence — scores stay host/admin-side.
            "readiness_band": self.readiness_band,
        }

    def to_host_dict(self) -> dict:
        d = self.to_dict()
        d["student_id"] = self.student_id
        d["readiness_score"] = self.readiness_score
        d["primary_style"] = self.primary_style
        return d


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
class PresencePolicy:
    enabled: bool = True
    grace_seconds: int = 90
    stale_seconds: int = 20
    require_liveness: bool = True
    max_faces_allowed: int = 1

    def __post_init__(self) -> None:
        self.enabled = bool(self.enabled)
        self.grace_seconds = max(30, min(300, int(self.grace_seconds or 90)))
        self.stale_seconds = max(5, min(120, int(self.stale_seconds or 20)))
        self.max_faces_allowed = max(1, int(self.max_faces_allowed or 1))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PresenceSignal:
    participant_id: str
    participant_name: str = ""
    present: bool = False
    face_count: int = 0
    liveness_state: str = PRESENCE_UNKNOWN
    liveness_score: float = 0.0
    reason: str = ""
    source: str = ""
    observed_at: str = ""
    absent_started_at: str = ""
    last_live_at: str = ""
    hold_started_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        self.participant_id = (self.participant_id or "").strip()
        if not self.participant_id:
            raise LiveRoomError("presence signal requires participant_id")
        self.participant_name = (self.participant_name or "").strip()
        self.present = bool(self.present)
        self.face_count = max(0, int(self.face_count or 0))
        self.liveness_state = (self.liveness_state or PRESENCE_UNKNOWN).strip().lower()
        if self.liveness_state not in PRESENCE_LIVENESS_STATES:
            self.liveness_state = PRESENCE_UNKNOWN
        self.liveness_score = max(0.0, min(1.0, float(self.liveness_score or 0.0)))
        self.reason = (self.reason or "").strip()
        self.source = (self.source or "").strip()
        self.observed_at = (self.observed_at or "").strip()
        self.absent_started_at = (self.absent_started_at or "").strip()
        self.last_live_at = (self.last_live_at or "").strip()
        self.hold_started_at = (self.hold_started_at or "").strip()
        self.updated_at = (self.updated_at or self.observed_at or _ts()).strip()

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
    # Geo discovery (Bigo-style browse by country/state/city).
    country: str = ""
    state: str = ""
    city: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    creator_name: str = ""
    creator_account_id: str = ""
    # Human-taught ("teach a class") mode: a person teaches, so Theodore is not
    # added to the room at all and the instructor holds the host/presenter slot.
    human_taught: bool = False
    human_host_account_id: str = ""
    human_host_name: str = ""
    # Presentation lifecycle: the room opens in a "waiting" state; the AI starts
    # presenting when the room fills, 5 min after the scheduled time, or when the
    # admin starts it. Then it auto-advances slides on a timer.
    admin_participant_id: str = ""          # the single admin = first learner to join
    presenting: bool = False                 # has the AI started the class?
    scheduled_start: str = ""                # ISO of the class's scheduled time (5-min rule)
    presentation_started_at: str = ""        # ISO when presenting began
    slide_started_at: str = ""               # ISO when the current slide began (auto-advance)
    auto_advance_seconds: int = 5            # per-slide dwell before auto-advancing (5s for now)
    auto_start_grace_seconds: int = 300      # 5-minute rule after the scheduled time
    welcome_message: str = PRE_CLASS_WELCOME
    welcome_started_at: str = ""
    pre_class_welcome_seconds: int = 12
    # Auto-end: a group lesson runs for its allotted length. Once presenting for
    # ``duration_seconds`` the class ends automatically (0 = open-ended, e.g. a
    # solo 1:1 or instant room). ``ended_at`` marks when it closed.
    duration_seconds: int = 0
    ended_at: str = ""
    # Optional XR lab mode (feature-flagged). Public snapshot omits raw observations.
    xr_lab_enabled: bool = False
    xr_lab: Optional[dict] = None
    xr_attempts: Dict[str, dict] = field(default_factory=dict)
    # Privacy-safe audience readiness snapshot for Theodore (no names).
    audience_profile: Dict[str, object] = field(default_factory=dict)
    # Camera-driven attendance hold policy/signals.
    presence_policy: PresencePolicy = field(default_factory=PresencePolicy)
    presence_signals: Dict[str, PresenceSignal] = field(default_factory=dict)
    presence_hold_active: bool = False
    presence_hold_participant_id: str = ""
    presence_hold_reason: str = ""
    presence_hold_started_at: str = ""
    # Synchronized educational mini-game (private answer is stripped publicly).
    group_game: Optional[dict] = None

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
        raise LiveRoomError("room is missing a host")

    def system_host_identity(self) -> tuple[str, str]:
        """Who automated room notices are attributed to.

        A human-taught class has no Theodore, so notices come from the
        instructor's host slot rather than from an AI that is not in the room.
        """
        if self.human_taught:
            try:
                host = self.host()
            except LiveRoomError:
                return HUMAN_HOST_ID, self.human_host_name or "Instructor"
            return host.id, host.name
        return AI_HOST_ID, AI_HOST_NAME

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
        from .live_room_games import public_game

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
            "human_taught": self.human_taught,
            "human_host_name": self.human_host_name,
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
            "country": self.country,
            "state": self.state,
            "city": self.city,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "creator_name": self.creator_name,
            "admin_participant_id": self.admin_participant_id,
            "presenting": self.presenting,
            "scheduled_start": self.scheduled_start,
            "duration_seconds": self.duration_seconds,
            "ended_at": self.ended_at,
            "welcome_message": self.welcome_message,
            "welcome_started_at": self.welcome_started_at,
            "pre_class_welcome_seconds": self.pre_class_welcome_seconds,
            "xr_lab_enabled": self.xr_lab_enabled,
            "xr_lab": self.xr_lab,
            "xr_attempts": {
                pid: {
                    "outcome": row.get("outcome"),
                    "score": row.get("score"),
                    "provisional": row.get("provisional", True),
                    "client_kind": row.get("client_kind"),
                    "completed_at": row.get("completed_at"),
                }
                for pid, row in (self.xr_attempts or {}).items()
            },
            "audience_profile": dict(self.audience_profile or {}),
            "presence_policy": self.presence_policy.to_dict(),
            "presence": {
                "hold_active": bool(self.presence_hold_active),
                "hold_participant_id": self.presence_hold_participant_id,
                "hold_participant_name": (
                    self.participants.get(self.presence_hold_participant_id).name
                    if self.presence_hold_participant_id in self.participants
                    else ""
                ),
                "hold_reason": self.presence_hold_reason,
                "hold_started_at": self.presence_hold_started_at,
                "signals": [
                    self.presence_signals[k].to_dict()
                    for k in sorted(self.presence_signals.keys())
                ],
            },
            "group_game": public_game(self.group_game),
        }

    def to_moderator_dict(self) -> dict:
        """Full room state plus private learner profiles/reports (educator only)."""
        d = self.to_dict()
        d["participants"] = [
            p.to_host_dict() for p in self.participants.values()
        ]
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
        # Anti-spam sliding-window timestamps, keyed by (room, participant, kind).
        # In-memory + best-effort: it lives on this store instance rather than in
        # the room snapshot (keeps chat/ask fast and avoids Redis churn). With
        # ingress session affinity a participant's requests hit one replica, so
        # the window is accurate; without it, limiting is per-replica but still
        # curbs floods.
        self._rate_events: dict[tuple[str, str, str], list[float]] = {}

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def _commit(self, room: LiveRoom) -> None:
        self._backend.save(room)

    def _enforce_rate(
        self,
        room_id: str,
        participant_id: str,
        kind: str,
        *,
        max_events: int,
        window_s: float,
        message: str,
    ) -> None:
        """Sliding-window rate limit for a participant action (chat/ask).

        Raises ``RateLimitedError`` when more than ``max_events`` have occurred in
        the last ``window_s`` seconds; otherwise records this event.
        """
        now = time.monotonic()
        key = (room_id, participant_id, kind)
        recent = [t for t in self._rate_events.get(key, []) if now - t < window_s]
        if len(recent) >= max_events:
            self._rate_events[key] = recent
            raise RateLimitedError(message)
        recent.append(now)
        self._rate_events[key] = recent

    def _clear_rate(self, room_id: str, participant_id: str) -> None:
        """Drop a participant's rate-limit bookkeeping (on leave)."""
        for kind in ("chat", "ask", "queue", "report", "gift", "react"):
            self._rate_events.pop((room_id, participant_id, kind), None)

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
        country: str = "",
        state: str = "",
        city: str = "",
        latitude: float = 0.0,
        longitude: float = 0.0,
        creator_name: str = "",
        creator_account_id: str = "",
        human_taught: bool = False,
        human_host_account_id: str = "",
        human_host_name: str = "",
        scheduled_start: str = "",
        duration_seconds: int = 0,
        presence_enabled: bool = True,
        presence_hold_grace_seconds: int = 90,
        presence_stale_seconds: int = 20,
        presence_require_liveness: bool = True,
        presence_max_faces_allowed: int = 1,
    ) -> LiveRoom:
        existing = self._backend.get(room_id)
        if existing is not None:
            dirty = False
            if scheduled_start and not existing.scheduled_start:
                existing.scheduled_start = scheduled_start
                dirty = True
            if duration_seconds and not existing.duration_seconds:
                existing.duration_seconds = int(duration_seconds)
                dirty = True
            next_policy = PresencePolicy(
                enabled=presence_enabled,
                grace_seconds=presence_hold_grace_seconds,
                stale_seconds=presence_stale_seconds,
                require_liveness=presence_require_liveness,
                max_faces_allowed=presence_max_faces_allowed,
            )
            if existing.presence_policy.to_dict() != next_policy.to_dict():
                existing.presence_policy = next_policy
                dirty = True
            if dirty:
                self._commit(existing)
            from .live_room_discovery import apply_location

            apply_location(
                existing,
                country=country,
                state=state,
                city=city,
                latitude=latitude,
                longitude=longitude,
                creator_name=creator_name,
                creator_account_id=creator_account_id,
            )
            if country or city or latitude:
                self._commit(existing)
            return existing
        room = LiveRoom(
            room_id=room_id,
            class_id=class_id,
            session_id=session_id,
            lesson_id=lesson_id,
            title=title,
            room_size=room_size,
            slide=SlideSync(index=0, title=slide_title, body=slide_body, narration=slide_narration),
            country=country.strip(),
            state=state.strip(),
            city=city.strip(),
            latitude=float(latitude or 0),
            longitude=float(longitude or 0),
            creator_name=creator_name.strip(),
            creator_account_id=creator_account_id.strip(),
            scheduled_start=(scheduled_start or "").strip(),
            duration_seconds=int(duration_seconds or 0),
            presence_policy=PresencePolicy(
                enabled=presence_enabled,
                grace_seconds=presence_hold_grace_seconds,
                stale_seconds=presence_stale_seconds,
                require_liveness=presence_require_liveness,
                max_faces_allowed=presence_max_faces_allowed,
            ),
        )
        if human_taught:
            # A person is teaching: no Theodore in the room at all. The host slot
            # is a placeholder until the instructor joins and takes it over.
            instructor = (human_host_name or creator_name or "Instructor").strip()
            room.human_taught = True
            room.human_host_account_id = (human_host_account_id or creator_account_id or "").strip()
            room.human_host_name = instructor
            room.welcome_message = human_class_welcome(instructor)
            host = Participant(
                id=HUMAN_HOST_ID,
                name=instructor,
                role=AI_HOST_ROLE,
                account_id=room.human_host_account_id,
                can_publish=True,
            )
        else:
            host = Participant(
                id=AI_HOST_ID, name=AI_HOST_NAME, role=AI_HOST_ROLE, can_publish=True
            )
        room.participants[host.id] = host
        welcome = ChatMessage(
            id=uuid.uuid4().hex[:10],
            from_id=host.id,
            from_name=host.name,
            text=room.welcome_message,
        )
        room.chat.append(welcome)
        self._commit(room)
        return room

    def enable_xr_lab(
        self,
        room_id: str,
        lab: dict,
        *,
        enabled: bool = True,
    ) -> LiveRoom:
        room = self.require(room_id)
        room.xr_lab_enabled = bool(enabled)
        room.xr_lab = dict(lab) if lab else None
        if not enabled:
            room.xr_lab = None
        self._commit(room)
        return room

    def record_xr_attempt(self, room_id: str, participant_id: str, summary: dict) -> LiveRoom:
        room = self.require(room_id)
        room.get_participant(participant_id)  # raises if unknown
        attempts = dict(room.xr_attempts or {})
        attempts[participant_id] = {
            "outcome": summary.get("outcome"),
            "score": summary.get("score"),
            "provisional": summary.get("provisional", True),
            "client_kind": summary.get("client_kind"),
            "completed_at": summary.get("completed_at"),
            "attempt_id": summary.get("attempt_id"),
            "lab_id": summary.get("lab_id"),
            "evidence_summary": summary.get("evidence_summary"),
        }
        room.xr_attempts = attempts
        self._commit(room)
        return room

    def set_audience_profile(self, room_id: str, profile: dict) -> LiveRoom:
        room = self.require(room_id)
        room.audience_profile = dict(profile or {})
        self._commit(room)
        return room

    def start_group_game(
        self, room_id: str, *, game_type: str, prompt: str, answer: str, points: int = 25
    ) -> LiveRoom:
        from .live_room_games import start_game

        room = self.require(room_id)
        room.group_game = start_game(
            game_type, prompt=prompt, answer=answer, points=points
        )
        self._commit(room)
        return room

    def play_group_game(
        self, room_id: str, participant_id: str, *,
        answer: str = "", cell: int = -1, letter: str = "",
    ) -> tuple[LiveRoom, dict]:
        from .live_room_games import apply_action

        room = self.require(room_id)
        participant = room.get_participant(participant_id)
        if not room.group_game:
            raise LiveRoomError("no group game is active")
        event = apply_action(
            room.group_game,
            participant_id=participant.id,
            participant_name=participant.name,
            answer=answer,
            cell=cell,
            letter=letter,
        )
        self._commit(room)
        return room, event

    def get(self, room_id: str) -> Optional[LiveRoom]:
        return self._backend.get(room_id)

    def delete(self, room_id: str) -> None:
        """Remove a room entirely (admin cleanup). Idempotent."""
        self._backend.delete(room_id)

    def list_live(
        self,
        *,
        lat: float = 0.0,
        lng: float = 0.0,
        radius_km: float = 0.0,
        country: str = "",
        city: str = "",
    ) -> List[LiveRoom]:
        """All rooms with status=live, optionally filtered by geo."""
        from .live_room_discovery import haversine_km

        rooms: List[LiveRoom] = []
        for rid in self._backend.list_live_ids():
            room = self._backend.get(rid)
            if room is None or room.status != "live":
                continue
            # Lazily close a room that outlived its allotted window even if no
            # client was ticking (abandoned/empty), so discovery never shows an
            # expired class as still "live".
            if self.should_expire(rid):
                self.end_room(rid, auto=True)
                continue
            if country and (room.country or "").lower() != country.strip().lower():
                continue
            if city and (room.city or "").lower() != city.strip().lower():
                continue
            if radius_km > 0 and lat and lng and room.latitude and room.longitude:
                if haversine_km(lat, lng, room.latitude, room.longitude) > radius_km:
                    continue
            rooms.append(room)
        if lat and lng:
            rooms.sort(
                key=lambda r: (
                    haversine_km(lat, lng, r.latitude, r.longitude)
                    if r.latitude and r.longitude
                    else 999_999,
                    -(r.viewer_count or r.learner_count),
                ),
            )
        else:
            rooms.sort(key=lambda r: (-(r.viewer_count or r.learner_count), r.title))
        return rooms

    def create_user_room(
        self,
        *,
        title: str,
        creator_name: str,
        creator_account_id: str = "",
        room_size: int = 6,
        country: str = "",
        state: str = "",
        city: str = "",
        latitude: float = 0.0,
        longitude: float = 0.0,
        lesson_id: str = "open-live",
    ) -> LiveRoom:
        """Instant Salareen room (Bigo-style go-live) — visible in discovery feed."""
        room_id = f"sal-{uuid.uuid4().hex[:10]}"
        return self.open_room(
            room_id=room_id,
            class_id="",
            session_id="",
            lesson_id=lesson_id,
            title=title,
            room_size=room_size,
            country=country,
            state=state,
            city=city,
            latitude=latitude,
            longitude=longitude,
            creator_name=creator_name,
            creator_account_id=creator_account_id,
        )

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
        language: str = "",
        student_id: str = "",
        readiness_band: str = "",
        readiness_score: float = 0.0,
        primary_style: str = "",
    ) -> Participant:
        room = self.require(room_id)
        if room.status != "live":
            raise LiveRoomError("this room is not live")
        name = validate_display_name(name)
        ident = (identity or "").strip() or f"learner-{uuid.uuid4().hex[:8]}"
        acct = (account_id or "").strip()
        from .languages import normalize_language

        lang = normalize_language(language)
        sid = (student_id or "").strip()
        if room.is_banned(ident):
            banned = room.banned[ident]
            detail = banned.reason or "You have been removed from this class."
            raise BannedError(detail)
        # Also reject banned account IDs regardless of identity string
        if acct and any(
            b.account_id == acct for b in room.banned.values() if b.account_id
        ):
            raise BannedError("You have been removed from this class.")
        for p in room.participants.values():
            if not p.is_host and p.identity == ident:
                if acct:
                    p.account_id = acct
                if lang and p.language != lang:
                    p.language = lang  # keep the language fresh on re-join
                if sid:
                    p.student_id = sid
                if readiness_band:
                    p.readiness_band = readiness_band
                    p.readiness_score = float(readiness_score or 0.0)
                style = (primary_style or "").strip()
                if style:
                    p.primary_style = style
                p.last_seen = _ts()   # re-join counts as presence
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
            language=lang,
            student_id=sid,
            readiness_band=(readiness_band or "").strip(),
            readiness_score=float(readiness_score or 0.0),
            primary_style=(primary_style or "").strip(),
            # Hard mutex: learners join WITHOUT publish rights. Their LiveKit token
            # can't send audio/video until the host/AI grants them the floor
            # (which flips can_publish and lets the client fetch a publish token).
            can_publish=False,
        )
        host_acct = (room.creator_account_id or "").strip()
        is_scheduled_host = bool(acct and host_acct and acct == host_acct)
        if room.human_taught and acct and acct == (room.human_host_account_id or host_acct):
            # The instructor IS the presenter: take over the host slot so their
            # camera fills the main tile and they can publish immediately.
            room.participants.pop(HUMAN_HOST_ID, None)
            participant.role = AI_HOST_ROLE
            participant.can_publish = True
            room.human_host_name = participant.name
        # The scheduled instructor always becomes class admin when they join.
        # Otherwise the first learner to join becomes admin (legacy flow).
        current_admin = room.participants.get(room.admin_participant_id)
        if is_scheduled_host or current_admin is None or current_admin.is_host:
            room.admin_participant_id = participant.id
            participant.is_admin = True
        room.participants[participant.id] = participant
        if not room.welcome_started_at:
            room.welcome_started_at = _ts()
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
        if p.is_host and not room.human_taught:
            raise LiveRoomError("the AI host cannot leave")
        restore_host_slot = p.is_host and room.human_taught
        name = p.name
        self._remove_from_queue(room, participant_id)
        self._clear_rate(room_id, participant_id)
        del room.participants[participant_id]
        if restore_host_slot:
            # Keep a host slot so the room still renders while the instructor is away.
            room.participants[HUMAN_HOST_ID] = Participant(
                id=HUMAN_HOST_ID,
                name=room.human_host_name or "Instructor",
                role=AI_HOST_ROLE,
                account_id=room.human_host_account_id,
                can_publish=True,
            )
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
        clean = (text or "").strip()
        if not clean:
            raise LiveRoomError("message is empty")
        if len(clean) > CHAT_MAX_CHARS:
            raise LiveRoomError(f"message is too long (max {CHAT_MAX_CHARS} characters)")
        # Anti-spam: cap the rate of chat messages per participant.
        self._enforce_rate(
            room_id, participant_id, "chat",
            max_events=CHAT_RATE_MAX, window_s=CHAT_RATE_WINDOW_S,
            message="you're sending messages too fast — please slow down",
        )
        text = clean
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

    def _remove_from_queue(self, room: "LiveRoom", participant_id: str) -> None:
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
        if len((question or "").strip()) > QUESTION_MAX_CHARS:
            raise LiveRoomError(f"question is too long (max {QUESTION_MAX_CHARS} characters)")
        existing = room.queue_entry_for(participant_id)
        if existing and existing.status in (QUEUE_WAITING, QUEUE_SPEAKING):
            if question.strip():
                existing.question = question.strip()
            return existing
        # Anti-spam: only NEW queue joins count (idempotent re-join above is free).
        self._enforce_rate(
            room_id, participant_id, "queue",
            max_events=QUEUE_RATE_MAX, window_s=QUEUE_RATE_WINDOW_S,
            message="you're raising your hand too fast — please wait a moment",
        )
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
        self._remove_from_queue(room, participant_id)
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
                from_id=room.system_host_identity()[0],
                from_name=room.system_host_identity()[1],
                text=(
                    f"🎤 {speaker.name}, you're up! "
                    + (f'Your question: "{next_entry.question}". ' if next_entry.question else "")
                    + "Go ahead — we're listening."
                ),
            )
        )
        self._commit(room)
        return speaker

    def call_on(
        self,
        room_id: str,
        participant_id: str,
        *,
        moderator_key: str = "",
    ) -> Participant:
        """Give the floor to a SPECIFIC learner (host/AI picks who holds the mic),
        jumping the FIFO queue. Any current speaker's turn is ended first, so the
        single-speaker mutex (only one publisher/talker) is preserved — the AI can
        switch who it's listening to mid-presentation."""
        room = self.require(room_id)
        if moderator_key:
            room.verify_moderator(moderator_key)
        target = room.get_participant(participant_id)  # KeyError -> unknown participant
        if target.is_host:
            raise LiveRoomError("the host already presents")
        if room.is_banned(target.identity):
            raise BannedError("that learner is blocked from this room")
        # Preempt the current holder (mutex: exactly one speaker at a time).
        if room.floor_participant_id and room.floor_participant_id != participant_id:
            for entry in room.speaking_queue:
                if (entry.participant_id == room.floor_participant_id
                        and entry.status == QUEUE_SPEAKING):
                    entry.status = QUEUE_DONE
            room.floor_participant_id = ""
        # Ensure the target has a queue entry so _grant_floor flips it to SPEAKING.
        existing = room.queue_entry_for(participant_id)
        if not (existing and existing.status in (QUEUE_WAITING, QUEUE_SPEAKING)):
            room.speaking_queue.append(
                QueueEntry(
                    id=uuid.uuid4().hex[:10],
                    participant_id=participant_id,
                    name=target.name,
                    question=(existing.question if existing else ""),
                    status=QUEUE_WAITING,
                    position=len(room.waiting_queue()) + 1,
                )
            )
        speaker = self._grant_floor(room, participant_id)
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id=room.system_host_identity()[0],
                from_name=room.system_host_identity()[1],
                text=f"🎤 {speaker.name}, the floor is yours — go ahead, we're listening.",
            )
        )
        room._reindex_waiting()
        self._commit(room)
        return speaker

    def start_presentation(
        self,
        room_id: str,
        *,
        participant_id: str = "",
        moderator_key: str = "",
        auto: bool = False,
    ) -> LiveRoom:
        """Begin the AI presentation. Authorized by the admin (participant_id) or
        moderator_key; ``auto=True`` is the server's own auto-start. Idempotent."""
        room = self.require(room_id)
        if not auto:
            if moderator_key:
                room.verify_moderator(moderator_key)
            elif participant_id:
                p = room.get_participant(participant_id)
                if not p.is_admin:
                    raise LiveRoomError("only the class admin can start the class")
            else:
                raise LiveRoomError("not authorized to start the class")
        if room.presenting:
            return room
        now = _ts()
        room.presenting = True
        room.presentation_started_at = now
        room.slide_started_at = now
        # Deduplicate start announcements — concurrent ticks / replica reopens
        # used to flood chat with "Class is starting automatically…" every few
        # seconds when presenting briefly reset or raced across writes. We use a
        # DETERMINISTIC message id (one per room) so that even a duplicate that
        # slips through a cross-replica read-modify-write race collapses to a
        # single line client-side (both web + mobile key chat by message id).
        start_msg_id = f"start-{room_id}"[:32]
        already_announced = any(
            m.id == start_msg_id
            or (m.from_id == AI_HOST_ID and m.text.startswith("🎬 Class is starting"))
            for m in room.chat[-30:]
        )
        if not already_announced:
            if auto:
                note = "the room is full" if room.is_full else "we're at start time"
                text = f"🎬 Class is starting automatically — {note}. Let's begin!"
            else:
                text = "🎬 Class is starting — let's begin!"
            room.chat.append(
                ChatMessage(
                    id=start_msg_id,
                    from_id=room.system_host_identity()[0],
                    from_name=room.system_host_identity()[1],
                    text=text,
                )
            )
        self._commit(room)
        return room

    def should_auto_start(self, room_id: str, *, now: Optional[datetime] = None) -> bool:
        """True when the AI should begin presenting.

        Theodore first gets a short, guaranteed pre-class window to welcome the
        audience and disclose clearly that he is an AI host. After that, a class
        runs whenever at least one learner is present and it is full, instant,
        or has reached its scheduled start time.

        A human-taught class never auto-starts: the instructor decides when to
        begin by clicking "Start my class"."""
        from datetime import timedelta

        room_check = self._backend.get(room_id)
        if room_check is not None and room_check.human_taught:
            return False

        room = self.require(room_id)
        if room.presence_hold_active:
            return False
        if room.status != "live" or room.presenting or room.learner_count < 1:
            return False
        welcome_started = _parse_ts(room.welcome_started_at)
        ref = now or _now()
        if welcome_started and ref < welcome_started + timedelta(
            seconds=max(0, room.pre_class_welcome_seconds)
        ):
            return False
        if room.is_full:
            return True
        sched = _parse_ts(room.scheduled_start)
        if sched is None:
            return True
        return ref >= sched  # scheduled — start once the time arrives (a learner is present)

    def should_auto_advance(self, room_id: str, *, now: Optional[datetime] = None) -> bool:
        """True when the current slide has been up long enough to auto-advance —
        but never while a learner holds the floor or is waiting to speak.

        The dwell is proportional to how long the slide's narration takes to
        SPEAK (not a fixed 5s), so slides don't advance before the AI finishes
        talking (which cut narration off) and a content-rich lesson runs for its
        natural length instead of racing by in a couple of minutes."""
        from datetime import timedelta

        room = self.require(room_id)
        if room.presence_hold_active:
            return False
        if room.status != "live" or not room.presenting or room.floor_participant_id or room.waiting_queue():
            return False
        started = _parse_ts(room.slide_started_at)
        if started is None:
            return False
        ref = now or _now()
        return ref >= started + timedelta(seconds=self.slide_dwell_seconds(room))

    @staticmethod
    def slide_dwell_seconds(room: LiveRoom) -> float:
        """Estimated seconds to speak the current slide, used as the auto-advance
        dwell. Clients narrate the slide title + body (falling back to the short
        narration line), so we size the dwell to that at a clear ~140 wpm, with a
        sensible floor/ceiling and a short buffer so narration always finishes."""
        slide = room.slide
        spoken = f"{slide.title}. {slide.body or slide.narration}".strip()
        words = len(spoken.split())
        # 140 wpm ≈ 2.33 words/sec (slightly slow so the estimate never trails the
        # actual TTS and cuts narration off), + 4s to breathe between slides.
        est = words / 2.33 + 4.0
        floor = float(room.auto_advance_seconds)  # never faster than the base dwell
        return max(floor, min(est, 150.0))

    def should_auto_end(self, room_id: str, *, now: Optional[datetime] = None) -> bool:
        """True when a presenting group lesson has used its whole allotted time
        (``duration_seconds`` after the presentation began) and should close.
        Open-ended rooms (duration_seconds == 0, e.g. solo 1:1) never auto-end."""
        from datetime import timedelta

        room = self.require(room_id)
        if room.presence_hold_active:
            return False
        if room.status != "live" or not room.presenting or room.duration_seconds <= 0:
            return False
        started = _parse_ts(room.presentation_started_at)
        if started is None:
            return False
        ref = now or _now()
        return ref >= started + timedelta(seconds=room.duration_seconds)

    def should_expire(self, room_id: str, *, now: Optional[datetime] = None) -> bool:
        """True when a scheduled group lesson has outlived its allotted window and
        should be closed even if NO client is ticking (an abandoned/empty room).
        Presenting rooms expire ``duration_seconds`` after they started; a room
        that never started expires once its scheduled window + grace fully lapses.
        Open-ended rooms (duration_seconds == 0, e.g. solo 1:1 / instant) never
        expire on the clock."""
        from datetime import timedelta

        room = self.require(room_id)
        if room.status != "live" or room.duration_seconds <= 0:
            return False
        ref = now or _now()
        started = _parse_ts(room.presentation_started_at)
        if started is not None:
            return ref >= started + timedelta(seconds=room.duration_seconds)
        sched = _parse_ts(room.scheduled_start)
        if sched is not None:
            return ref >= sched + timedelta(
                seconds=room.duration_seconds + room.auto_start_grace_seconds
            )
        return False

    @staticmethod
    def _presence_is_live(room: LiveRoom, signal: PresenceSignal) -> tuple[bool, str]:
        if not room.presence_policy.enabled:
            return True, "disabled"
        if not signal.present or signal.face_count <= 0:
            return False, signal.reason or "no_face"
        if signal.face_count > room.presence_policy.max_faces_allowed:
            return False, "too_many_faces"
        if room.presence_policy.require_liveness and signal.liveness_state != PRESENCE_LIVE:
            return False, "liveness_not_verified"
        return True, signal.reason or "verified"

    @staticmethod
    def _set_presence_hold(
        room: LiveRoom,
        participant_id: str,
        participant_name: str,
        reason: str,
        *,
        now: datetime,
    ) -> bool:
        if room.presence_hold_active and room.presence_hold_participant_id == participant_id:
            return False
        room.presence_hold_active = True
        room.presence_hold_participant_id = participant_id
        room.presence_hold_reason = (reason or "presence_not_verified").strip()
        room.presence_hold_started_at = now.isoformat()
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id=room.system_host_identity()[0],
                from_name=room.system_host_identity()[1],
                text=(
                    f"⏸️ Presence hold: pausing class because {participant_name or 'a learner'} "
                    "is not visually present. We'll resume automatically once they return."
                ),
            )
        )
        return True

    @staticmethod
    def _clear_presence_hold(room: LiveRoom, participant_name: str, *, now: datetime) -> bool:
        if not room.presence_hold_active:
            return False
        room.presence_hold_active = False
        room.presence_hold_participant_id = ""
        room.presence_hold_reason = ""
        room.presence_hold_started_at = ""
        # Reset the slide timer so auto-advance does not jump immediately after resume.
        room.slide_started_at = now.isoformat()
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id=room.system_host_identity()[0],
                from_name=room.system_host_identity()[1],
                text=(
                    f"▶️ Presence restored for {participant_name or 'the learner'} — "
                    "resuming class."
                ),
            )
        )
        return True

    def report_presence(
        self,
        room_id: str,
        *,
        participant_id: str,
        present: bool,
        face_count: int = 0,
        liveness_state: str = PRESENCE_UNKNOWN,
        liveness_score: float = 0.0,
        reason: str = "",
        source: str = "",
        observed_at: Optional[datetime] = None,
    ) -> dict:
        room = self.require(room_id)
        p = room.participants.get(participant_id)
        if p is None or p.is_host:
            raise NotInRoomError(f"unknown participant {participant_id!r}")
        ref = observed_at or _now()
        signal = room.presence_signals.get(participant_id) or PresenceSignal(
            participant_id=participant_id,
            participant_name=p.name,
        )
        signal.participant_name = p.name
        signal.present = bool(present)
        signal.face_count = max(0, int(face_count or 0))
        signal.liveness_state = (liveness_state or PRESENCE_UNKNOWN).strip().lower()
        if signal.liveness_state not in PRESENCE_LIVENESS_STATES:
            signal.liveness_state = PRESENCE_UNKNOWN
        signal.liveness_score = max(0.0, min(1.0, float(liveness_score or 0.0)))
        signal.reason = (reason or "").strip()
        signal.source = (source or "").strip()
        signal.observed_at = ref.isoformat()
        signal.updated_at = _ts()
        is_live, hold_reason = self._presence_is_live(room, signal)
        if is_live:
            signal.last_live_at = ref.isoformat()
            signal.absent_started_at = ""
            signal.hold_started_at = ""
            if (
                room.presence_hold_active
                and room.presence_hold_participant_id == participant_id
            ):
                self._clear_presence_hold(room, p.name, now=ref)
        else:
            if not signal.absent_started_at:
                signal.absent_started_at = ref.isoformat()
            absent_since = _parse_ts(signal.absent_started_at)
            if (
                absent_since is not None
                and (ref - absent_since).total_seconds() >= room.presence_policy.grace_seconds
            ):
                signal.hold_started_at = room.presence_hold_started_at or ref.isoformat()
                self._set_presence_hold(room, participant_id, p.name, hold_reason, now=ref)
        room.presence_signals[participant_id] = signal
        self._commit(room)
        payload = signal.to_dict()
        payload["verified_live"] = is_live
        payload["hold_reason"] = hold_reason
        return payload

    def evaluate_presence_holds(self, room_id: str, *, now: Optional[datetime] = None) -> bool:
        room = self.require(room_id)
        if not room.presence_policy.enabled or room.status != "live" or not room.presenting:
            return False
        ref = now or _now()
        changed = False
        for pid, participant in list(room.participants.items()):
            if participant.is_host:
                continue
            signal = room.presence_signals.get(pid)
            if signal is None:
                signal = PresenceSignal(participant_id=pid, participant_name=participant.name)
                signal.reason = "no_signal"
                signal.present = False
                signal.observed_at = participant.joined_at or ""
                signal.updated_at = _ts()
                signal.absent_started_at = ref.isoformat()
                room.presence_signals[pid] = signal
                changed = True
            else:
                signal.participant_name = participant.name
                observed = _parse_ts(signal.observed_at or signal.updated_at)
                if observed is None or (
                    (ref - observed).total_seconds() > room.presence_policy.stale_seconds
                ):
                    if signal.present:
                        signal.present = False
                        changed = True
                    if not signal.reason:
                        signal.reason = "stale_signal"
                        changed = True
                    if not signal.absent_started_at:
                        signal.absent_started_at = ref.isoformat()
                        changed = True
        if room.presence_hold_active:
            active_id = room.presence_hold_participant_id
            if not active_id or active_id not in room.participants:
                changed = self._clear_presence_hold(room, "the learner", now=ref) or changed
            else:
                active_signal = room.presence_signals.get(active_id)
                if active_signal is not None:
                    is_live, _ = self._presence_is_live(room, active_signal)
                    if is_live:
                        changed = (
                            self._clear_presence_hold(
                                room, room.participants[active_id].name, now=ref
                            )
                            or changed
                        )
        if not room.presence_hold_active:
            for pid, participant in room.participants.items():
                if participant.is_host:
                    continue
                signal = room.presence_signals.get(pid)
                if signal is None:
                    continue
                is_live, hold_reason = self._presence_is_live(room, signal)
                if is_live:
                    continue
                absent_since = _parse_ts(signal.absent_started_at)
                if absent_since is None:
                    continue
                if (ref - absent_since).total_seconds() < room.presence_policy.grace_seconds:
                    continue
                signal.hold_started_at = room.presence_hold_started_at or ref.isoformat()
                changed = self._set_presence_hold(
                    room,
                    pid,
                    participant.name,
                    hold_reason,
                    now=ref,
                ) or changed
                break
        if changed:
            self._commit(room)
        return changed

    def touch(self, room_id: str, participant_id: str, *, now: Optional[datetime] = None) -> None:
        """Refresh a learner's presence heartbeat (called on the client tick)."""
        room = self.require(room_id)
        p = room.participants.get(participant_id)
        if p is None or p.is_host:
            return
        p.last_seen = now.isoformat() if now else _ts()
        self._commit(room)

    def prune_stale(
        self,
        room_id: str,
        *,
        ttl_seconds: int = 45,
        now: Optional[datetime] = None,
    ) -> List[str]:
        """Remove learners whose presence heartbeat went stale — i.e. they closed
        the browser/app (or lost connection) without leaving. Releases the floor
        and clears their Q&A queue entries. Returns the removed display names."""
        room = self.require(room_id)
        ref = now or _now()
        removed: List[str] = []
        for pid, p in list(room.participants.items()):
            if p.is_host:
                continue
            seen = _parse_ts(p.last_seen or p.joined_at)
            if seen is None:
                continue
            if (ref - seen).total_seconds() <= ttl_seconds:
                continue
            # Stale: drop them and clean up any floor/queue state they held.
            if room.floor_participant_id == pid:
                room.floor_participant_id = ""
            room.speaking_queue = [
                e for e in room.speaking_queue
                if e.participant_id != pid or e.status == QUEUE_DONE
            ]
            room.participants.pop(pid, None)
            room.presence_signals.pop(pid, None)
            if room.presence_hold_active and room.presence_hold_participant_id == pid:
                room.presence_hold_active = False
                room.presence_hold_participant_id = ""
                room.presence_hold_reason = ""
                room.presence_hold_started_at = ""
            removed.append(p.name)
        if removed:
            room._reindex_waiting()
            room.viewer_count = room.learner_count
            room.chat.append(
                ChatMessage(
                    id=uuid.uuid4().hex[:10],
                    from_id="system",
                    from_name="Room",
                    text=f"{', '.join(removed)} left the class.",
                )
            )
            self._commit(room)
        return removed

    def note_slide_started(self, room_id: str, *, now: Optional[datetime] = None) -> None:
        """Reset the per-slide auto-advance timer (call after a slide change)."""
        room = self.require(room_id)
        room.slide_started_at = now.isoformat() if now else _ts()
        self._commit(room)

    def rebind_session(self, room_id: str, session_id: str) -> None:
        """Point the room at a new teaching session id — used to recover after the
        orchestrator lost in-memory sessions (restart) so slides can advance again."""
        room = self.require(room_id)
        room.session_id = session_id
        self._commit(room)

    def auto_call_next_if_waiting(self, room_id: str) -> Optional[Participant]:
        """AI picks up the next raised hand at a natural break (e.g. between
        slides) — only when no one currently holds the floor and someone is
        waiting. Returns the new speaker, or None if nothing to do. Best-effort:
        never raises for the 'empty queue / already speaking' cases."""
        room = self.require(room_id)
        if room.floor_participant_id or not room.waiting_queue():
            return None
        return self.call_next(room_id)

    def next_unanswered_question(self, room_id: str) -> Optional[QueueEntry]:
        """The next waiting Q&A entry that carries a typed question, when nobody
        currently holds the floor. Lets the AI host pause and answer queued
        questions itself (no human moderator needed)."""
        room = self.require(room_id)
        if room.floor_participant_id:
            return None
        for entry in room.waiting_queue():
            if (entry.question or "").strip():
                return entry
        return None

    def resolve_question(self, room_id: str, entry_id: str) -> bool:
        """Mark a queued question answered (DONE) and lower the asker's hand if
        they have no other pending entry. Returns True if something changed."""
        room = self.require(room_id)
        pid = ""
        for entry in room.speaking_queue:
            if entry.id == entry_id and entry.status == QUEUE_WAITING:
                entry.status = QUEUE_DONE
                pid = entry.participant_id
        if not pid:
            return False
        still_pending = any(
            e.participant_id == pid and e.status in (QUEUE_WAITING, QUEUE_SPEAKING)
            for e in room.speaking_queue
        )
        if not still_pending:
            p = room.participants.get(pid)
            if p:
                p.hand_raised = False
        room._reindex_waiting()
        self._commit(room)
        return True

    def finish_turn(self, room_id: str, participant_id: str, *, moderator_key: str = "") -> None:
        """End the current speaker's turn and release the floor."""
        room = self.require(room_id)
        if moderator_key:
            room.verify_moderator(moderator_key)
        if room.floor_participant_id != participant_id:
            if moderator_key:
                raise LiveRoomError("this learner does not have the floor")
            return
        try:
            p = room.get_participant(participant_id)
        except (KeyError, LiveRoomError):
            # Participant already left — still clear floor state
            room.floor_participant_id = ""
            for entry in room.speaking_queue:
                if entry.participant_id == participant_id and entry.status == QUEUE_SPEAKING:
                    entry.status = QUEUE_DONE
            room._reindex_waiting()
            self._commit(room)
            return
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
        if len(q) > QUESTION_MAX_CHARS:
            raise LiveRoomError(f"question is too long (max {QUESTION_MAX_CHARS} characters)")
        # Anti-spam: cap how often a participant can fire questions at Theodore.
        self._enforce_rate(
            room_id, participant_id, "ask",
            max_events=ASK_RATE_MAX, window_s=ASK_RATE_WINDOW_S,
            message="you're asking questions too fast — please wait a moment",
        )
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
        # Anti-abuse: cap how fast one learner can file reports (harassment guard).
        self._enforce_rate(
            room_id, reporter_participant_id, "report",
            max_events=REPORT_RATE_MAX, window_s=REPORT_RATE_WINDOW_S,
            message="you're filing reports too fast — please wait a moment",
        )
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
            account_id=target.account_id or "",
        )
        room.banned[target.identity] = entry
        name = target.name
        self._remove_from_queue(room, participant_id)
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
        if recipient_id == sender_participant_id:
            raise LiveRoomError("you can't send a gift to yourself")
        recipient = room.get_participant(recipient_id)
        # Anti-spam: cap gift frequency (points balance already gates volume).
        self._enforce_rate(
            room_id, sender_participant_id, "gift",
            max_events=GIFT_RATE_MAX, window_s=GIFT_RATE_WINDOW_S,
            message="you're sending gifts too fast — please slow down",
        )
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
        # Anti-spam: cap reaction frequency (they broadcast to every client).
        self._enforce_rate(
            room_id, participant_id, "react",
            max_events=REACT_RATE_MAX, window_s=REACT_RATE_WINDOW_S,
            message="you're reacting too fast — please slow down",
        )
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

    def end_room(self, room_id: str, *, auto: bool = False) -> LiveRoom:
        room = self.require(room_id)
        if room.status == "ended":
            return room  # idempotent: a client tick may fire the auto-end twice
        if room.recording.status == RECORDING_ACTIVE:
            self.stop_recording(room_id)
        room.status = "ended"
        room.presenting = False
        room.floor_participant_id = ""
        room.presence_hold_active = False
        room.presence_hold_participant_id = ""
        room.presence_hold_reason = ""
        room.presence_hold_started_at = ""
        room.ended_at = _ts()
        text = (
            "🎓 That's our allotted time for today — the class is now complete. "
            "Thank you so much for attending and for your wonderful participation. "
            "It was a pleasure learning with you; see you in the next session!"
            if auto
            else "Class dismissed. Thank you for attending — see you next time!"
        )
        room.chat.append(
            ChatMessage(
                id=uuid.uuid4().hex[:10],
                from_id=room.system_host_identity()[0],
                from_name=room.system_host_identity()[1],
                text=text,
            )
        )
        self._commit(room)
        return room
