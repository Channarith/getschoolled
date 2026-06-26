"""Extended auth routes: forgot password, 2FA, OAuth, passkeys, login audit."""

from __future__ import annotations

import os

from aoep_shared.auth import sign_token, verify_token
from aoep_shared.login_audit import login_context_from_headers
from aoep_shared.oauth_login import OAuthError, verify_facebook_access_token, verify_google_id_token
from aoep_shared.passkeys import (
    credentials_public,
    new_login_challenge,
    new_registration_challenge,
    verify_login,
    verify_registration,
)
from aoep_shared.password_reset import issue_reset_token, verify_reset_token
from aoep_shared.totp import generate_totp_secret, otpauth_uri, verify_totp
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class TotpCodeRequest(BaseModel):
    code: str


class OAuthGoogleRequest(BaseModel):
    id_token: str


class OAuthFacebookRequest(BaseModel):
    access_token: str


class PasskeyRegisterVerify(BaseModel):
    challenge: str
    credential_id: str
    client_data_json: str
    public_key: str = ""
    label: str = "Passkey"


class PasskeyLoginOptions(BaseModel):
    email: str = ""


class PasskeyLoginVerify(BaseModel):
    account_id: str
    challenge: str
    credential_id: str
    client_data_json: str


def register_auth_security_routes(app, *, token_key_fn, current_account, session_fn):
    """Mount secure-auth endpoints on the identity FastAPI app."""

    def _ctx(request: Request) -> dict:
        c = login_context_from_headers(
            x_forwarded_for=request.headers.get("x-forwarded-for", ""),
            x_real_ip=request.headers.get("x-real-ip", ""),
            cf_ipcountry=request.headers.get("cf-ipcountry", ""),
            user_agent=request.headers.get("user-agent", ""),
            client_ip=request.client.host if request.client else "",
        )
        return {"ip": c.ip, "user_agent": c.user_agent, "country_hint": c.country_hint}

    @app.post("/auth/login")
    def login(req: LoginRequest, request: Request) -> dict:
        ctx = _ctx(request)
        acct = app.state.accounts.authenticate(
            req.email, req.password, **ctx,
        )
        if acct is None:
            raise HTTPException(status_code=401, detail="invalid email or password")
        if acct.totp_enabled and acct.totp_secret:
            mfa = sign_token(
                {"sub": acct.id, "purpose": "mfa_pending"},
                token_key_fn(),
                ttl_s=300,
            )
            return {"requires_2fa": True, "mfa_token": mfa}
        return session_fn(acct)

    @app.post("/auth/2fa/verify")
    def verify_2fa_login(req: MfaVerifyRequest, request: Request) -> dict:
        body = verify_token(req.mfa_token, token_key_fn())
        if not body or body.get("purpose") != "mfa_pending":
            raise HTTPException(status_code=401, detail="invalid or expired MFA session")
        acct = app.state.accounts.by_id(body.get("sub", ""))
        if acct is None or not acct.totp_enabled:
            raise HTTPException(status_code=401, detail="2FA not enabled")
        if not verify_totp(acct.totp_secret, req.code):
            ctx = _ctx(request)
            app.state.accounts.record_login_event(
                acct.id, success=False, method="mfa", **ctx, reason="bad_code",
            )
            raise HTTPException(status_code=401, detail="invalid 2FA code")
        ctx = _ctx(request)
        app.state.accounts.oauth_login_success(acct.id, method="mfa", **ctx)
        return session_fn(acct)

    @app.post("/auth/forgot-password")
    def forgot_password(req: ForgotPasswordRequest) -> dict:
        acct = app.state.accounts.by_email(req.email)
        out = {"sent": True}
        if acct is None:
            return out
        token = issue_reset_token(acct.id, acct.email, token_key_fn())
        if os.environ.get("DEPLOY_MODE", "local").lower() == "local":
            out["reset_token"] = token
        return out

    @app.post("/auth/reset-password")
    def reset_password(req: ResetPasswordRequest) -> dict:
        from aoep_shared.passwords import validate_password

        body = verify_reset_token(req.token, token_key_fn())
        if not body:
            raise HTTPException(status_code=400, detail="invalid or expired reset link")
        try:
            validate_password(req.new_password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        app.state.accounts.set_password(body["sub"], req.new_password)
        acct = app.state.accounts.by_id(body["sub"])
        if acct:
            acct.failed_logins = 0
            acct.locked_until = None
        return {"reset": True}

    @app.post("/auth/2fa/setup")
    def setup_2fa(acct=Depends(current_account)) -> dict:
        secret = generate_totp_secret()
        app.state.accounts.set_totp_secret(acct.id, secret)
        return {
            "secret": secret,
            "otpauth_uri": otpauth_uri(secret=secret, email=acct.email),
        }

    @app.post("/auth/2fa/confirm")
    def confirm_2fa(req: TotpCodeRequest, acct=Depends(current_account)) -> dict:
        if not acct.totp_secret or not verify_totp(acct.totp_secret, req.code):
            raise HTTPException(status_code=400, detail="invalid 2FA code")
        app.state.accounts.enable_totp(acct.id)
        return {"enabled": True}

    @app.post("/auth/2fa/disable")
    def disable_2fa(req: TotpCodeRequest, acct=Depends(current_account)) -> dict:
        if not acct.totp_enabled or not verify_totp(acct.totp_secret, req.code):
            raise HTTPException(status_code=400, detail="invalid 2FA code")
        app.state.accounts.disable_totp(acct.id)
        return {"enabled": False}

    @app.post("/auth/oauth/google")
    def oauth_google(req: OAuthGoogleRequest, request: Request) -> dict:
        ctx = _ctx(request)
        try:
            ident = verify_google_id_token(req.id_token)
        except OAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        acct = app.state.accounts.get_or_create_oauth_account(
            email=ident["email"], subject=ident["sub"], display_name=ident.get("name", ""),
        )
        app.state.accounts.oauth_login_success(acct.id, method="google", **ctx)
        return session_fn(acct)

    @app.post("/auth/oauth/facebook")
    def oauth_facebook(req: OAuthFacebookRequest, request: Request) -> dict:
        ctx = _ctx(request)
        try:
            ident = verify_facebook_access_token(req.access_token)
        except OAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        acct = app.state.accounts.get_or_create_oauth_account(
            email=ident["email"], subject=ident["sub"], display_name=ident.get("name", ""),
        )
        app.state.accounts.oauth_login_success(acct.id, method="facebook", **ctx)
        return session_fn(acct)

    @app.post("/auth/passkey/register/options")
    def passkey_register_options(acct=Depends(current_account)) -> dict:
        opts = new_registration_challenge(acct.id)
        app.state.accounts.store_passkey_challenge(acct.id, opts["challenge"])
        return opts

    @app.post("/auth/passkey/register/verify")
    def passkey_register_verify(req: PasskeyRegisterVerify, acct=Depends(current_account)) -> dict:
        expected = app.state.accounts.pop_passkey_challenge(acct.id)
        if not expected or expected != req.challenge:
            raise HTTPException(status_code=400, detail="passkey challenge mismatch")
        try:
            cred = verify_registration(
                challenge=req.challenge,
                client_data_json=req.client_data_json,
                credential_id=req.credential_id,
                public_key=req.public_key,
            )
            cred.label = req.label or cred.label
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        app.state.accounts.add_passkey(acct.id, cred)
        return {"registered": True, "credential_id": cred.credential_id}

    @app.post("/auth/passkey/login/options")
    def passkey_login_options(req: PasskeyLoginOptions) -> dict:
        acct = app.state.accounts.by_email(req.email) if req.email else None
        allow = [c.credential_id for c in (acct.passkeys if acct else [])]
        if not allow:
            raise HTTPException(status_code=404, detail="no passkeys for this account")
        opts = new_login_challenge(allow_credentials=allow)
        app.state.accounts.store_passkey_challenge(acct.id, opts["challenge"])
        return {**opts, "account_id": acct.id}

    @app.post("/auth/passkey/login/verify")
    def passkey_login_verify(req: PasskeyLoginVerify, request: Request) -> dict:
        acct = app.state.accounts.by_id(req.account_id)
        if acct is None:
            raise HTTPException(status_code=401, detail="unknown account")
        expected = app.state.accounts.pop_passkey_challenge(acct.id)
        if not expected or expected != req.challenge:
            raise HTTPException(status_code=400, detail="passkey challenge mismatch")
        stored = app.state.accounts.passkey_by_id(acct.id, req.credential_id)
        if stored is None:
            raise HTTPException(status_code=401, detail="unknown passkey")
        if not verify_login(
            challenge=req.challenge,
            credential_id=req.credential_id,
            client_data_json=req.client_data_json,
            stored=stored,
        ):
            raise HTTPException(status_code=401, detail="passkey verification failed")
        ctx = _ctx(request)
        app.state.accounts.oauth_login_success(acct.id, method="passkey", **ctx)
        return session_fn(acct)

    @app.get("/auth/login-history")
    def login_history(acct=Depends(current_account)) -> dict:
        return {"events": app.state.accounts.login_history(acct.id)}

    @app.get("/auth/security")
    def security_summary(acct=Depends(current_account)) -> dict:
        return {
            "totp_enabled": acct.totp_enabled,
            "passkeys": credentials_public(acct.passkeys),
            "oauth_linked": bool(acct.oauth_subject),
            "recent_logins": app.state.accounts.login_history(acct.id, limit=5),
        }
