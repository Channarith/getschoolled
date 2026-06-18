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


@app.post("/enrollments/{course_id}/status")
def update_status(course_id: str, req: StatusUpdate, acct=Depends(current_account)) -> dict:
    try:
        enr = app.state.accounts.set_status(acct.id, course_id, req.status, score=req.score)
    except KeyError:
        raise HTTPException(status_code=404, detail="not enrolled in that course")
    return enr.model_dump()


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
