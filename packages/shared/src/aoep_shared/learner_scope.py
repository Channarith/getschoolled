"""Authorize a caller for one student record.

Internal services (the orchestrator) present ``X-Internal-Token``. A signed-in
member presents the same session token identity uses. The member may only
touch students on their own account.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .auth import verify_token
from .identity_sync import identity_base_url, internal_token
from .internal_auth import is_internal_caller


def _bearer(request) -> str:
    header = request.headers.get("authorization", "") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _presented_internal(request) -> str:
    return request.headers.get("x-internal-token") or _bearer(request)


def is_internal_request(request) -> bool:
    return is_internal_caller(_presented_internal(request))


def session_account_id(request) -> str:
    """Account id from a user session token, or empty when it is not one."""
    token = _bearer(request)
    if not token or is_internal_caller(token):
        # A bearer that is the internal token is not a user session.
        if is_internal_caller(request.headers.get("x-internal-token") or ""):
            return ""
    key = os.environ.get("AUTH_SIGNING_KEY", "dev-auth-signing-key").encode()
    claims = verify_token(token, key) if token else None
    if not claims or claims.get("purpose") or claims.get("kind"):
        return ""
    if claims.get("scope") in ("internal", "agent", "teacher"):
        return ""
    return str(claims.get("sub") or "")


def account_owns_student(account_id: str, student_id: str, *, timeout_s: float = 2.0) -> bool:
    """Ask identity whether this account owns the student. Fail closed."""
    url = (
        f"{identity_base_url()}/internal/students/"
        f"{urllib.parse.quote(student_id)}/owner"
    )
    req = urllib.request.Request(
        url,
        headers={"X-Internal-Token": internal_token()},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        raise
    return str(body.get("account_id") or "") == account_id


def require_student_access(request, student_id: str) -> None:
    """401/403/503 unless the caller may read or write this student."""
    from fastapi import HTTPException

    if is_internal_request(request):
        return
    account_id = session_account_id(request)
    if not account_id:
        raise HTTPException(status_code=401, detail="sign in required")
    try:
        owned = account_owns_student(account_id, student_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="could not verify student ownership") from exc
    if not owned:
        raise HTTPException(status_code=403, detail="student is not on this account")
