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
from typing import List, Mapping, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .group_class_backend import GroupClassBackend

from .live_room import learner_capacity, validate_room_size

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
    room_size: int = 6  # Salareen grid: 4, 6, or 9 total seats including AI host
    language: str = "en"
    description: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = STATUS_SCHEDULED
    registrations: List[Registration] = field(default_factory=list)
    session_id: str = ""           # set when the class goes live
    bridge_session_id: str = ""    # set when the meeting bridge is connected
    live_room_id: str = ""         # Salareen room id (class-{id}) when live

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
        self.room_size = int(self.room_size)
        if self.platform == "salareen":
            self.room_size = validate_room_size(self.room_size)
            max_learners = learner_capacity(self.room_size)
            if self.capacity > max_learners:
                self.capacity = max_learners
        else:
            self.room_size = 6
        self.capacity = int(self.capacity)
        if self.capacity <= 0:
            raise GroupClassError("capacity must be positive")
        if self.platform == "salareen" and self.capacity > learner_capacity(self.room_size):
            raise GroupClassError(
                f"salareen capacity cannot exceed {learner_capacity(self.room_size)} "
                f"for a {self.room_size}-seat room"
            )
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
        d["room_size"] = self.room_size
        d["learner_capacity"] = (
            learner_capacity(self.room_size) if self.platform == "salareen" else self.capacity
        )
        d["live_room_id"] = self.live_room_id
        return d


class GroupClassStore:
    """Registry of scheduled group classes.

    In-memory locally; on Vultr VKE (``REDIS_URL`` set) classes are stored in
    Redis so start/join flows work on any orchestrator replica.
    """

    def __init__(self, backend: Optional["GroupClassBackend"] = None) -> None:
        if backend is None:
            from .group_class_backend import build_group_class_backend

            backend = build_group_class_backend()
        self._backend = backend

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def _commit(self, gc: GroupClass) -> None:
        self._backend.save(gc)

    def _all_classes(self) -> List[GroupClass]:
        items: List[GroupClass] = []
        for class_id in self._backend.list_ids():
            gc = self._backend.get(class_id)
            if gc is not None:
                items.append(gc)
        return items

    def schedule(self, **kwargs) -> GroupClass:
        gc = GroupClass(**kwargs)
        self._commit(gc)
        return gc

    def add(self, gc: GroupClass) -> GroupClass:
        self._commit(gc)
        return gc

    def save(self, gc: GroupClass) -> GroupClass:
        """Persist field updates (session_id, live_room_id, etc.)."""
        self._commit(gc)
        return gc

    def get(self, class_id: str) -> Optional[GroupClass]:
        return self._backend.get(class_id)

    def require(self, class_id: str) -> GroupClass:
        gc = self._backend.get(class_id)
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
        # Remove classes whose time is fully over (auto-delete), then retire any
        # just-ended ones so nothing past its window lingers as joinable.
        self.purge_expired(now=ref)
        self.sweep_expired(now=ref)
        items = self._all_classes()
        if not include_ended:
            items = [c for c in items if c.status != STATUS_ENDED]
        if upcoming_only:
            def still_relevant(c: GroupClass) -> bool:
                if c.status == STATUS_ENDED:
                    return False
                # Keep until the scheduled window (start + duration) has passed —
                # this now applies to LIVE too, so a class that was started/lazy-
                # opened but never closed doesn't show as joinable forever.
                end = c.start_dt.timestamp() + c.duration_min * 60
                return end >= ref.timestamp()
            items = [c for c in items if still_relevant(c)]
        items.sort(key=lambda c: c.start_dt)
        return items

    def sweep_expired(self, *, now: Optional[datetime] = None) -> int:
        """Mark any non-ended class whose scheduled window (start + duration) has
        fully passed as ENDED, so stale 'LIVE' classes get cleaned up instead of
        lingering as joinable. Returns how many were retired."""
        ref = now or _now()
        retired = 0
        for c in self._all_classes():
            if c.status == STATUS_ENDED:
                continue
            end = c.start_dt.timestamp() + c.duration_min * 60
            if end < ref.timestamp():
                c.status = STATUS_ENDED
                self._commit(c)
                retired += 1
        return retired

    def delete(self, class_id: str) -> None:
        """Remove a class entirely from the store."""
        self._backend.delete(class_id)

    def purge_expired(self, *, grace_seconds: int = 120, now: Optional[datetime] = None) -> int:
        """Delete classes whose scheduled window (start + duration) finished more
        than ``grace_seconds`` ago, so past classes are removed entirely (not just
        hidden) — the "auto-delete once the allotted time has finished" cleanup.
        The short grace lets a just-ended class show its farewell first. Returns
        how many were deleted."""
        ref = now or _now()
        removed = 0
        for c in self._all_classes():
            end = c.start_dt.timestamp() + c.duration_min * 60 + grace_seconds
            if end < ref.timestamp():
                self._backend.delete(c.id)
                removed += 1
        return removed

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
        self._commit(gc)
        return reg

    def set_status(self, class_id: str, status: str) -> GroupClass:
        if status not in _STATUSES:
            raise GroupClassError(f"invalid status {status!r}")
        gc = self.require(class_id)
        gc.status = status
        self._commit(gc)
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
            "live_room_id": gc.live_room_id or room,
            "room_size": gc.room_size,
            "join_path": f"/live-room/{gc.live_room_id or room}",
            "join_url": gc.meeting_url or "",
            "note": (
                "Built-in Salareen live room — join the multi-user grid "
                f"({gc.room_size} seats, AI host Theodore)."
            ),
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


def google_meet_url(class_id: str) -> str:
    """Deterministic placeholder Google Meet join link for a scheduled class."""
    import hashlib

    h = hashlib.sha256(class_id.encode()).hexdigest()
    alphabet = "abcdefghijklmnopqrstuvwxyz"

    def part(start: int, length: int) -> str:
        return "".join(alphabet[int(h[i : i + 2], 16) % 26] for i in range(start, start + length * 2, 2))

    return f"https://meet.google.com/{part(0, 3)}-{part(6, 4)}-{part(14, 3)}"


def calendar_ics(
    gc: GroupClass,
    *,
    attendee_name: str = "",
    attendee_email: str = "",
) -> str:
    """Build a minimal .ics invite learners can add to phone or desktop calendar."""
    start = gc.start_dt
    from datetime import timedelta

    end = start + timedelta(minutes=gc.duration_min)

    def fmt(dt) -> str:
        return dt.strftime("%Y%m%dT%H%M%SZ")

    join = gc.meeting_url or google_meet_url(gc.id)
    desc = (gc.description or f"Salareen group class: {gc.title}").replace("\n", "\\n")
    if join:
        desc += f"\\nJoin: {join}"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Salareen//Group Classes//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:group-class-{gc.id}@salareen.com",
        f"DTSTAMP:{fmt(_now())}",
        f"DTSTART:{fmt(start)}",
        f"DTEND:{fmt(end)}",
        f"SUMMARY:{gc.title}",
        f"DESCRIPTION:{desc}",
        f"LOCATION:{join}",
        f"URL:{join}",
    ]
    if attendee_email:
        lines.append(f"ATTENDEE;CN={attendee_name or attendee_email}:MAILTO:{attendee_email}")
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\r\n".join(lines) + "\r\n"


def standard_class_id(platform: str, lesson_id: str, start_iso: str) -> str:
    """Stable id for a seeded standard class.

    Derived from (platform, lesson, start time) so EVERY orchestrator replica —
    and every process restart — produces the exact same id for the same logical
    class. That's what lets a class listed by one replica be started on another
    (previously the id was random per replica → "unknown group class" 404).
    """
    import hashlib

    h = hashlib.sha1(f"{platform}|{lesson_id}|{start_iso}".encode()).hexdigest()
    return f"std{h[:9]}"


def ensure_standard_daily_classes(
    store: GroupClassStore,
    *,
    lesson_ids: Optional[List[str]] = None,
    days_ahead: int = 14,
    tz_name: str = "America/New_York",
) -> int:
    """Seed bookable standard classes at noon and 5pm daily on Google Meet."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    lessons = [lid for lid in (lesson_ids or []) if lid]
    if not lessons:
        lessons = ["intro-to-fractions", "intro-to-photosynthesis"]
    tz = ZoneInfo(tz_name)
    now_local = _now().astimezone(tz)
    created = 0
    slot_hours = (12, 17)
    salareen_hours = (10, 15)
    titles = {
        12: "Standard Group Class — Midday",
        17: "Standard Group Class — Evening",
    }
    salareen_titles = {
        10: "Salareen Live Class — Morning",
        15: "Salareen Live Class — Afternoon",
    }
    # Snapshot existing classes once (not per-slot) and dedup by BOTH the logical
    # slot key and the deterministic id, so re-seeding is idempotent even against
    # legacy random-id rows.
    existing = store.list(upcoming_only=False)
    seen_keys = {(c.platform, c.start_time, c.lesson_id) for c in existing}
    seen_ids = {c.id for c in existing}

    def _seed(platform: str, hour: int, title: str, day_offset: int, hours: tuple,
              **extra) -> None:
        nonlocal created
        start_local = datetime(day.year, day.month, day.day, hour, 0, tzinfo=tz)
        if start_local <= now_local:
            return
        start_iso = start_local.astimezone(timezone.utc).isoformat()
        lesson_id = lessons[(day_offset * len(hours) + hours.index(hour)) % len(lessons)]
        cid = standard_class_id(platform, lesson_id, start_iso)
        if (platform, start_iso, lesson_id) in seen_keys or cid in seen_ids:
            return
        store.schedule(
            id=cid, title=title, lesson_id=lesson_id, platform=platform,
            start_time=start_iso, duration_min=60, language="en", **extra,
        )
        seen_keys.add((platform, start_iso, lesson_id))
        seen_ids.add(cid)
        created += 1

    for day_offset in range(days_ahead):
        day = (now_local + timedelta(days=day_offset)).date()
        for hour in slot_hours:
            start_iso = datetime(day.year, day.month, day.day, hour, 0, tzinfo=tz) \
                .astimezone(timezone.utc).isoformat()
            lesson_id = lessons[(day_offset * len(slot_hours) + slot_hours.index(hour)) % len(lessons)]
            _seed(
                "meet", hour, titles[hour], day_offset, slot_hours,
                meeting_url=google_meet_url(standard_class_id("meet", lesson_id, start_iso)),
                host="Salareen AI", capacity=100,
                description="Daily standard group class on Google Meet. Book to receive a calendar invite.",
            )
        for hour in salareen_hours:
            _seed(
                "salareen", hour, salareen_titles[hour], day_offset, salareen_hours,
                meeting_url="", host="Theodore (AI)", capacity=5, room_size=6,
                description="In-app Salareen live room with Theodore. Tap Start to go live, then Join.",
            )
    return created
