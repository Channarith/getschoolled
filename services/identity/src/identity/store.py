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
from aoep_shared.rewards import PointsLedger
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
    level: str = "beginner"
    hands_on: bool = False
    points_awarded: bool = False   # guard against double-awarding on re-pass
    enrolled_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class StudentProfile(BaseModel):
    """A learner sub-profile under an account (one account, many students -
    like Netflix profiles). Each carries its own mastery + history so Foresight
    can recommend and adapt PER STUDENT."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    display_name: str
    age_band: str = "adult"            # child | teen | adult
    mastery: Dict[str, float] = Field(default_factory=dict)   # skill -> [0,1]
    completed_course_ids: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())


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
    # Learner sub-profiles (one account, multiple students).
    students: Dict[str, StudentProfile] = Field(default_factory=dict)
    # Rewards: points ledger + redemptions (pydantic-excluded; managed in-store).
    points: PointsLedger = Field(default_factory=PointsLedger, exclude=True)
    redemptions: List[dict] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

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
        # Arcade leaderboard: account_id -> aggregate game stats.
        self._game_stats: Dict[str, dict] = {}

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
                   *, score: Optional[float] = None, level: Optional[str] = None,
                   hands_on: Optional[bool] = None) -> Enrollment:
        acct = self._by_id[account_id]
        enr = acct.enrollments.get(course_id)
        if enr is None:
            raise KeyError(course_id)
        enr.status = status
        if score is not None:
            enr.score = score
        if level is not None:
            enr.level = level
        if hands_on is not None:
            enr.hands_on = hands_on
        enr.updated_at = time.time()
        # Reward points on the FIRST transition to passed (idempotent).
        if status is EnrollmentStatus.PASSED and not enr.points_awarded:
            from aoep_shared.rewards import points_for_completion

            pts = points_for_completion(enr.level, passed=True, score=enr.score,
                                        hands_on=enr.hands_on)
            acct.points.earn(pts, reason="course_passed", ref=course_id)
            enr.points_awarded = True
        return enr

    # --- rewards ----------------------------------------------------------- #
    def points_balance(self, account_id: str) -> int:
        return self._by_id[account_id].points.balance

    def redeem(self, account_id: str, prize) -> dict:
        from aoep_shared.rewards import redeem_prize

        acct = self._by_id[account_id]
        redemption = redeem_prize(acct.points, prize)
        rec = {
            "prize_id": redemption.prize_id, "kind": redemption.kind,
            "cost_points": redemption.cost_points, "voucher_code": redemption.voucher_code,
            "percent": redemption.percent, "raffle_entry_id": redemption.raffle_entry_id,
            "detail": redemption.detail, "created_at": redemption.created_at,
        }
        acct.redemptions.append(rec)
        return rec

    def rewards_summary(self, account_id: str) -> dict:
        acct = self._by_id[account_id]
        return {
            "balance": acct.points.balance,
            "ledger": [{"delta": e.delta, "reason": e.reason, "ref": e.ref, "ts": e.ts}
                       for e in acct.points.entries[-25:]],
            "redemptions": acct.redemptions,
        }

    def enrollments(self, account_id: str) -> List[Enrollment]:
        return list(self._by_id[account_id].enrollments.values())

    # --- learning games / arcade ------------------------------------------ #
    def record_game(self, account_id: str, *, subject: str, game_type: str,
                    score: dict, player_name: str = "") -> dict:
        """Award game points to the account ledger + update the leaderboard.

        `score` is the dict form of games.ScoreResult. Returns the updated
        per-player stats. Points feed the same rewards ledger (redeemable).
        """
        acct = self._by_id[account_id]
        pts = int(score.get("points", 0))
        if pts > 0:
            acct.points.earn(pts, reason=f"game:{subject}", ref=str(score.get("game_id", "")))
        st = self._game_stats.setdefault(account_id, {
            "account_id": account_id, "name": player_name or acct.display_name or acct.email,
            "game_points": 0, "games_played": 0, "best_by_subject": {},
        })
        st["name"] = player_name or st["name"]
        st["game_points"] += pts
        st["games_played"] += 1
        prev = st["best_by_subject"].get(subject, 0)
        st["best_by_subject"][subject] = max(prev, pts)
        return st

    def leaderboard(self, *, subject: Optional[str] = None, limit: int = 20) -> List[dict]:
        """Top players. Global ranks by total game points; subject ranks by best
        single-game score in that subject."""
        rows = list(self._game_stats.values())
        if subject:
            rows = [r for r in rows if subject in r["best_by_subject"]]
            rows.sort(key=lambda r: r["best_by_subject"].get(subject, 0), reverse=True)
            key = lambda r: r["best_by_subject"].get(subject, 0)  # noqa: E731
        else:
            rows.sort(key=lambda r: r["game_points"], reverse=True)
            key = lambda r: r["game_points"]  # noqa: E731
        out = []
        for i, r in enumerate(rows[:limit], start=1):
            out.append({"rank": i, "name": r["name"], "score": key(r),
                        "game_points": r["game_points"], "games_played": r["games_played"]})
        return out

    def my_game_rank(self, account_id: str, *, subject: Optional[str] = None) -> Optional[int]:
        board = self.leaderboard(subject=subject, limit=10_000)
        mine = self._game_stats.get(account_id)
        if not mine:
            return None
        for row in board:
            if row["name"] == mine["name"]:
                return row["rank"]
        return None

    # --- student sub-profiles --------------------------------------------- #
    def add_student(self, account_id: str, display_name: str, *, age_band: str = "adult",
                    interests: Optional[List[str]] = None) -> StudentProfile:
        acct = self._by_id[account_id]
        prof = StudentProfile(display_name=display_name, age_band=age_band,
                              interests=list(interests or []))
        acct.students[prof.id] = prof
        return prof

    def list_students(self, account_id: str) -> List[StudentProfile]:
        return list(self._by_id[account_id].students.values())

    def get_student(self, account_id: str, student_id: str) -> Optional[StudentProfile]:
        return self._by_id[account_id].students.get(student_id)

    def set_mastery(self, account_id: str, student_id: str, skill: str, value: float) -> StudentProfile:
        prof = self._by_id[account_id].students.get(student_id)
        if prof is None:
            raise KeyError(student_id)
        prof.mastery[skill] = max(0.0, min(1.0, float(value)))
        return prof

    def record_completion(self, account_id: str, student_id: str, course_id: str,
                          skills: Optional[List[str]] = None, *, mastery: float = 0.8) -> StudentProfile:
        prof = self._by_id[account_id].students.get(student_id)
        if prof is None:
            raise KeyError(student_id)
        if course_id not in prof.completed_course_ids:
            prof.completed_course_ids.append(course_id)
        for s in (skills or []):
            prof.mastery[s] = max(prof.mastery.get(s, 0.0), mastery)
        return prof
