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

import hashlib
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

# User-created marketplace classes require human audit before learners can join.
AUDIT_PENDING = "pending"
AUDIT_APPROVED = "approved"
AUDIT_REJECTED = "rejected"
_AUDIT_STATUSES = (AUDIT_PENDING, AUDIT_APPROVED, AUDIT_REJECTED)

PAYMENT_UNPAID = "unpaid"
PAYMENT_PENDING = "pending"
PAYMENT_PAID = "paid"
_PAYMENT_STATUSES = (PAYMENT_UNPAID, PAYMENT_PENDING, PAYMENT_PAID)

# Paid classes with enrolled students require the host to check in at least this
# many seconds before the scheduled start.
HOST_EARLY_SECONDS = 300


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
    account_id: str = ""
    payment_status: str = PAYMENT_UNPAID
    checkout_session_id: str = ""
    attendee_code: str = ""
    attendee_code_bound_identity: str = ""
    attendee_code_used: bool = False
    registered_at: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise GroupClassError("registration name is required")
        self.name = self.name.strip()
        self.email = (self.email or "").strip()
        self.account_id = (self.account_id or "").strip()
        self.payment_status = (self.payment_status or PAYMENT_UNPAID).strip().lower()
        if self.payment_status not in _PAYMENT_STATUSES:
            raise GroupClassError(f"invalid payment_status {self.payment_status!r}")
        self.checkout_session_id = (self.checkout_session_id or "").strip()
        self.attendee_code = (self.attendee_code or "").strip().upper()
        self.attendee_code_bound_identity = (self.attendee_code_bound_identity or "").strip()
        if not self.registered_at:
            self.registered_at = _now().isoformat()


@dataclass
class InstructorReview:
    reviewer_name: str
    rating: int
    comment: str = ""
    reviewer_account_id: str = ""
    created_at: str = ""
    verified_attendee: bool = False

    def __post_init__(self) -> None:
        self.reviewer_name = (self.reviewer_name or "").strip()
        if not self.reviewer_name:
            raise GroupClassError("reviewer_name is required")
        self.reviewer_account_id = (self.reviewer_account_id or "").strip()
        self.comment = (self.comment or "").strip()
        self.rating = int(self.rating)
        if self.rating < 1 or self.rating > 5:
            raise GroupClassError("rating must be between 1 and 5")
        if not self.created_at:
            self.created_at = _now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


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
    audience: str = "general"
    description: str = ""
    created_by_account_id: str = ""
    instructor_account_id: str = ""
    # True when a person teaches this class ("Teach a class"). instructor_account_id
    # cannot carry this on its own: it falls back to created_by_account_id, so a
    # student-scheduled study group would look instructor-led and lose Theodore.
    human_taught: bool = False
    instructor_name: str = ""
    marketplace_listing: bool = False
    audit_required: bool = False
    audit_status: str = AUDIT_APPROVED
    credentials_summary: str = ""
    credential_photo_url: str = ""
    identity_photo_url: str = ""
    interview_notes: str = ""
    demo_notes: str = ""
    audited_by: str = ""
    audited_at: str = ""
    price_per_user_usd: float = 0.0
    commission_rate: float = 0.15
    payment_required: bool = False
    attendee_code_required: bool = False
    max_faces_allowed: int = 1
    require_liveness: bool = True
    recording_protection_required: bool = True
    device_profile: str = ""
    camera_ingest_mode: str = "platform_default"
    camera_sources: List[dict] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = STATUS_SCHEDULED
    registrations: List[Registration] = field(default_factory=list)
    reviews: List[InstructorReview] = field(default_factory=list)
    session_id: str = ""           # set when the class goes live
    bridge_session_id: str = ""    # set when the meeting bridge is connected
    live_room_id: str = ""         # Salareen room id (class-{id}) when live
    xr_lab_enabled: bool = False   # optional XR demonstration lab for this class
    presentation_filename: str = ""  # original PDF/PPTX name when host uploaded a deck
    host_checked_in_at: str = ""   # ISO timestamp when the scheduled host joined/went live
    host_payout_usd: float = 0.0     # settled instructor payout after class ends

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
        self.created_by_account_id = (self.created_by_account_id or "").strip()
        self.instructor_account_id = (
            (self.instructor_account_id or "").strip() or self.created_by_account_id
        )
        self.instructor_name = (
            (self.instructor_name or "").strip() or (self.host or "").strip()
        )
        self.marketplace_listing = bool(self.marketplace_listing)
        self.audit_required = bool(self.audit_required or self.marketplace_listing)
        self.audit_status = (self.audit_status or AUDIT_APPROVED).strip().lower()
        if self.audit_status not in _AUDIT_STATUSES:
            raise GroupClassError(
                f"audit_status must be one of {', '.join(_AUDIT_STATUSES)}"
            )
        if self.audit_required and self.audit_status == AUDIT_APPROVED and self.marketplace_listing:
            # New marketplace classes should be reviewed before they go live.
            self.audit_status = AUDIT_PENDING
        self.credentials_summary = (self.credentials_summary or "").strip()
        self.credential_photo_url = (self.credential_photo_url or "").strip()
        self.identity_photo_url = (self.identity_photo_url or "").strip()
        self.interview_notes = (self.interview_notes or "").strip()
        self.demo_notes = (self.demo_notes or "").strip()
        self.audited_by = (self.audited_by or "").strip()
        self.audited_at = (self.audited_at or "").strip()
        self.price_per_user_usd = max(0.0, float(self.price_per_user_usd or 0.0))
        self.commission_rate = float(self.commission_rate or 0.0)
        if self.commission_rate < 0 or self.commission_rate > 1:
            raise GroupClassError("commission_rate must be between 0 and 1")
        self.payment_required = bool(self.payment_required or self.price_per_user_usd > 0)
        self.attendee_code_required = bool(
            self.attendee_code_required or self.payment_required or self.marketplace_listing
        )
        self.max_faces_allowed = max(1, int(self.max_faces_allowed or 1))
        self.require_liveness = bool(self.require_liveness)
        self.recording_protection_required = bool(self.recording_protection_required)
        self.device_profile = (self.device_profile or "").strip().lower()
        self.camera_ingest_mode = (
            (self.camera_ingest_mode or "platform_default").strip().lower()
        )
        self.camera_sources = [
            dict(row) for row in (self.camera_sources or []) if isinstance(row, dict)
        ][:16]
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
        if self.marketplace_listing and self.capacity > 9:
            raise GroupClassError("marketplace classes are limited to 9 learners")
        if self.platform == "salareen" and self.capacity > learner_capacity(self.room_size):
            raise GroupClassError(
                f"salareen capacity cannot exceed {learner_capacity(self.room_size)} "
                f"for a {self.room_size}-seat room"
            )
        if self.status not in _STATUSES:
            raise GroupClassError(f"invalid status {self.status!r}")
        self.presentation_filename = (self.presentation_filename or "").strip()
        self.host_checked_in_at = (self.host_checked_in_at or "").strip()
        self.host_payout_usd = max(0.0, float(self.host_payout_usd or 0.0))

    @property
    def host_account_ids(self) -> List[str]:
        ids: List[str] = []
        for val in (self.instructor_account_id, self.created_by_account_id):
            acct = (val or "").strip()
            if acct and acct not in ids:
                ids.append(acct)
        return ids

    @property
    def practice_session(self) -> bool:
        """True when no paying students registered — host may run without payout."""
        return self.paid_registration_count() == 0

    def paid_registration_count(self) -> int:
        return sum(1 for reg in self.registrations if reg.payment_status == PAYMENT_PAID)

    def record_host_checkin(self, account_id: str) -> None:
        acct = (account_id or "").strip()
        if not acct or acct not in self.host_account_ids:
            return
        now_iso = _now().isoformat()
        if not self.host_checked_in_at:
            self.host_checked_in_at = now_iso
            return
        try:
            existing = _parse_iso(self.host_checked_in_at)
            incoming = _parse_iso(now_iso)
            if incoming < existing:
                self.host_checked_in_at = now_iso
        except GroupClassError:
            self.host_checked_in_at = now_iso

    def host_arrived_early_enough(self) -> bool:
        if not self.host_checked_in_at:
            return False
        try:
            checked = _parse_iso(self.host_checked_in_at)
        except GroupClassError:
            return False
        deadline = self.start_dt.timestamp() - HOST_EARLY_SECONDS
        return checked.timestamp() <= deadline

    def can_start_teaching(self) -> bool:
        if self.practice_session:
            return True
        return self.host_arrived_early_enough()

    def settle_host_payout(self) -> float:
        """Compute instructor payout after class ends; zero for practice sessions."""
        count = self.paid_registration_count()
        if count <= 0 or not self.host_arrived_early_enough():
            self.host_payout_usd = 0.0
            return 0.0
        gross = self.price_per_user_usd * count
        payout = round(gross * (1.0 - self.commission_rate), 2)
        self.host_payout_usd = payout
        return payout

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
        d["review_count"] = len(self.reviews)
        if self.reviews:
            d["review_avg"] = round(
                sum(int(r.rating) for r in self.reviews) / len(self.reviews), 2
            )
        else:
            d["review_avg"] = 0.0
        d["camera_source_count"] = len(self.camera_sources)
        d["external_camera_ingest_supported"] = self.platform in ("teams", "zoom", "meet")
        d["room_size"] = self.room_size
        d["learner_capacity"] = (
            learner_capacity(self.room_size) if self.platform == "salareen" else self.capacity
        )
        d["live_room_id"] = self.live_room_id
        d["practice_session"] = self.practice_session
        d["paid_registration_count"] = self.paid_registration_count()
        d["host_arrived_early_enough"] = self.host_arrived_early_enough()
        d["can_start_teaching"] = self.can_start_teaching()
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

    @staticmethod
    def _mint_attendee_code(class_id: str, account_id: str, seed: str = "") -> str:
        raw = f"{class_id}|{account_id}|{seed}|{uuid.uuid4().hex}".encode()
        digest = hashlib.sha256(raw).hexdigest().upper()
        return f"{digest[:4]}-{digest[4:8]}-{digest[8:12]}"

    @staticmethod
    def _registration_matches(
        reg: Registration,
        *,
        email: str = "",
        account_id: str = "",
        checkout_session_id: str = "",
    ) -> bool:
        if checkout_session_id and reg.checkout_session_id == checkout_session_id:
            return True
        if account_id and reg.account_id and reg.account_id == account_id:
            return True
        if email and reg.email and reg.email.lower() == email.lower():
            return True
        return False

    def register(
        self,
        class_id: str,
        name: str,
        email: str = "",
        *,
        account_id: str = "",
        checkout_session_id: str = "",
        payment_status: str = PAYMENT_UNPAID,
    ) -> Registration:
        gc = self.require(class_id)
        if gc.status == STATUS_ENDED:
            raise GroupClassError("this class has already ended")
        if gc.audit_required and gc.audit_status != AUDIT_APPROVED:
            raise GroupClassError("this class is pending Salareen audit approval")
        pay = (payment_status or PAYMENT_UNPAID).strip().lower()
        if pay not in _PAYMENT_STATUSES:
            raise GroupClassError(
                f"payment_status must be one of {', '.join(_PAYMENT_STATUSES)}"
            )
        if gc.payment_required and pay != PAYMENT_PAID:
            raise GroupClassError("payment must be completed before registration")
        reg = Registration(
            name=name,
            email=email,
            account_id=account_id,
            checkout_session_id=checkout_session_id,
            payment_status=pay,
        )
        for existing in gc.registrations:
            if self._registration_matches(
                existing,
                email=reg.email,
                account_id=reg.account_id,
                checkout_session_id=reg.checkout_session_id,
            ):
                if gc.payment_required and existing.payment_status != PAYMENT_PAID and pay == PAYMENT_PAID:
                    existing.payment_status = PAYMENT_PAID
                if not existing.name:
                    existing.name = reg.name
                if reg.email and not existing.email:
                    existing.email = reg.email
                if reg.account_id and not existing.account_id:
                    existing.account_id = reg.account_id
                if gc.attendee_code_required and not existing.attendee_code and existing.payment_status == PAYMENT_PAID:
                    existing.attendee_code = self._mint_attendee_code(gc.id, existing.account_id or existing.email or existing.name)
                self._commit(gc)
                return existing  # idempotent for same learner/payment session
        if gc.is_full:
            raise ClassFullError("this class is full")
        if gc.attendee_code_required and reg.payment_status == PAYMENT_PAID:
            reg.attendee_code = self._mint_attendee_code(gc.id, reg.account_id or reg.email or reg.name)
        gc.registrations.append(reg)
        self._commit(gc)
        return reg

    def open_checkout(
        self,
        class_id: str,
        *,
        name: str,
        email: str = "",
        account_id: str = "",
        checkout_session_id: str,
    ) -> Registration:
        gc = self.require(class_id)
        if gc.status == STATUS_ENDED:
            raise GroupClassError("this class has already ended")
        if gc.audit_required and gc.audit_status != AUDIT_APPROVED:
            raise GroupClassError("this class is pending Salareen audit approval")
        if gc.is_full:
            raise ClassFullError("this class is full")
        reg = Registration(
            name=name,
            email=email,
            account_id=account_id,
            checkout_session_id=checkout_session_id,
            payment_status=PAYMENT_PENDING,
        )
        for existing in gc.registrations:
            if self._registration_matches(existing, email=reg.email, account_id=reg.account_id):
                existing.checkout_session_id = checkout_session_id
                existing.payment_status = PAYMENT_PENDING
                self._commit(gc)
                return existing
        gc.registrations.append(reg)
        self._commit(gc)
        return reg

    def confirm_checkout(
        self,
        class_id: str,
        *,
        checkout_session_id: str,
        account_id: str = "",
    ) -> Registration:
        gc = self.require(class_id)
        sid = (checkout_session_id or "").strip()
        if not sid:
            raise GroupClassError("checkout_session_id is required")
        for reg in gc.registrations:
            if reg.checkout_session_id != sid:
                continue
            if account_id and reg.account_id and reg.account_id != account_id:
                raise GroupClassError("checkout does not belong to this account")
            reg.payment_status = PAYMENT_PAID
            if gc.attendee_code_required and not reg.attendee_code:
                reg.attendee_code = self._mint_attendee_code(gc.id, reg.account_id or reg.email or reg.name, sid)
            self._commit(gc)
            return reg
        raise GroupClassError("checkout session not found for this class")

    def authorize_attendee(
        self,
        class_id: str,
        *,
        attendee_code: str,
        account_id: str = "",
        identity: str = "",
    ) -> Registration | None:
        """Validate one attendee code per learner and bind first successful join."""
        gc = self.require(class_id)
        code = (attendee_code or "").strip().upper()
        if gc.attendee_code_required and not code:
            raise GroupClassError("attendee code is required for this class")
        if gc.audit_required and gc.audit_status != AUDIT_APPROVED:
            raise GroupClassError("this class is pending Salareen audit approval")
        if not gc.attendee_code_required:
            return None
        ident = (identity or "").strip()
        acct = (account_id or "").strip()
        for reg in gc.registrations:
            if reg.attendee_code != code:
                continue
            if reg.payment_status != PAYMENT_PAID:
                raise GroupClassError("payment must be completed before joining this class")
            if acct and reg.account_id and reg.account_id != acct:
                raise GroupClassError("attendee code does not belong to this account")
            if reg.attendee_code_bound_identity and ident and reg.attendee_code_bound_identity != ident:
                raise GroupClassError("this attendee code is already bound to another participant")
            if not reg.attendee_code_bound_identity and ident:
                reg.attendee_code_bound_identity = ident
            reg.attendee_code_used = True
            self._commit(gc)
            return reg
        raise GroupClassError("invalid attendee code")

    def add_review(
        self,
        class_id: str,
        *,
        reviewer_name: str,
        rating: int,
        comment: str = "",
        reviewer_account_id: str = "",
    ) -> InstructorReview:
        gc = self.require(class_id)
        verified = False
        for reg in gc.registrations:
            if reviewer_account_id and reg.account_id == reviewer_account_id:
                verified = True
                break
            if reviewer_name and reg.name.lower() == reviewer_name.strip().lower():
                verified = True
                break
        review = InstructorReview(
            reviewer_name=reviewer_name,
            rating=rating,
            comment=comment,
            reviewer_account_id=reviewer_account_id,
            verified_attendee=verified,
        )
        for existing in gc.reviews:
            if (
                reviewer_account_id
                and existing.reviewer_account_id
                and existing.reviewer_account_id == reviewer_account_id
            ):
                existing.rating = review.rating
                existing.comment = review.comment
                existing.created_at = review.created_at
                existing.verified_attendee = review.verified_attendee
                self._commit(gc)
                return existing
        gc.reviews.append(review)
        self._commit(gc)
        return review

    def audit_class(
        self,
        class_id: str,
        *,
        approved: bool,
        audited_by: str,
        interview_notes: str = "",
        demo_notes: str = "",
    ) -> GroupClass:
        gc = self.require(class_id)
        gc.audit_required = True
        gc.audit_status = AUDIT_APPROVED if approved else AUDIT_REJECTED
        gc.audited_by = (audited_by or "").strip() or "salareen-employee"
        gc.audited_at = _now().isoformat()
        if interview_notes.strip():
            gc.interview_notes = interview_notes.strip()
        if demo_notes.strip():
            gc.demo_notes = demo_notes.strip()
        self._commit(gc)
        return gc

    def instructor_stats(self, instructor_account_id: str) -> dict:
        iid = (instructor_account_id or "").strip()
        if not iid:
            return {"courses_taught": 0, "review_count": 0, "review_avg": 0.0}
        taught = 0
        ratings: list[int] = []
        for gc in self._all_classes():
            if gc.instructor_account_id != iid:
                continue
            if gc.status in (STATUS_LIVE, STATUS_ENDED):
                taught += 1
            ratings.extend(int(r.rating) for r in gc.reviews)
        avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
        return {"courses_taught": taught, "review_count": len(ratings), "review_avg": avg}

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
    camera_hint = {
        "device_profile": gc.device_profile,
        "camera_ingest_mode": gc.camera_ingest_mode,
        "camera_sources": gc.camera_sources,
        "camera_source_count": len(gc.camera_sources),
    }
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
            **camera_hint,
        }
    note = (
        f"Connect the bridge (integrations {gc.platform}/connect) to pipe the "
        "AI's LiveKit room into the meeting so the AI presents through "
        f"{gc.platform}."
    )
    if gc.platform == "teams":
        note += (
            " Teams bridge can ingest external room-device cameras (for example "
            "Cisco room kits and iPad camera sources) when provided in "
            "camera_sources during bridge connect."
        )
    return {
        "needs_bridge": True,
        "platform": gc.platform,
        "meeting_ref": gc.meeting_url,
        "livekit_room": room,
        "connect_endpoint": f"/bridges/{gc.platform}/connect",
        "supports_external_camera_ingest": gc.platform == "teams",
        "camera_ingest_endpoint": (
            f"/bridges/{gc.platform}/connect" if gc.platform == "teams" else ""
        ),
        "note": note,
        **camera_hint,
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
