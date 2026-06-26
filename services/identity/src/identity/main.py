"""Identity service (Netflix-style accounts + membership + portfolio).

Sign-up / login (HMAC session tokens), the member's subscription tier, and their
course portfolio: saved ("my list"), enrolled, in-progress, passed, failed.
Mastery is fetched from the memory service and payments from billing; this
service is the account + enrollment system of record.
"""

from __future__ import annotations

import os
import time

from aoep_shared.auth import sign_token, verify_token
from aoep_shared.flags import require_admin
from aoep_shared.internal_auth import require_internal
from aoep_shared.schemas import PlanTier, Region
from aoep_shared.service import create_service
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .store import AccountStore, BillingAddress, ClassContext, Enrollment, EnrollmentStatus
from .persistence import load_from_redis

app = create_service("identity")
app.state.accounts = AccountStore()
load_from_redis(app.state.accounts)


def _bootstrap_on_startup() -> None:
    import logging

    from .bootstrap import bootstrap_accounts
    from .persistence import load_from_redis_with_retry, save_to_redis_with_retry

    if not load_from_redis_with_retry(app.state.accounts):
        logging.getLogger(__name__).info(
            "identity startup: no Redis snapshot loaded (will bootstrap in-memory)")
    stats = bootstrap_accounts(app.state.accounts)
    if not save_to_redis_with_retry(app.state.accounts):
        logging.getLogger(__name__).error(
            "identity bootstrap: failed to persist seeded accounts to Redis (%s)", stats)


@app.on_event("startup")
def _startup_seed_accounts() -> None:
    _bootstrap_on_startup()
# Arcade: live game rounds (answer keys kept server-side) + submitted guard.
app.state.game_rounds = {}
app.state.game_submitted = set()


def _token_key() -> bytes:
    return os.environ.get("AUTH_SIGNING_KEY", "dev-auth-signing-key").encode()


def current_account(authorization: str = Header(default="")):
    """Resolve the Bearer session token to an Account (401 otherwise)."""
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    claims = verify_token(token, _token_key()) if token else None
    if not claims:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    acct = app.state.accounts.by_id(claims.get("sub", ""))
    if acct is None:
        raise HTTPException(status_code=401, detail="account not found")
    return acct


def require_admin_account(acct=Depends(current_account)):
    """Operator accounts (is_admin) for admin-only read APIs."""
    if not acct.is_admin:
        raise HTTPException(status_code=403, detail="admin access required")
    return acct


def _admin_secret() -> str:
    return os.environ.get("ADMIN_SECRET", "dev-admin-secret")


def require_admin_secret(x_admin_secret: str = Header(default="")) -> str:
    """Operator shared secret (same header memory admin routes use)."""
    if not require_admin(x_admin_secret, _admin_secret()):
        raise HTTPException(status_code=403, detail="admin secret required")
    return x_admin_secret


def _run_reseed_seeded() -> dict:
    from .bootstrap import bootstrap_accounts, env_seed_password
    from .persistence import load_from_redis_with_retry, save_to_redis_with_retry

    load_from_redis_with_retry(app.state.accounts)
    stats = bootstrap_accounts(app.state.accounts)
    persisted = save_to_redis_with_retry(app.state.accounts)
    qa_pw = env_seed_password("QA_ACCOUNTS_PASSWORD", "QaTest123")
    admin_pw = env_seed_password("DEFAULT_ADMIN_PASSWORD", "88888888")
    login_ok = {
        "admin@salareen.com": app.state.accounts.authenticate("admin@salareen.com", admin_pw) is not None,
        "qa-pro@salareen.com": app.state.accounts.authenticate("qa-pro@salareen.com", qa_pw) is not None,
        "qa3": app.state.accounts.authenticate("qa3", qa_pw) is not None,
    }
    return {
        "reseeded": True,
        "stats": stats,
        "persisted": persisted,
        "accounts": len(app.state.accounts._by_id),
        "login_ok": login_ok,
    }


PROFILE_SHARE_SCOPES = {"profile", "interests", "mastery", "completions", "class_context"}


def _normalize_share_scopes(scopes: list[str]) -> list[str]:
    if not scopes:
        return ["profile", "interests", "mastery", "completions", "class_context"]
    cleaned = sorted({s.strip() for s in scopes if s.strip()})
    unknown = [s for s in cleaned if s not in PROFILE_SHARE_SCOPES]
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown profile share scope: {unknown[0]}")
    return cleaned


def current_profile_share(authorization: str = Header(default="")):
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    claims = verify_token(token, _token_key()) if token else None
    if not claims or claims.get("kind") != "profile_share":
        raise HTTPException(status_code=401, detail="invalid or expired profile share token")
    acct = app.state.accounts.by_id(claims.get("sub", ""))
    if acct is None:
        raise HTTPException(status_code=401, detail="profile share account not found")
    grant = app.state.accounts.profile_share_grant(acct.id, claims.get("grant_id", ""))
    if grant is None or grant.revoked or grant.student_id != claims.get("student_id"):
        raise HTTPException(status_code=401, detail="profile share grant is not active")
    if grant.expires_at < time.time():
        raise HTTPException(status_code=401, detail="profile share grant expired")
    return acct, grant


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""
    region: Region = Region.US


class LoginRequest(BaseModel):
    email: str
    password: str


def _client_info(request: Request) -> dict:
    fwd = request.headers.get("X-Forwarded-For", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")
    return {
        "ip": ip,
        "user_agent": request.headers.get("User-Agent", "")[:256],
        "country_hint": request.headers.get("CF-IPCountry", "") or request.headers.get("X-Country", ""),
    }


def _session(acct) -> dict:
    token = sign_token({"sub": acct.id, "email": acct.email}, _token_key())
    return {"token": token, "account": acct.public()}


from .auth_security import register_auth_security_routes

register_auth_security_routes(app, token_key_fn=_token_key, current_account=current_account, session_fn=_session)


@app.post("/auth/signup")
def signup(req: SignupRequest, request: Request) -> dict:
    from aoep_shared.passwords import validate_password

    try:
        validate_password(req.password)
        acct = app.state.accounts.create(
            req.email, req.password, display_name=req.display_name, region=req.region)
        app.state.accounts.ensure_default_student(acct.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    info = _client_info(request)
    app.state.accounts.record_login_event(acct.id, success=True, **info)
    return _session(acct)


@app.post("/auth/login")
def login(req: LoginRequest, request: Request) -> dict:
    info = _client_info(request)
    acct = app.state.accounts.by_email(req.email)
    if acct and acct.locked_until and acct.locked_until > time.time():
        raise HTTPException(status_code=429, detail="account temporarily locked; try again later")
    acct = app.state.accounts.authenticate(req.email, req.password, **info)
    if acct is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    return _session(acct)


@app.get("/auth/login-history")
def login_history(acct=Depends(current_account)) -> dict:
    return {"events": app.state.accounts.login_history(acct.id)}


@app.get("/auth/onboarding-status")
def onboarding_status(acct=Depends(current_account)) -> dict:
    from aoep_shared.membership import tier_requires_payment

    return {
        "completed": acct.onboarding_completed_at is not None,
        "completed_at": acct.onboarding_completed_at,
        "tier": acct.tier.value,
        "membership_class": acct.membership_class,
        "billing_required": tier_requires_payment(acct.tier.value),
        "billing_validated": acct.billing_validated_at is not None,
    }


@app.get("/auth/me")
def me(acct=Depends(current_account)) -> dict:
    return acct.public()


@app.get("/admin/accounts")
def admin_list_accounts(_acct=Depends(require_admin_account)) -> dict:
    """List every member account (operator admin UI)."""
    rows = [a.public() for a in app.state.accounts.list_all_accounts()]
    rows.sort(key=lambda r: r.get("created_at", 0), reverse=True)
    return {"accounts": rows, "count": len(rows)}


@app.post("/admin/accounts/reseed-seeded")
def admin_reseed_seeded(_acct=Depends(require_admin_account)) -> dict:
    """Re-sync default admin + QA personas and persist to Redis (admin session)."""
    return _run_reseed_seeded()


@app.post("/admin/ops/reseed-seeded")
def ops_reseed_seeded(_: str = Depends(require_admin_secret)) -> dict:
    """Operator recovery: reseed admin + QA using X-Admin-Secret (no login JWT)."""
    return _run_reseed_seeded()


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@app.post("/auth/password")
def change_password(req: PasswordChange, acct=Depends(current_account)) -> dict:
    from aoep_shared.passwords import validate_password

    if not app.state.accounts.authenticate(acct.email, req.current_password):
        raise HTTPException(status_code=400, detail="current password is incorrect")
    try:
        validate_password(req.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    app.state.accounts.set_password(acct.id, req.new_password)
    return {"changed": True}


# --------------------------------------------------------------------------- #
# Membership
# --------------------------------------------------------------------------- #
class TierChange(BaseModel):
    tier: PlanTier


@app.get("/membership/subscription")
def get_subscription(acct=Depends(current_account)) -> dict:
    from aoep_shared.plan_pricing import subscription_public

    return subscription_public(
        tier=acct.tier.value,
        subscription_started_at=acct.subscription_started_at,
        billing_anchor_day=acct.billing_anchor_day,
        next_billing_at=acct.next_billing_at,
        billing_amount_usd=acct.billing_amount_usd,
    )


class SubscribeRequest(BaseModel):
    tier: PlanTier


@app.post("/membership/subscribe")
def subscribe(req: SubscribeRequest, acct=Depends(current_account)) -> dict:
    """Activate Standard ($19.99) or VIP ($29.99) with calendar-day billing.

    In local/sandbox mode this completes immediately after checkout; production
    should route through the billing webhook with ``require_internal`` tier sync.
    """
    from aoep_shared.plan_pricing import CONSUMER_TIERS, tier_requires_payment

    tier_val = req.tier.value
    if tier_val not in CONSUMER_TIERS:
        raise HTTPException(status_code=422, detail=f"tier {tier_val!r} is not a consumer plan")
    if tier_requires_payment(tier_val):
        updated = app.state.accounts.activate_subscription(acct.id, req.tier)
    else:
        updated = app.state.accounts.set_tier(acct.id, req.tier)
    return {
        "tier": updated.tier.value,
        "membership_class": updated.membership_class,
        "subscription": updated.public()["subscription"],
    }


@app.post("/membership/tier", dependencies=[Depends(require_internal)])
def set_tier(req: TierChange, acct=Depends(current_account)) -> dict:
    """Update the caller's subscription tier.

    Gated by ``require_internal`` because tier upgrades must be
    driven by the billing service (after a verified payment) or by
    a teacher / admin agent - not by the user themselves. The
    billing webhook handler forwards an internal token here.
    """
    from aoep_shared.plan_pricing import tier_requires_payment

    if tier_requires_payment(req.tier.value):
        updated = app.state.accounts.activate_subscription(acct.id, req.tier)
    else:
        updated = app.state.accounts.set_tier(acct.id, req.tier)
    return {"tier": updated.tier.value}


# --------------------------------------------------------------------------- #
# Portfolio (enrollments + status history)
# --------------------------------------------------------------------------- #
class EnrollRequest(BaseModel):
    course_id: str
    title: str = ""
    status: EnrollmentStatus = EnrollmentStatus.ENROLLED


@app.post("/enrollments")
def enroll(req: EnrollRequest, acct=Depends(current_account)) -> dict:
    enr = app.state.accounts.upsert_enrollment(
        acct.id, Enrollment(course_id=req.course_id, title=req.title, status=req.status))
    return enr.model_dump()


class StatusUpdate(BaseModel):
    status: EnrollmentStatus
    score: float | None = None
    level: str | None = None
    hands_on: bool | None = None


@app.post("/enrollments/{course_id}/status")
def update_status(course_id: str, req: StatusUpdate, acct=Depends(current_account)) -> dict:
    try:
        enr = app.state.accounts.set_status(
            acct.id, course_id, req.status, score=req.score, level=req.level,
            hands_on=req.hands_on)
    except KeyError:
        raise HTTPException(status_code=404, detail="not enrolled in that course")
    return {**enr.model_dump(), "points_balance": app.state.accounts.points_balance(acct.id)}


# --------------------------------------------------------------------------- #
# Student sub-profiles (one account, multiple learners) + Foresight inputs
# --------------------------------------------------------------------------- #
class CreateStudent(BaseModel):
    display_name: str
    age_band: str = "adult"
    interests: list[str] = []


@app.post("/students")
def add_student(req: CreateStudent, acct=Depends(current_account)) -> dict:
    prof = app.state.accounts.add_student(
        acct.id, req.display_name, age_band=req.age_band, interests=req.interests)
    return prof.model_dump()


@app.get("/students")
def list_students(acct=Depends(current_account)) -> dict:
    return {"students": [s.model_dump() for s in app.state.accounts.list_students(acct.id)]}


@app.get("/students/{student_id}")
def get_student(student_id: str, acct=Depends(current_account)) -> dict:
    prof = app.state.accounts.get_student(acct.id, student_id)
    if prof is None:
        raise HTTPException(status_code=404, detail="unknown student profile")
    return prof.model_dump()


class LearningProfileSubmit(BaseModel):
    answers: dict


@app.post("/students/{student_id}/learning-profile")
def submit_learning_profile(student_id: str, req: LearningProfileSubmit,
                              acct=Depends(current_account)) -> dict:
    from aoep_shared.learning_profile import derive_learning_profile, validate_onboarding_answers

    try:
        validate_onboarding_answers(req.answers)
        profile = derive_learning_profile(req.answers)
        prof = app.state.accounts.apply_learning_profile(acct.id, student_id, profile)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown student profile")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "student": prof.model_dump(),
        "learner_category": profile.learner_category,
        "recorded": True,
    }


@app.post("/students/{student_id}/learning-profile/skip")
def skip_learning_profile(student_id: str, acct=Depends(current_account)) -> dict:
    try:
        prof = app.state.accounts.skip_learning_profile(acct.id, student_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown student profile")
    return {"student": prof.model_dump(), "skipped": True}


class MasteryUpdate(BaseModel):
    skill: str
    value: float


@app.post("/students/{student_id}/mastery")
def set_mastery(student_id: str, req: MasteryUpdate, acct=Depends(current_account)) -> dict:
    try:
        prof = app.state.accounts.set_mastery(acct.id, student_id, req.skill, req.value)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown student profile")
    return prof.model_dump()


class CompleteCourse(BaseModel):
    course_id: str
    skills: list[str] = []


@app.post("/students/{student_id}/complete")
def complete_course(student_id: str, req: CompleteCourse, acct=Depends(current_account)) -> dict:
    try:
        prof = app.state.accounts.record_completion(acct.id, student_id, req.course_id, req.skills)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown student profile")
    return prof.model_dump()


class ClassContextRequest(BaseModel):
    course_id: str
    class_id: str = ""
    title: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    source: str = "class"
    external_refs: dict[str, str] = Field(default_factory=dict)


@app.post("/students/{student_id}/class-context")
def record_class_context(student_id: str, req: ClassContextRequest,
                         acct=Depends(current_account)) -> dict:
    try:
        context = app.state.accounts.record_class_context(
            acct.id, student_id, ClassContext(**req.model_dump()))
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown student profile")
    return context.model_dump()


@app.get("/students/{student_id}/profile-context")
def profile_context(student_id: str, acct=Depends(current_account)) -> dict:
    try:
        return app.state.accounts.profile_context(acct.id, student_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown student profile")


class ProfileShareGrantRequest(BaseModel):
    integration: str = ""
    scopes: list[str] = Field(default_factory=list)
    ttl_s: int = 3600


@app.post("/students/{student_id}/profile-share-grants")
def create_profile_share_grant(student_id: str, req: ProfileShareGrantRequest,
                               acct=Depends(current_account)) -> dict:
    scopes = _normalize_share_scopes(req.scopes)
    try:
        grant = app.state.accounts.create_profile_share_grant(
            acct.id, student_id, integration=req.integration, scopes=scopes, ttl_s=req.ttl_s)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown student profile")
    token = sign_token(
        {"kind": "profile_share", "sub": acct.id, "student_id": student_id,
         "grant_id": grant.id, "scopes": scopes, "aud": req.integration},
        _token_key(),
        ttl_s=max(60, min(int(req.ttl_s), 86_400)),
    )
    return {"grant": grant.model_dump(), "token": token}


@app.get("/profile-shares/context")
def shared_profile_context(share=Depends(current_profile_share)) -> dict:
    acct, grant = share
    return app.state.accounts.profile_context(acct.id, grant.student_id, scopes=grant.scopes)


# --------------------------------------------------------------------------- #
# Rewards (points for completion -> discounts / prizes / raffle entries)
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Learning games / arcade: play-to-learn mini-games, points + leaderboard
# --------------------------------------------------------------------------- #
@app.get("/games")
def games_catalog_ep() -> dict:
    from aoep_shared.games import games_catalog

    return games_catalog()


class NewGameRequest(BaseModel):
    subject: str = "science"
    game_type: str = "quiz"
    age_group: str = "teen"
    n: int = 5


@app.post("/games/new")
def games_new(req: NewGameRequest) -> dict:
    from aoep_shared.games import AgeGroup, GameType, make_round

    try:
        gt = GameType(req.game_type)
    except ValueError:
        raise HTTPException(status_code=422, detail="unknown game_type")
    try:
        age = AgeGroup(req.age_group)
    except ValueError:
        raise HTTPException(status_code=422, detail="unknown age_group")
    rnd = make_round(req.subject, gt, age_group=age, n=max(1, min(req.n, 8)))
    app.state.game_rounds[rnd.game_id] = rnd
    from .persistence import save_game_round

    save_game_round(rnd.model_dump_json(), rnd.game_id)
    return rnd.public()


class SubmitGameRequest(BaseModel):
    game_id: str
    answers: dict
    elapsed_s: float | None = None


@app.post("/games/submit")
def games_submit(req: SubmitGameRequest, acct=Depends(current_account)) -> dict:
    from aoep_shared.games import score_round

    rnd = app.state.game_rounds.get(req.game_id)
    if rnd is None:
        from aoep_shared.games import GameRound
        from .persistence import load_game_round

        raw = load_game_round(req.game_id)
        if raw:
            rnd = GameRound.model_validate_json(raw)
            app.state.game_rounds[req.game_id] = rnd
    if rnd is None:
        raise HTTPException(status_code=404, detail="unknown or expired game")
    if req.game_id in app.state.game_submitted:
        raise HTTPException(status_code=409, detail="game already submitted")
    result = score_round(rnd, req.answers, elapsed_s=req.elapsed_s)
    app.state.game_submitted.add(req.game_id)
    app.state.accounts.record_game(
        acct.id, subject=result.subject, game_type=result.game_type.value,
        age_group=rnd.age_group.value,
        score=result.model_dump(), player_name=acct.display_name or acct.email)
    return {
        "result": result.model_dump(),
        "points_earned": result.points,
        "balance": app.state.accounts.points_balance(acct.id),
        "rank": app.state.accounts.my_game_rank(acct.id),
        "subject_rank": app.state.accounts.my_game_rank(acct.id, subject=result.subject),
    }


@app.get("/games/leaderboard")
def games_leaderboard(subject: str | None = None, age_group: str | None = None,
                      limit: int = 20) -> dict:
    return {"subject": subject, "age_group": age_group,
            "leaders": app.state.accounts.leaderboard(
                subject=subject, age_group=age_group, limit=limit)}


class LanguagePracticeRequest(BaseModel):
    language: str
    skill: str = "vocabulary"
    correct: int = 0
    total: int = 0


@app.post("/language/practice")
def language_practice(req: LanguagePracticeRequest, acct=Depends(current_account)) -> dict:
    """Award XP/points for a completed language-practice set (feeds rewards)."""
    from aoep_shared.language_learning import practice_xp

    xp = practice_xp(req.skill, req.correct, req.total)
    if xp > 0:
        acct.points.earn(xp, reason=f"language:{req.language}", ref=req.skill)
    return {"language": req.language, "skill": req.skill, "xp": xp,
            "balance": app.state.accounts.points_balance(acct.id)}


@app.get("/rewards")
def rewards(acct=Depends(current_account)) -> dict:
    return app.state.accounts.rewards_summary(acct.id)


@app.get("/rewards/catalog")
def rewards_catalog() -> dict:
    from aoep_shared.rewards import REWARDS_CATALOG

    return {"prizes": [
        {"id": p.id, "name": p.name, "kind": p.kind.value,
         "cost_points": p.cost_points, "detail": p.detail}
        for p in REWARDS_CATALOG
    ]}


class GrantRequest(BaseModel):
    grant: str   # HMAC-signed reward voucher minted by the AI agent (orchestrator)


@app.post("/rewards/grant")
def rewards_grant(req: GrantRequest, acct=Depends(current_account)) -> dict:
    """Redeem an AI-agent reward voucher to the CURRENT account.

    The voucher is an HMAC-signed token (scope=reward) minted by the teaching
    agent with the shared INTERNAL_TOKEN_KEY; we verify the signature + expiry
    here so the agent authorizes the points while the learner cannot forge or
    replay them. Bounded amount; one-time per voucher nonce.
    """
    import os

    from aoep_shared.auth import verify_token

    key = os.environ.get("INTERNAL_TOKEN_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="reward grants are not configured")
    body = verify_token(req.grant, key.encode("utf-8"))
    if not body or body.get("scope") != "reward":
        raise HTTPException(status_code=403, detail="invalid or expired reward grant")
    try:
        pts = int(body.get("points", 0))
    except (TypeError, ValueError):
        pts = 0
    if pts <= 0 or pts > 200:
        raise HTTPException(status_code=400, detail="invalid grant amount")
    balance, earned = app.state.accounts.award_grant(
        acct.id, pts, reason=str(body.get("reason", "AI teacher reward")),
        ref=str(body.get("ref", "")), nonce=body.get("nonce"))
    return {"earned": earned, "balance": balance, "reason": body.get("reason")}


class RedeemRequest(BaseModel):
    prize_id: str


@app.post("/rewards/redeem")
def rewards_redeem(req: RedeemRequest, acct=Depends(current_account)) -> dict:
    from aoep_shared.rewards import prize_by_id

    prize = prize_by_id(req.prize_id)
    if prize is None:
        raise HTTPException(status_code=404, detail="unknown prize")
    try:
        rec = app.state.accounts.redeem(acct.id, prize)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"redemption": rec, "balance": app.state.accounts.points_balance(acct.id)}


@app.get("/portfolio")
def portfolio(acct=Depends(current_account)) -> dict:
    enrollments = [e.model_dump() for e in app.state.accounts.enrollments(acct.id)]
    by_status: dict[str, list] = {}
    for e in enrollments:
        by_status.setdefault(e["status"], []).append(e)
    return {
        "account": acct.public(),
        "tier": acct.tier.value,
        "enrollments": enrollments,
        "by_status": by_status,
        "counts": {k: len(v) for k, v in by_status.items()},
    }
