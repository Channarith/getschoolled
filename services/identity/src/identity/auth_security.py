"""Extended auth routes: forgot password, 2FA, OAuth, passkeys, login audit."""

from __future__ import annotations

import logging
import os
import secrets
import time as _time

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state for security controls
# ---------------------------------------------------------------------------

# Size cap for unbounded in-process sets / dicts.  When any collection exceeds
# this limit the oldest / all entries are evicted to prevent memory exhaustion.
_MAX_AUTH_SET_SIZE = 100_000

# Bug 4: TOTP replay prevention — track (account_id, code) pairs accepted in
# the last 90 seconds so the same code cannot be used twice in one window.
_used_totp: dict[tuple, float] = {}  # (account_id, code) -> accepted_at
_TOTP_TTL = 90.0  # seconds (covers one 30-s window + one carry-over)


def _purge_used_totp() -> None:
    now = _time.time()
    expired = [k for k, ts in list(_used_totp.items()) if now - ts > _TOTP_TTL]
    for k in expired:
        _used_totp.pop(k, None)
    # Hard size cap: if TTL purge wasn't enough, drop the oldest half.
    if len(_used_totp) > _MAX_AUTH_SET_SIZE:
        _log.warning("_used_totp exceeded %d entries; evicting oldest half", _MAX_AUTH_SET_SIZE)
        cutoff = len(_used_totp) // 2
        for k in list(_used_totp.keys())[:cutoff]:
            _used_totp.pop(k, None)


def _bounded_set_add(s: set, value: str, name: str) -> None:
    """Add *value* to set *s*, evicting a random 50% when the size cap is hit.

    Previously this called s.clear() which would re-enable all previously
    burned MFA tokens and used reset tokens. Now we evict half randomly so
    burned tokens are still mostly (>50%) protected after eviction.
    """
    if len(s) >= _MAX_AUTH_SET_SIZE:
        import random as _random
        _log.warning("%s exceeded %d entries; evicting 50%% to prevent memory exhaustion", name, _MAX_AUTH_SET_SIZE)
        to_remove = _random.sample(list(s), len(s) // 2)
        for item in to_remove:
            s.discard(item)
    s.add(value)


def _bounded_dict_add(d: dict, key: str, value, name: str) -> None:
    """Set d[key]=value, evicting the oldest half of *d* when the size cap is hit."""
    if len(d) >= _MAX_AUTH_SET_SIZE:
        _log.warning("%s exceeded %d entries; evicting oldest half", name, _MAX_AUTH_SET_SIZE)
        cutoff = len(d) // 2
        for k in list(d.keys())[:cutoff]:
            d.pop(k, None)
    d[key] = value


# Bug 7: 2FA brute-force lockout — after 5 wrong codes the mfa_token is burned.
# These fall back to in-process dicts/sets when Redis is unavailable (single-pod
# deployments or dev). In production multi-pod deployments Redis is required for
# correct cross-pod enforcement.
MFA_MAX_ACCOUNT_FAILURES = 5  # account-scoped ceiling; survives mfa_token rotation
_mfa_fail_counts: dict[str, int] = {}  # mfa_token -> failure count (in-process fallback)
_mfa_burned: set[str] = set()         # mfa_tokens invalidated by lockout (in-process fallback)
_mfa_account_fail_counts: dict[str, int] = {}  # account_id -> cumulative failures (bypass-resistant)

# Bug 8: Password-reset token single-use (in-process fallback).
_used_reset_tokens: set[str] = set()

# ── Redis helpers for distributed auth state ─────────────────────────────────

def _get_redis():
    """Return a Redis client if available, else None (graceful degradation)."""
    try:
        from .persistence import _redis_client  # noqa: PLC0415
        return _redis_client()
    except Exception:
        return None


_MFA_FAIL_KEY = "identity:mfa_fail:{token}"
_MFA_BURN_KEY = "identity:mfa_burned:{token}"
_MFA_ACCOUNT_FAIL_KEY = "identity:mfa_account_fail:{account_id}"
_RESET_USED_KEY = "identity:reset_used:{token}"
_MFA_TTL = 300  # 5 minutes (mfa_token lifetime)
_RESET_TTL = 3600  # 1 hour (reset token lifetime)


def _mfa_fail_count(token: str) -> int:
    r = _get_redis()
    if r:
        try:
            return int(r.get(_MFA_FAIL_KEY.format(token=token)) or 0)
        except Exception:
            pass
    return _mfa_fail_counts.get(token, 0)


def _mfa_fail_increment(token: str) -> int:
    r = _get_redis()
    if r:
        try:
            key = _MFA_FAIL_KEY.format(token=token)
            count = r.incr(key)
            r.expire(key, _MFA_TTL)
            return int(count)
        except Exception:
            pass
    count = _mfa_fail_counts.get(token, 0) + 1
    _mfa_fail_counts[token] = count
    return count


def _mfa_is_burned(token: str) -> bool:
    r = _get_redis()
    if r:
        try:
            return bool(r.exists(_MFA_BURN_KEY.format(token=token)))
        except Exception:
            pass
    return token in _mfa_burned


def _mfa_burn(token: str) -> None:
    r = _get_redis()
    if r:
        try:
            key = _MFA_BURN_KEY.format(token=token)
            r.set(key, "1", ex=_MFA_TTL)
            return
        except Exception:
            pass
    _bounded_set_add(_mfa_burned, token, "_mfa_burned")


def _mfa_account_fail_increment(account_id: str) -> int:
    """Increment account-level MFA failure count. Survives mfa_token rotation."""
    r = _get_redis()
    if r:
        try:
            key = _MFA_ACCOUNT_FAIL_KEY.format(account_id=account_id)
            count = r.incr(key)
            r.expire(key, 3600)
            return int(count)
        except Exception:
            pass
    count = _mfa_account_fail_counts.get(account_id, 0) + 1
    _bounded_dict_add(_mfa_account_fail_counts, account_id, count, "_mfa_account_fail_counts")
    return count


def _mfa_account_fail_count(account_id: str) -> int:
    r = _get_redis()
    if r:
        try:
            return int(r.get(_MFA_ACCOUNT_FAIL_KEY.format(account_id=account_id)) or 0)
        except Exception:
            pass
    return _mfa_account_fail_counts.get(account_id, 0)


def _reset_token_is_used(token: str) -> bool:
    r = _get_redis()
    if r:
        try:
            return bool(r.exists(_RESET_USED_KEY.format(token=token)))
        except Exception:
            pass
    return token in _used_reset_tokens


def _reset_token_mark_used(token: str) -> None:
    r = _get_redis()
    if r:
        try:
            r.set(_RESET_USED_KEY.format(token=token), "1", ex=_RESET_TTL)
            return
        except Exception:
            pass
    _bounded_set_add(_used_reset_tokens, token, "_used_reset_tokens")


_TOTP_REDIS_KEY = "identity:totp_used:{account_id}:{code}"


def _totp_is_used(account_id: str, code: str) -> bool:
    """Check TOTP code was already accepted (Redis-backed, falls back to in-process)."""
    r = _get_redis()
    if r:
        try:
            return bool(r.exists(_TOTP_REDIS_KEY.format(account_id=account_id, code=code)))
        except Exception:
            pass
    totp_key = (account_id, code)
    now = _time.time()
    ts = _used_totp.get(totp_key)
    return ts is not None and now - ts <= _TOTP_TTL


def _totp_mark_used(account_id: str, code: str) -> None:
    """Record TOTP code as used (Redis-backed, falls back to in-process)."""
    r = _get_redis()
    if r:
        try:
            r.set(_TOTP_REDIS_KEY.format(account_id=account_id, code=code), "1", ex=int(_TOTP_TTL) + 5)
            return
        except Exception:
            pass
    _used_totp[(account_id, code)] = _time.time()

from aoep_shared.auth import sign_token, verify_token  # noqa: E402
from aoep_shared.login_audit import login_context_from_headers  # noqa: E402
from aoep_shared.oauth_login import (  # noqa: E402
    OAuthError,
    oauth_provider_status,
    verify_apple_identity_token,
    verify_facebook_access_token,
    verify_google_id_token,
)
from aoep_shared.passkeys import (  # noqa: E402
    credentials_public,
    new_login_challenge,
    new_registration_challenge,
    verify_login,
    verify_registration,
)
from aoep_shared.password_reset import issue_reset_token, verify_reset_token  # noqa: E402
from aoep_shared.totp import generate_totp_secret, otpauth_uri, verify_totp  # noqa: E402
from fastapi import Depends, HTTPException, Request  # noqa: E402
from pydantic import BaseModel  # noqa: E402


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


class Setup2faRequest(BaseModel):
    code: str = ""  # required when 2FA is already active (re-provisioning)


class OAuthGoogleRequest(BaseModel):
    id_token: str


class OAuthFacebookRequest(BaseModel):
    access_token: str


class OAuthAppleRequest(BaseModel):
    identity_token: str


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
                {
                    "sub": acct.id,
                    "purpose": "mfa_pending",
                    # Unique per login so re-auth cannot reuse/reset a prior
                    # mfa_token's failure counter by minting an identical JWT.
                    "jti": secrets.token_hex(8),
                },
                token_key_fn(),
                ttl_s=300,
            )
            return {"requires_2fa": True, "mfa_token": mfa}
        return session_fn(acct)

    @app.post("/auth/2fa/verify")
    def verify_2fa_login(req: MfaVerifyRequest, request: Request) -> dict:
        # Bug 7: Reject tokens that have been burned (Redis-backed, falls back to in-process).
        if _mfa_is_burned(req.mfa_token):
            raise HTTPException(status_code=401, detail="invalid or expired MFA session")
        body = verify_token(req.mfa_token, token_key_fn())
        if not body or body.get("purpose") != "mfa_pending":
            raise HTTPException(status_code=401, detail="invalid or expired MFA session")
        acct = app.state.accounts.by_id(body.get("sub", ""))
        if acct is None or not acct.totp_enabled:
            raise HTTPException(status_code=401, detail="2FA not enabled")
        # Account-level lockout check (survives mfa_token rotation by attacker re-login).
        if _mfa_account_fail_count(acct.id) >= MFA_MAX_ACCOUNT_FAILURES:
            raise HTTPException(status_code=429, detail="too many 2FA failures; account locked")
        if not verify_totp(acct.totp_secret, req.code):
            # Bug 7: Track failures per mfa_token; burn after limit attempts (Redis-backed).
            count = _mfa_fail_increment(req.mfa_token)
            _mfa_account_fail_increment(acct.id)
            if count >= MFA_MAX_ACCOUNT_FAILURES:
                _mfa_burn(req.mfa_token)
            ctx = _ctx(request)
            app.state.accounts.record_login_event(
                acct.id, success=False, method="mfa", **ctx, reason="bad_code",
            )
            raise HTTPException(status_code=401, detail="invalid 2FA code")
        # Bug 4: Reject replayed TOTP codes in the same 30-s window.
        if _totp_is_used(acct.id, req.code):
            raise HTTPException(status_code=401, detail="TOTP code already used")
        _totp_mark_used(acct.id, req.code)
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

        # Bug 8: Prevent reset-token reuse — Redis-backed, falls back to in-process.
        if _reset_token_is_used(req.token):
            raise HTTPException(status_code=400, detail="invalid or expired reset link")
        body = verify_reset_token(req.token, token_key_fn())
        if not body:
            raise HTTPException(status_code=400, detail="invalid or expired reset link")
        try:
            validate_password(req.new_password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        # Mark token as used BEFORE writing password — prevents concurrent replay.
        _reset_token_mark_used(req.token)
        app.state.accounts.set_password(body["sub"], req.new_password)
        acct = app.state.accounts.by_id(body["sub"])
        if acct:
            acct.failed_logins = 0
            acct.locked_until = None
        return {"reset": True}

    @app.post("/auth/2fa/setup")
    def setup_2fa(
        acct=Depends(current_account),
        req: Setup2faRequest | None = None,
    ) -> dict:
        body = req or Setup2faRequest()
        if acct.totp_enabled:
            if not body.code or not verify_totp(acct.totp_secret, body.code):
                raise HTTPException(
                    status_code=409,
                    detail="current 2FA code required to re-provision authenticator",
                )
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
        try:
            acct = app.state.accounts.get_or_create_oauth_account(
                email=ident["email"], subject=ident["sub"], display_name=ident.get("name", ""),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        app.state.accounts.oauth_login_success(acct.id, method="google", **ctx)
        return session_fn(acct)

    @app.post("/auth/oauth/facebook")
    def oauth_facebook(req: OAuthFacebookRequest, request: Request) -> dict:
        ctx = _ctx(request)
        try:
            ident = verify_facebook_access_token(req.access_token)
        except OAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        try:
            acct = app.state.accounts.get_or_create_oauth_account(
                email=ident["email"], subject=ident["sub"], display_name=ident.get("name", ""),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        app.state.accounts.oauth_login_success(acct.id, method="facebook", **ctx)
        return session_fn(acct)

    @app.post("/auth/oauth/apple")
    def oauth_apple(req: OAuthAppleRequest, request: Request) -> dict:
        ctx = _ctx(request)
        try:
            ident = verify_apple_identity_token(req.identity_token)
        except OAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        try:
            acct = app.state.accounts.get_or_create_oauth_account(
                email=ident["email"], subject=ident["sub"], display_name=ident.get("name", ""),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        app.state.accounts.oauth_login_success(acct.id, method="apple", **ctx)
        return session_fn(acct)

    @app.get("/auth/oauth/providers")
    def oauth_providers() -> dict:
        return oauth_provider_status()

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
        # Bug 9: Return a generic 200 (empty challenge) for unknown emails /
        # accounts without passkeys to prevent account enumeration via 404.
        if not allow:
            opts = new_login_challenge(allow_credentials=[])
            return opts
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
