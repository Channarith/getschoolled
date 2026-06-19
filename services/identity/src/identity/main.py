"""Identity service (Netflix-style accounts + membership + portfolio).

Sign-up / login (HMAC session tokens), the member's subscription tier, and their
course portfolio: saved ("my list"), enrolled, in-progress, passed, failed.
Mastery is fetched from the memory service and payments from billing; this
service is the account + enrollment system of record.
"""

from __future__ import annotations

import os

from aoep_shared.auth import sign_token, verify_token
from aoep_shared.schemas import PlanTier, Region
from aoep_shared.service import create_service
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from .store import AccountStore, Enrollment, EnrollmentStatus

app = create_service("identity")
app.state.accounts = AccountStore()


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


def _session(acct) -> dict:
    token = sign_token({"sub": acct.id, "email": acct.email}, _token_key())
    return {"token": token, "account": acct.public()}


@app.post("/auth/signup")
def signup(req: SignupRequest) -> dict:
    try:
        acct = app.state.accounts.create(
            req.email, req.password, display_name=req.display_name, region=req.region)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _session(acct)


@app.post("/auth/login")
def login(req: LoginRequest) -> dict:
    acct = app.state.accounts.authenticate(req.email, req.password)
    if acct is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    return _session(acct)


@app.get("/auth/me")
def me(acct=Depends(current_account)) -> dict:
    return acct.public()


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@app.post("/auth/password")
def change_password(req: PasswordChange, acct=Depends(current_account)) -> dict:
    if not app.state.accounts.authenticate(acct.email, req.current_password):
        raise HTTPException(status_code=400, detail="current password is incorrect")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="new password must be >= 8 characters")
    app.state.accounts.set_password(acct.id, req.new_password)
    return {"changed": True}


# --------------------------------------------------------------------------- #
# Membership
# --------------------------------------------------------------------------- #
class TierChange(BaseModel):
    tier: PlanTier


@app.post("/membership/tier")
def set_tier(req: TierChange, acct=Depends(current_account)) -> dict:
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


# --------------------------------------------------------------------------- #
# Rewards (points for completion -> discounts / prizes / raffle entries)
# --------------------------------------------------------------------------- #
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
