"""Scheduled group classes the AI drives through external meeting platforms.

A *group class* is a scheduled, multi-learner session: an educator picks a
lesson, a platform (Zoom / Microsoft Teams / Google Meet, or the built-in
Salareen room), a start time and a capacity. Learners browse the upcoming
schedule and register. At class time the AI teaching brain joins the meeting
(via the media bridge in :mod:`aoep_shared.bridges`) and presents the
coursework — slides + narration + live Q&A — through that meeting platform.

This module is the pure, dependency-free scheduling core: the data model, an
in-memory store with capacity/registration rules, and the *bridge plan* that
ties a class to the bridge engine. It is fully usable and testable without any
meeting-platform SDK; the orchestrator service exposes it over HTTP.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Mapping, Optional

# Platforms a class can run on. The three external ones map onto
# aoep_shared.bridges.BridgePlatform; "salareen" is the built-in LiveKit room
# (no external bridge needed — learners join the web/app live class directly).
PLATFORMS: tuple = ("salareen", "zoom", "teams", "meet")

# Platforms that require a media bridge into an external meeting.
BRIDGED_PLATFORMS: tuple = ("zoom", "teams", "meet")

# Lifecycle states.
STATUS_SCHEDULED = "scheduled"
STATUS_LIVE = "live"
STATUS_ENDED = "ended"
_STATUSES = (STATUS_SCHEDULED, STATUS_LIVE, STATUS_ENDED)


class GroupClassError(ValueError):
    """Invalid scheduling/registration request (maps to HTTP 400)."""


class ClassFullError(GroupClassError):
    """Raised when a learner registers for a class with no seats left."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, tolerating a trailing ``Z`` and naive input."""
    if not value or not str(value).strip():
        raise GroupClassError("start_time is required")
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise GroupClassError(f"invalid start_time {value!r}: {exc}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class Registration:
    name: str
    email: str = ""
    registered_at: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise GroupClassError("registration name is required")
        self.name = self.name.strip()
        self.email = (self.email or "").strip()
        if not self.registered_at:
            self.registered_at = _now().isoformat()


@dataclass
class GroupClass:
    title: str
    lesson_id: str
    platform: str = "salareen"
    meeting_url: str = ""          # external join URL/id (empty for "salareen")
    start_time: str = ""           # ISO-8601
    duration_min: int = 60
    host: str = "Salareen AI"
    capacity: int = 100
    language: str = "en"
    description: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = STATUS_SCHEDULED
    registrations: List[Registration] = field(default_factory=list)
    session_id: str = ""           # set when the class goes live
    bridge_session_id: str = ""    # set when the meeting bridge is connected

    def __post_init__(self) -> None:
        self.title = (self.title or "").strip()
        if not self.title:
            raise GroupClassError("title is required")
        if not self.lesson_id or not str(self.lesson_id).strip():
            raise GroupClassError("lesson_id is required")
        self.lesson_id = str(self.lesson_id).strip()
        self.platform = (self.platform or "salareen").strip().lower()
        if self.platform not in PLATFORMS:
            raise GroupClassError(
                f"unknown platform {self.platform!r}; expected one of {', '.join(PLATFORMS)}"
            )
        self.meeting_url = (self.meeting_url or "").strip()
        if self.platform in BRIDGED_PLATFORMS and not self.meeting_url:
            raise GroupClassError(
                f"{self.platform} classes need a meeting_url (the join link learners use)"
            )
        # Normalize + validate the start time (raises on bad input).
        self.start_time = _parse_iso(self.start_time).isoformat()
        self.duration_min = int(self.duration_min)
        if self.duration_min <= 0:
            raise GroupClassError("duration_min must be positive")
        self.capacity = int(self.capacity)
        if self.capacity <= 0:
            raise GroupClassError("capacity must be positive")
        if self.status not in _STATUSES:
            raise GroupClassError(f"invalid status {self.status!r}")

    @property
    def start_dt(self) -> datetime:
        return _parse_iso(self.start_time)

    @property
    def seats_left(self) -> int:
        return max(0, self.capacity - len(self.registrations))

    @property
    def is_full(self) -> bool:
        return self.seats_left <= 0

    @property
    def needs_bridge(self) -> bool:
        return self.platform in BRIDGED_PLATFORMS

    def to_dict(self) -> dict:
        d = asdict(self)
        d["seats_left"] = self.seats_left
        d["registered"] = len(self.registrations)
        d["needs_bridge"] = self.needs_bridge
        return d


class GroupClassStore:
    """In-memory registry of scheduled group classes (process-local)."""

    def __init__(self) -> None:
        self._classes: Dict[str, GroupClass] = {}

    def schedule(self, **kwargs) -> GroupClass:
        gc = GroupClass(**kwargs)
        self._classes[gc.id] = gc
        return gc

    def add(self, gc: GroupClass) -> GroupClass:
        self._classes[gc.id] = gc
        return gc

    def get(self, class_id: str) -> Optional[GroupClass]:
        return self._classes.get(class_id)

    def require(self, class_id: str) -> GroupClass:
        gc = self._classes.get(class_id)
        if gc is None:
            raise KeyError(class_id)
        return gc

    def list(
        self,
        *,
        upcoming_only: bool = False,
        include_ended: bool = True,
        now: Optional[datetime] = None,
    ) -> List[GroupClass]:
        """Return classes sorted by start time (soonest first).

        ``upcoming_only`` keeps classes that have not yet ended (start time + a
        grace window of their duration is still in the future, OR they are
        currently live). ``include_ended`` drops classes already marked ended.
        """
        ref = now or _now()
        items = list(self._classes.values())
        if not include_ended:
            items = [c for c in items if c.status != STATUS_ENDED]
        if upcoming_only:
            def still_relevant(c: GroupClass) -> bool:
                if c.status == STATUS_LIVE:
                    return True
                if c.status == STATUS_ENDED:
                    return False
                # scheduled: keep until the class would have finished.
                end = c.start_dt.timestamp() + c.duration_min * 60
                return end >= ref.timestamp()
            items = [c for c in items if still_relevant(c)]
        items.sort(key=lambda c: c.start_dt)
        return items

    def register(self, class_id: str, name: str, email: str = "") -> Registration:
        gc = self.require(class_id)
        if gc.status == STATUS_ENDED:
            raise GroupClassError("this class has already ended")
        reg = Registration(name=name, email=email)
        if reg.email:
            for existing in gc.registrations:
                if existing.email and existing.email.lower() == reg.email.lower():
                    return existing  # idempotent: already registered with this email
        if gc.is_full:
            raise ClassFullError("this class is full")
        gc.registrations.append(reg)
        return reg

    def set_status(self, class_id: str, status: str) -> GroupClass:
        if status not in _STATUSES:
            raise GroupClassError(f"invalid status {status!r}")
        gc = self.require(class_id)
        gc.status = status
        return gc


def bridge_plan(gc: GroupClass, *, livekit_room: str = "") -> Mapping[str, object]:
    """Describe how the AI joins this class's meeting to present the coursework.

    The plan is what an educator/operator (or the orchestrator's ``start``
    endpoint) feeds to the media bridge: which platform, the meeting reference,
    and the LiveKit room the teaching brain runs in. For "salareen" classes no
    external bridge is needed — learners join the built-in live room directly.
    """
    room = livekit_room or f"class-{gc.id}"
    if not gc.needs_bridge:
        return {
            "needs_bridge": False,
            "platform": gc.platform,
            "livekit_room": room,
            "join_url": gc.meeting_url or "",
            "note": "Built-in Salareen room — learners join the live class directly.",
        }
    return {
        "needs_bridge": True,
        "platform": gc.platform,
        "meeting_ref": gc.meeting_url,
        "livekit_room": room,
        "connect_endpoint": f"/bridges/{gc.platform}/connect",
        "note": (
            f"Connect the bridge (integrations {gc.platform}/connect) to pipe the "
            "AI's LiveKit room into the meeting so the AI presents through "
            f"{gc.platform}."
        ),
    }
