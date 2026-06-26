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
from aoep_shared.membership import membership_class_for_tier
from aoep_shared.plan_pricing import (
    anchor_day_from_timestamp,
    initial_next_billing_at,
    price_usd_for_tier,
    tier_requires_payment,
)
from aoep_shared.passkeys import PasskeyCredential
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


class ClassContext(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    course_id: str
    class_id: str = ""
    title: str = ""
    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    source: str = "class"
    external_refs: Dict[str, str] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class ProfileShareGrant(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    student_id: str
    integration: str = ""
    scopes: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())
    expires_at: float = 0.0
    revoked: bool = False


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
    class_contexts: List[ClassContext] = Field(default_factory=list)
    # One-time onboarding learning-behavior survey (modalities, pace, accessibility).
    primary_style: str = "mixed"
    learning_pace: str = "moderate"
    learning_structure: str = "step_by_step"
    session_length: str = "medium"
    group_preference: str = "either"
    reading_level: str = "intermediate"
    motivation: str = "personal"
    accessibility: Dict[str, bool] = Field(default_factory=dict)
    accommodations_notes: str = ""
    learner_category: str = ""
    onboarding_completed_at: Optional[float] = None
    # Raw survey answers for re-opening / editing the learning profile from Settings.
    onboarding_answers: Dict[str, object] = Field(default_factory=dict)
    # Evolving adaptation (pace, goals, triggers, failed teaching approaches).
    learning_goals: List[str] = Field(default_factory=list)
    goal_timeline: str = ""
    adaptation: Dict[str, object] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())


class BillingAddress(BaseModel):
    line1: str = ""
    line2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = "US"
    phone: str = ""


class LoginEvent(BaseModel):
    ts: float = Field(default_factory=lambda: time.time())
    success: bool = True
    ip: str = ""
    user_agent: str = ""
    country_hint: str = ""
    method: str = "password"   # password | google | facebook | passkey | mfa


class Account(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    email: str
    display_name: str = ""
    password_hash: str = ""
    tier: PlanTier = PlanTier.FREE
    region: Region = Region.US
    membership_class: str = "standard"   # standard | vip (derived from tier)
    is_admin: bool = False
    created_at: float = Field(default_factory=lambda: time.time())
    # Subscription billing (Netflix-style calendar-day monthly).
    subscription_started_at: Optional[float] = None
    billing_anchor_day: Optional[int] = None   # 1–31, day of month they signed up
    next_billing_at: Optional[float] = None  # unix ts of next charge
    billing_amount_usd: Optional[float] = None
    # Security signals.
    last_login_at: Optional[float] = None
    failed_logins: int = 0
    login_count: int = 0
    locked_until: Optional[float] = None
    login_events: List[LoginEvent] = Field(default_factory=list)
    totp_secret: str = ""
    totp_enabled: bool = False
    oauth_subject: str = ""          # provider:sub when passwordless OAuth linked
    passkeys: List[PasskeyCredential] = Field(default_factory=list)
    onboarding_completed_at: Optional[float] = None
    billing_address: Optional[BillingAddress] = None
    card_last4: str = ""
    billing_validated_at: Optional[float] = None
    enrollments: Dict[str, Enrollment] = Field(default_factory=dict)
    # Learner sub-profiles (one account, multiple students).
    students: Dict[str, StudentProfile] = Field(default_factory=dict)
    profile_share_grants: Dict[str, ProfileShareGrant] = Field(default_factory=dict)
    # Rewards: points ledger + redemptions (pydantic-excluded; managed in-store).
    points: PointsLedger = Field(default_factory=PointsLedger, exclude=True)
    redemptions: List[dict] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def public(self) -> dict:
        from aoep_shared.plan_pricing import subscription_public

        return {
            "id": self.id, "email": self.email, "display_name": self.display_name,
            "tier": self.tier.value, "region": self.region.value,
            "membership_class": self.membership_class,
            "is_admin": self.is_admin,
            "created_at": self.created_at, "last_login_at": self.last_login_at,
            "login_count": self.login_count,
            "totp_enabled": self.totp_enabled,
            "has_passkeys": bool(self.passkeys),
            "oauth_linked": bool(self.oauth_subject),
            "subscription": subscription_public(
                tier=self.tier.value,
                subscription_started_at=self.subscription_started_at,
                billing_anchor_day=self.billing_anchor_day,
                next_billing_at=self.next_billing_at,
                billing_amount_usd=self.billing_amount_usd,
            ),
        }


class AccountStore:
    def __init__(self) -> None:
        self._by_id: Dict[str, Account] = {}
        self._id_by_email: Dict[str, str] = {}
        # Arcade leaderboard: account_id -> aggregate game stats.
        self._game_stats: Dict[str, dict] = {}
        # One-time nonces of redeemed AI-agent reward vouchers (replay guard).
        self._used_grant_nonces: set = set()
        self._passkey_challenges: Dict[str, str] = {}

    def _persist(self) -> None:
        from .persistence import persist_hook

        persist_hook(self)

    def list_all_accounts(self) -> List[Account]:
        """All accounts (operator/admin tooling)."""
        return list(self._by_id.values())

    def create(self, email: str, password: str, *, display_name: str = "",
               tier: PlanTier = PlanTier.FREE, region: Region = Region.US) -> Account:
        email = email.strip().lower()
        if not email or "@" not in email:
            raise ValueError("a valid email is required")
        if email in self._id_by_email:
            raise ValueError("an account with that email already exists")
        acct = Account(
            email=email,
            display_name=display_name or email.split("@")[0],
            password_hash=hash_password(password),
            tier=tier,
            region=region,
            membership_class=membership_class_for_tier(tier.value),
        )
        self._by_id[acct.id] = acct
        self._id_by_email[email] = acct.id
        self._persist()
        return acct

    def seed_account(
        self,
        email: str,
        password: str,
        *,
        display_name: str = "",
        tier: PlanTier = PlanTier.FREE,
        region: Region = Region.US,
        username: str = "",
        is_admin: bool = False,
        force_password: bool = False,
    ) -> Account:
        """Create (idempotently) a seeded account. Optionally registers a bare
        username alias for login. When ``force_password`` is True (QA personas),
        always re-hash the password so known test credentials keep working after
        Redis reloads or a prior manual signup with a different password."""
        email = email.strip().lower()
        alias = username.strip().lower()
        existing = self.by_email(email)
        if existing is None and alias:
            existing = self._by_id.get(self._id_by_email.get(alias, ""))
        if existing is not None:
            existing.tier = tier
            existing.membership_class = membership_class_for_tier(tier.value)
            existing.is_admin = existing.is_admin or is_admin
            if display_name:
                existing.display_name = display_name
            if force_password:
                existing.password_hash = hash_password(password)
            if alias and alias not in self._id_by_email:
                self._id_by_email[alias] = existing.id
            self._persist()
            return existing
        acct = Account(
            email=email,
            display_name=display_name or email.split("@")[0],
            password_hash=hash_password(password),
            tier=tier,
            region=region,
            is_admin=is_admin,
            membership_class=membership_class_for_tier(tier.value),
        )
        self._by_id[acct.id] = acct
        self._id_by_email[email] = acct.id
        if alias and alias not in self._id_by_email:
            self._id_by_email[alias] = acct.id
        self._persist()
        return acct

    def seed_admin(self, email: str, password: str, *, username: str = "admin",
                   display_name: str = "Administrator",
                   force_password: bool = True) -> Account:
        """Create (idempotently) a default admin account. Also registers a bare
        `username` alias so you can log in with just "admin". Marked is_admin so
        the web unlocks operator surfaces (e.g. the Homework grader).

        ``force_password`` re-syncs the hash on every startup (same as QA
        personas) so DEFAULT_ADMIN_* credentials keep working after Redis reloads
        or an accidental manual signup on the admin email."""
        return self.seed_account(
            email,
            password,
            display_name=display_name,
            username=username,
            is_admin=True,
            force_password=force_password,
        )

    def by_email(self, email: str) -> Optional[Account]:
        aid = self._id_by_email.get(email.strip().lower())
        return self._by_id.get(aid) if aid else None

    def by_id(self, account_id: str) -> Optional[Account]:
        return self._by_id.get(account_id)

    def authenticate(
        self,
        email: str,
        password: str,
        *,
        ip: str = "",
        user_agent: str = "",
        country_hint: str = "",
    ) -> Optional[Account]:
        acct = self.by_email(email)
        if acct is None:
            return None
        if acct.locked_until and acct.locked_until > time.time():
            self.record_login_event(
                acct.id, success=False, ip=ip, user_agent=user_agent,
                country_hint=country_hint, method="password", reason="locked",
            )
            return None
        if not verify_password(password, acct.password_hash):
            acct.failed_logins += 1
            if acct.failed_logins >= 5:
                acct.locked_until = time.time() + 900  # 15 min lockout
            self.record_login_event(
                acct.id, success=False, ip=ip, user_agent=user_agent,
                country_hint=country_hint, method="password", reason="bad_password",
            )
            self._persist()
            return None
        acct.failed_logins = 0
        acct.locked_until = None
        acct.last_login_at = time.time()
        acct.login_count += 1
        self.record_login_event(
            acct.id, success=True, ip=ip, user_agent=user_agent,
            country_hint=country_hint, method="password",
        )
        self._persist()
        return acct

    def record_login_event(
        self,
        account_id: str,
        *,
        success: bool,
        ip: str = "",
        user_agent: str = "",
        country_hint: str = "",
        method: str = "password",
        reason: str = "",
    ) -> None:
        acct = self._by_id.get(account_id)
        if acct is None:
            return
        acct.login_events.append(LoginEvent(
            success=success,
            ip=(ip or "")[:64],
            user_agent=(user_agent or "")[:256],
            country_hint=(country_hint or reason or "")[:32],
            method=method[:24],
        ))
        if len(acct.login_events) > 50:
            acct.login_events = acct.login_events[-50:]
        self._persist()

    def login_history(self, account_id: str, limit: int = 20) -> List[dict]:
        acct = self._by_id.get(account_id)
        if acct is None:
            return []
        return [e.model_dump() for e in reversed(acct.login_events)][:limit]

    def find_by_oauth_subject(self, subject: str) -> Optional[Account]:
        sub = (subject or "").strip()
        if not sub:
            return None
        for acct in self._by_id.values():
            if acct.oauth_subject == sub:
                return acct
        return None

    def link_oauth(
        self,
        account_id: str,
        *,
        subject: str,
        display_name: str = "",
    ) -> Account:
        acct = self._by_id[account_id]
        acct.oauth_subject = subject
        if display_name and not acct.display_name:
            acct.display_name = display_name
        self._persist()
        return acct

    def oauth_login_success(
        self,
        account_id: str,
        *,
        ip: str = "",
        user_agent: str = "",
        country_hint: str = "",
        method: str = "google",
    ) -> Account:
        acct = self._by_id[account_id]
        acct.failed_logins = 0
        acct.locked_until = None
        acct.last_login_at = time.time()
        acct.login_count += 1
        self.record_login_event(
            account_id, success=True, ip=ip, user_agent=user_agent,
            country_hint=country_hint, method=method,
        )
        return acct

    def get_or_create_oauth_account(
        self,
        *,
        email: str,
        subject: str,
        display_name: str = "",
    ) -> Account:
        existing = self.find_by_oauth_subject(subject)
        if existing:
            return existing
        by_email = self.by_email(email)
        if by_email:
            return self.link_oauth(by_email.id, subject=subject, display_name=display_name)
        acct = Account(
            email=email.strip().lower(),
            display_name=display_name or email.split("@")[0],
            password_hash=hash_password(uuid.uuid4().hex),
            oauth_subject=subject,
            membership_class=membership_class_for_tier(PlanTier.FREE.value),
        )
        self._by_id[acct.id] = acct
        self._id_by_email[acct.email] = acct.id
        self.ensure_default_student(acct.id)
        self._persist()
        return acct

    def set_totp_secret(self, account_id: str, secret: str) -> None:
        acct = self._by_id[account_id]
        acct.totp_secret = secret
        acct.totp_enabled = False
        self._persist()

    def enable_totp(self, account_id: str) -> None:
        acct = self._by_id[account_id]
        acct.totp_enabled = True
        self._persist()

    def disable_totp(self, account_id: str) -> None:
        acct = self._by_id[account_id]
        acct.totp_secret = ""
        acct.totp_enabled = False
        self._persist()

    def add_passkey(self, account_id: str, cred: PasskeyCredential) -> None:
        acct = self._by_id[account_id]
        acct.passkeys = [c for c in acct.passkeys if c.credential_id != cred.credential_id]
        acct.passkeys.append(cred)
        self._persist()

    def passkey_by_id(self, account_id: str, credential_id: str) -> Optional[PasskeyCredential]:
        acct = self._by_id.get(account_id)
        if acct is None:
            return None
        for c in acct.passkeys:
            if c.credential_id == credential_id:
                return c
        return None

    def store_passkey_challenge(self, account_id: str, challenge: str) -> None:
        self._passkey_challenges[account_id] = challenge

    def pop_passkey_challenge(self, account_id: str) -> str:
        return self._passkey_challenges.pop(account_id, "")

    def find_account_by_passkey(self, credential_id: str) -> Optional[Account]:
        for acct in self._by_id.values():
            if any(c.credential_id == credential_id for c in acct.passkeys):
                return acct
        return None

    def set_password(self, account_id: str, new_password: str) -> None:
        acct = self._by_id[account_id]
        acct.password_hash = hash_password(new_password)
        self._persist()

    def set_billing_profile(
        self,
        account_id: str,
        address: BillingAddress,
        *,
        card_last4: str = "",
    ) -> Account:
        acct = self._by_id[account_id]
        acct.billing_address = address
        if card_last4:
            acct.card_last4 = card_last4
        acct.billing_validated_at = time.time()
        self._persist()
        return acct

    def complete_onboarding(self, account_id: str) -> Account:
        acct = self._by_id[account_id]
        acct.onboarding_completed_at = time.time()
        self._persist()
        return acct

    def patch_account(self, account_id: str, **fields) -> Account:
        acct = self._by_id[account_id]
        for key, val in fields.items():
            if val is not None and hasattr(acct, key):
                setattr(acct, key, val)
        self._persist()
        return acct

    def set_tier(self, account_id: str, tier: PlanTier) -> Account:
        acct = self._by_id[account_id]
        acct.tier = tier
        acct.membership_class = membership_class_for_tier(tier.value)
        if not tier_requires_payment(tier.value):
            acct.subscription_started_at = None
            acct.billing_anchor_day = None
            acct.next_billing_at = None
            acct.billing_amount_usd = None
        self._persist()
        return acct

    def activate_subscription(
        self,
        account_id: str,
        tier: PlanTier,
        *,
        started_at: Optional[float] = None,
    ) -> Account:
        """Start or change a paid plan with calendar-day monthly billing."""
        if not tier_requires_payment(tier.value):
            return self.set_tier(account_id, tier)
        acct = self._by_id[account_id]
        now = started_at if started_at is not None else time.time()
        anchor = anchor_day_from_timestamp(now)
        acct.tier = tier
        acct.membership_class = membership_class_for_tier(tier.value)
        acct.subscription_started_at = now
        acct.billing_anchor_day = anchor
        acct.billing_amount_usd = price_usd_for_tier(tier.value)
        acct.next_billing_at = initial_next_billing_at(now, anchor_day=anchor)
        self._persist()
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
            self._persist()
            return existing
        acct.enrollments[enrollment.course_id] = enrollment
        self._persist()
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
        self._persist()
        return enr

    # --- rewards ----------------------------------------------------------- #
    def points_balance(self, account_id: str) -> int:
        return self._by_id[account_id].points.balance

    def award_grant(self, account_id: str, points: int, *, reason: str,
                    ref: str = "", nonce: Optional[str] = None) -> tuple[int, int]:
        """Credit an AI-agent reward voucher to an account. Returns
        (new_balance, points_earned). Idempotent on the voucher nonce so a
        re-submitted voucher does not double-credit."""
        acct = self._by_id[account_id]
        if nonce and nonce in self._used_grant_nonces:
            return acct.points.balance, 0
        if nonce:
            self._used_grant_nonces.add(nonce)
        acct.points.earn(points, reason=reason, ref=ref)
        self._persist()
        return acct.points.balance, points

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
        self._persist()
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
                    score: dict, player_name: str = "", age_group: str = "teen") -> dict:
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
            "points_by_age": {},
        })
        st["name"] = player_name or st["name"]
        st["game_points"] += pts
        st["games_played"] += 1
        prev = st["best_by_subject"].get(subject, 0)
        st["best_by_subject"][subject] = max(prev, pts)
        st["points_by_age"][age_group] = st["points_by_age"].get(age_group, 0) + pts
        st["last_age_group"] = age_group
        self._persist()
        return st

    def leaderboard(self, *, subject: Optional[str] = None, age_group: Optional[str] = None,
                    limit: int = 20) -> List[dict]:
        """Top players. Global ranks by total game points; subject ranks by best
        single-game score in that subject; age_group ranks by points earned in
        that age tier (so kids compete with kids, adults with adults)."""
        rows = list(self._game_stats.values())
        if subject:
            rows = [r for r in rows if subject in r["best_by_subject"]]
            key = lambda r: r["best_by_subject"].get(subject, 0)  # noqa: E731
        elif age_group:
            rows = [r for r in rows if age_group in r.get("points_by_age", {})]
            key = lambda r: r.get("points_by_age", {}).get(age_group, 0)  # noqa: E731
        else:
            key = lambda r: r["game_points"]  # noqa: E731
        rows.sort(key=key, reverse=True)
        out = []
        for i, r in enumerate(rows[:limit], start=1):
            out.append({"rank": i, "name": r["name"], "score": key(r),
                        "game_points": r["game_points"], "games_played": r["games_played"]})
        return out

    def my_game_rank(self, account_id: str, *, subject: Optional[str] = None,
                     age_group: Optional[str] = None) -> Optional[int]:
        board = self.leaderboard(subject=subject, age_group=age_group, limit=10_000)
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
        self._persist()
        return prof

    def apply_learning_profile(self, account_id: str, student_id: str, profile) -> StudentProfile:
        """Persist onboarding survey results on a student profile."""
        prof = self._by_id[account_id].students.get(student_id)
        if prof is None:
            raise KeyError(student_id)
        prof.primary_style = profile.primary_style
        prof.learning_pace = profile.pace
        prof.learning_structure = profile.structure
        prof.session_length = profile.session_length
        prof.group_preference = profile.group_preference
        prof.reading_level = profile.reading_level
        prof.motivation = profile.motivation
        prof.accessibility = dict(profile.accessibility)
        prof.accommodations_notes = profile.accommodations_notes
        prof.learner_category = profile.learner_category
        prof.onboarding_completed_at = profile.completed_at
        prof.onboarding_answers = dict(profile.raw_answers)
        self._persist()
        return prof

    def record_adaptation_event(
        self,
        account_id: str,
        student_id: str,
        event_type: str,
        payload: dict,
    ) -> StudentProfile:
        from aoep_shared.learner_adaptation import adaptation_from_dict

        prof = self._by_id[account_id].students.get(student_id)
        if prof is None:
            raise KeyError(student_id)
        raw = dict(prof.adaptation or {})
        adapt = adaptation_from_dict(
            raw,
            learning_goals=list(prof.learning_goals or []),
            goal_timeline=str(prof.goal_timeline or ""),
        )
        et = (event_type or "").strip().lower()
        if et == "completion_pace":
            adapt.record_completion(float(payload.get("minutes", 20)))
        elif et in ("course_completion", "course_finish"):
            adapt.record_course_finish(
                str(payload.get("course_id", "")),
                float(payload.get("minutes", 20)),
                expected_min=float(payload.get("expected_min", 25)),
                complexity=int(payload.get("complexity", 3)),
            )
        elif et in ("wellness", "mood"):
            adapt.record_wellness(
                str(payload.get("state", "ok")),
                str(payload.get("reason", "")),
            )
        elif et in ("lx_tick", "lx_session_end"):
            adapt.record_lx_sample(
                float(payload.get("score", 0)),
                strategy=str(payload.get("strategy", "")),
                success=payload.get("success") if "success" in payload else None,
            )
        elif et == "pulse_survey":
            from aoep_shared.pulse_survey import interpret_pulse

            hints = interpret_pulse(
                going_well=int(payload.get("going_well", 3)),
                pace=str(payload.get("pace", "just right")),
                working_best=payload.get("working_best"),
                teaching_strategy=str(payload.get("teaching_strategy", "")),
            )
            adapt.record_lx_sample(
                hints["lx_score"],
                strategy=str(payload.get("teaching_strategy", "") or hints.get("preferred_strategy", "")),
                success=hints["strategy_success"] or hints["lx_score"] >= 70,
            )
            if hints["strategy_failure"] and hints.get("preferred_strategy"):
                adapt.record_failed_approach(
                    str(payload.get("teaching_strategy", "default")),
                    str(payload.get("course_id", "")),
                    f"pulse: learner prefers {hints['preferred_strategy']}",
                )
            elif hints["strategy_success"]:
                adapt.record_strategy(str(payload.get("teaching_strategy", "default")), success=True)
            elif hints.get("preferred_strategy") and hints["lx_score"] >= 70:
                adapt.record_strategy(hints["preferred_strategy"], success=True)
            for tr in hints.get("triggers", []):
                adapt.record_trigger(
                    tr["trigger"], tr["reason"], severity="medium", allow_retry=True,
                )
        elif et == "strategy_success":
            adapt.record_strategy(str(payload.get("strategy", "default")), success=True)
        elif et == "strategy_failure":
            adapt.record_failed_approach(
                str(payload.get("strategy", "default")),
                str(payload.get("topic", "")),
                str(payload.get("reason", "")),
            )
        elif et == "trigger":
            adapt.record_trigger(
                str(payload.get("trigger", "")),
                str(payload.get("reason", "")),
                severity=str(payload.get("severity", "medium")),
                allow_retry=bool(payload.get("allow_retry", False)),
            )
        elif et == "goals":
            goals = payload.get("goals")
            if isinstance(goals, list):
                prof.learning_goals = [str(g) for g in goals]
            if payload.get("timeline"):
                prof.goal_timeline = str(payload["timeline"])
            adapt.profile_revision += 1
        prof.adaptation = adapt.to_dict()
        self._persist()
        return prof

    def skip_learning_profile(self, account_id: str, student_id: str) -> StudentProfile:
        """Record that the user dismissed the one-time survey (persisted, not local-only)."""
        prof = self._by_id[account_id].students.get(student_id)
        if prof is None:
            raise KeyError(student_id)
        if prof.onboarding_completed_at is None:
            prof.onboarding_completed_at = time.time()
        if not prof.learner_category:
            prof.learner_category = "skipped"
        self._persist()
        return prof

    def ensure_default_student(self, account_id: str) -> StudentProfile:
        """Create a primary student profile if the account has none (post-signup)."""
        acct = self._by_id[account_id]
        if acct.students:
            return next(iter(acct.students.values()))
        name = acct.display_name or acct.email.split("@")[0]
        return self.add_student(account_id, name, age_band="adult")

    def list_students(self, account_id: str) -> List[StudentProfile]:
        return list(self._by_id[account_id].students.values())

    def get_student(self, account_id: str, student_id: str) -> Optional[StudentProfile]:
        return self._by_id[account_id].students.get(student_id)

    def set_mastery(
        self, account_id: str, student_id: str, skill: str, value: float
    ) -> StudentProfile:
        prof = self._by_id[account_id].students.get(student_id)
        if prof is None:
            raise KeyError(student_id)
        prof.mastery[skill] = max(0.0, min(1.0, float(value)))
        self._persist()
        return prof

    def record_completion(
        self, account_id: str, student_id: str, course_id: str,
        skills: Optional[List[str]] = None, *, mastery: float = 0.8,
        minutes: Optional[float] = None,
        expected_min: Optional[float] = None,
        complexity: Optional[int] = None,
    ) -> StudentProfile:
        prof = self._by_id[account_id].students.get(student_id)
        if prof is None:
            raise KeyError(student_id)
        if course_id not in prof.completed_course_ids:
            prof.completed_course_ids.append(course_id)
        for s in (skills or []):
            prof.mastery[s] = max(prof.mastery.get(s, 0.0), mastery)
        if minutes is not None and minutes > 0:
            self.record_adaptation_event(
                account_id, student_id, "course_completion", {
                    "course_id": course_id,
                    "minutes": minutes,
                    "expected_min": expected_min or 25,
                    "complexity": complexity or 3,
                },
            )
            prof = self._by_id[account_id].students[student_id]
        else:
            self._persist()
        return prof

    def record_class_context(self, account_id: str, student_id: str,
                             context: ClassContext) -> ClassContext:
        prof = self._by_id[account_id].students.get(student_id)
        if prof is None:
            raise KeyError(student_id)
        context.skills = sorted({s.strip() for s in context.skills if s.strip()})
        now = time.time()
        context.updated_at = now
        for idx, existing in enumerate(prof.class_contexts):
            same_class = context.class_id and existing.class_id == context.class_id
            same_course = not context.class_id and existing.course_id == context.course_id
            if same_class or same_course:
                context.id = existing.id
                context.created_at = existing.created_at
                prof.class_contexts[idx] = context
                self._persist()
                return context
        prof.class_contexts.append(context)
        self._persist()
        return context

    def create_profile_share_grant(self, account_id: str, student_id: str, *,
                                   integration: str = "", scopes: Optional[List[str]] = None,
                                   ttl_s: int = 3600) -> ProfileShareGrant:
        if student_id not in self._by_id[account_id].students:
            raise KeyError(student_id)
        grant = ProfileShareGrant(
            student_id=student_id,
            integration=integration,
            scopes=list(scopes or []),
            expires_at=time.time() + max(60, min(int(ttl_s), 86_400)),
        )
        self._by_id[account_id].profile_share_grants[grant.id] = grant
        self._persist()
        return grant

    def profile_share_grant(self, account_id: str, grant_id: str) -> Optional[ProfileShareGrant]:
        return self._by_id[account_id].profile_share_grants.get(grant_id)

    def profile_context(self, account_id: str, student_id: str, *,
                        scopes: Optional[List[str]] = None) -> dict:
        acct = self._by_id[account_id]
        prof = acct.students.get(student_id)
        if prof is None:
            raise KeyError(student_id)
        wanted = set(scopes or [
            "profile", "interests", "mastery", "completions", "class_context",
            "learning_profile", "adaptation", "pace",
        ])
        student = {"id": prof.id, "display_name": prof.display_name, "age_band": prof.age_band}
        if "interests" in wanted or "profile" in wanted:
            student["interests"] = list(prof.interests)
        if "learning_profile" in wanted or "profile" in wanted:
            from aoep_shared.content_access import needs_simplified_content

            student["learning_profile"] = {
                "primary_style": prof.primary_style,
                "learning_pace": prof.learning_pace,
                "reading_level": prof.reading_level,
                "accessibility": dict(prof.accessibility),
                "accommodations_notes": prof.accommodations_notes,
                "learner_category": prof.learner_category,
                "needs_simplified_content": needs_simplified_content(
                    age_band=prof.age_band,
                    reading_level=prof.reading_level,
                    accessibility=prof.accessibility,
                    accommodations_notes=prof.accommodations_notes,
                    learner_category=prof.learner_category,
                ),
            }
        out = {
            "schema_version": "aoep.profile_context.v2",
            "account_id": acct.id,
            "student": student,
            "exported_at": time.time(),
            "scopes": sorted(wanted),
        }
        if "mastery" in wanted:
            out["mastery"] = dict(prof.mastery)
        if "completions" in wanted:
            out["completed_course_ids"] = list(prof.completed_course_ids)
        if "class_context" in wanted:
            out["class_contexts"] = [c.model_dump() for c in prof.class_contexts]
        if "adaptation" in wanted or "pace" in wanted:
            out["adaptation"] = dict(prof.adaptation or {})
        if "pace" in wanted:
            raw = prof.adaptation or {}
            finishes = raw.get("course_finishes") or []
            out["course_pace"] = {
                "observed_pace": raw.get("observed_pace", "moderate"),
                "avg_minutes_per_lesson": raw.get("avg_minutes_per_lesson"),
                "recent_finishes": finishes[-5:],
                "wellness_state": raw.get("wellness_state", "ok"),
            }
        return out
