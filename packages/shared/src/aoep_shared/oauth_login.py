"""Google / Facebook OAuth login verification (dual-mode: sandbox + cloud)."""

from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class OAuthError(Exception):
    pass


def _deploy_mode() -> str:
    return os.environ.get("DEPLOY_MODE", "local").lower()


def _http_get_json(url: str, *, timeout: float = 10.0) -> dict:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def verify_google_id_token(id_token: str) -> dict:
    """Return {email, sub, name} from a Google ID token."""
    token = (id_token or "").strip()
    if not token:
        raise OAuthError("missing Google id_token")
    if _deploy_mode() == "local" and token.startswith("sandbox_google_"):
        email = token.removeprefix("sandbox_google_")
        if "@" not in email:
            email = f"{email}@example.com"
        return {"email": email.lower(), "sub": f"google:{email}", "name": email.split("@")[0]}
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise OAuthError("GOOGLE_CLIENT_ID not configured")
    data = _http_get_json(
        "https://oauth2.googleapis.com/tokeninfo?" + urlencode({"id_token": token})
    )
    if data.get("aud") != client_id:
        raise OAuthError("Google token audience mismatch")
    email = (data.get("email") or "").lower()
    if not email:
        raise OAuthError("Google token missing email")
    return {"email": email, "sub": f"google:{data.get('sub', email)}", "name": data.get("name", "")}


def verify_facebook_access_token(access_token: str) -> dict:
    """Return {email, sub, name} from a Facebook user access token."""
    token = (access_token or "").strip()
    if not token:
        raise OAuthError("missing Facebook access_token")
    if _deploy_mode() == "local" and token.startswith("sandbox_facebook_"):
        email = token.removeprefix("sandbox_facebook_")
        if "@" not in email:
            email = f"{email}@example.com"
        return {"email": email.lower(), "sub": f"facebook:{email}", "name": email.split("@")[0]}
    app_id = os.environ.get("FACEBOOK_APP_ID", "").strip()
    app_secret = os.environ.get("FACEBOOK_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        raise OAuthError("FACEBOOK_APP_ID/SECRET not configured")
    debug = _http_get_json(
        "https://graph.facebook.com/debug_token?"
        + urlencode({"input_token": token, "access_token": f"{app_id}|{app_secret}"})
    )
    info = debug.get("data") or {}
    if not info.get("is_valid"):
        raise OAuthError("invalid Facebook token")
    if str(info.get("app_id")) != app_id:
        raise OAuthError("Facebook token app mismatch")
    profile = _http_get_json(
        "https://graph.facebook.com/me?"
        + urlencode({"fields": "id,name,email", "access_token": token})
    )
    email = (profile.get("email") or "").lower()
    if not email:
        raise OAuthError("Facebook profile missing email permission")
    return {
        "email": email,
        "sub": f"facebook:{profile.get('id', email)}",
        "name": profile.get("name", ""),
    }
