"""Accounts + portfolios (enrollments, status, subscription).

In-memory store mirroring the other services (Postgres in production - see the
accounts/subscriptions tables in db/migrations). Holds the user account, their
membership tier, and their course portfolio (Netflix-style "my list" + history
of taken/passed/failed courses). Mastery lives in the memory service; payments in
billing - the portfolio references them.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Dict, List, Optional

from aoep_shared.auth import hash_password, verify_password
from aoep_shared.schemas import PlanTier, Region
from pydantic import BaseModel, Field


class EnrollmentStatus(str, enum.Enum):
    SAVED = "saved"            # added to "my list" / watchlist
    ENROLLED = "enrolled"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"


class Enrollment(BaseModel):
    course_id: str
    title: str = ""
    status: EnrollmentStatus = EnrollmentStatus.ENROLLED
    score: Optional[float] = None
    enrolled_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class Account(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    email: str
    display_name: str = ""
    password_hash: str = ""
    tier: PlanTier = PlanTier.FREE
    region: Region = Region.US
    created_at: float = Field(default_factory=lambda: time.time())
    # Security signals.
    last_login_at: Optional[float] = None
    failed_logins: int = 0
    enrollments: Dict[str, Enrollment] = Field(default_factory=dict)

    def public(self) -> dict:
        return {
            "id": self.id, "email": self.email, "display_name": self.display_name,
            "tier": self.tier.value, "region": self.region.value,
            "created_at": self.created_at, "last_login_at": self.last_login_at,
        }


class AccountStore:
    def __init__(self) -> None:
        self._by_id: Dict[str, Account] = {}
        self._id_by_email: Dict[str, str] = {}

    def create(self, email: str, password: str, *, display_name: str = "",
               tier: PlanTier = PlanTier.FREE, region: Region = Region.US) -> Account:
        email = email.strip().lower()
        if not email or "@" not in email:
            raise ValueError("a valid email is required")
        if email in self._id_by_email:
            raise ValueError("an account with that email already exists")
        acct = Account(email=email, display_name=display_name or email.split("@")[0],
                       password_hash=hash_password(password), tier=tier, region=region)
        self._by_id[acct.id] = acct
        self._id_by_email[email] = acct.id
        return acct

    def by_email(self, email: str) -> Optional[Account]:
        aid = self._id_by_email.get(email.strip().lower())
        return self._by_id.get(aid) if aid else None

    def by_id(self, account_id: str) -> Optional[Account]:
        return self._by_id.get(account_id)

    def authenticate(self, email: str, password: str) -> Optional[Account]:
        acct = self.by_email(email)
        if acct is None:
            return None
        if not verify_password(password, acct.password_hash):
            acct.failed_logins += 1
            return None
        acct.failed_logins = 0
        acct.last_login_at = time.time()
        return acct

    def set_password(self, account_id: str, new_password: str) -> None:
        acct = self._by_id[account_id]
        acct.password_hash = hash_password(new_password)

    def set_tier(self, account_id: str, tier: PlanTier) -> Account:
        acct = self._by_id[account_id]
        acct.tier = tier
        return acct

    # --- portfolio --------------------------------------------------------- #
    def upsert_enrollment(self, account_id: str, enrollment: Enrollment) -> Enrollment:
        acct = self._by_id[account_id]
        existing = acct.enrollments.get(enrollment.course_id)
        if existing:
            existing.status = enrollment.status
            if enrollment.score is not None:
                existing.score = enrollment.score
            if enrollment.title:
                existing.title = enrollment.title
            existing.updated_at = time.time()
            return existing
        acct.enrollments[enrollment.course_id] = enrollment
        return enrollment

    def set_status(self, account_id: str, course_id: str, status: EnrollmentStatus,
                   *, score: Optional[float] = None) -> Enrollment:
        acct = self._by_id[account_id]
        enr = acct.enrollments.get(course_id)
        if enr is None:
            raise KeyError(course_id)
        enr.status = status
        if score is not None:
            enr.score = score
        enr.updated_at = time.time()
        return enr

    def enrollments(self, account_id: str) -> List[Enrollment]:
        return list(self._by_id[account_id].enrollments.values())
