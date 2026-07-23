"""Google / Facebook / Apple OAuth login verification (dual-mode: sandbox + cloud)."""

from __future__ import annotations

import base64
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class OAuthError(Exception):
    pass


def _deploy_mode() -> str:
    return os.environ.get("DEPLOY_MODE", "local").lower()


def oauth_provider_status() -> dict:
    """Return backend OAuth provider availability for UI gating."""
    deploy_mode = _deploy_mode()
    sandbox_enabled = deploy_mode == "local"
    google_live = bool(os.environ.get("GOOGLE_CLIENT_ID", "").strip())
    facebook_live = bool(
        os.environ.get("FACEBOOK_APP_ID", "").strip()
        and os.environ.get("FACEBOOK_APP_SECRET", "").strip()
    )
    apple_live = bool(os.environ.get("APPLE_BUNDLE_ID", "").strip())

    def _provider(live_enabled: bool, missing: str) -> dict:
        if sandbox_enabled:
            return {"enabled": True, "mode": "sandbox", "reason": ""}
        if live_enabled:
            return {"enabled": True, "mode": "live", "reason": ""}
        return {"enabled": False, "mode": "disabled", "reason": missing}

    return {
        "sandbox_enabled": sandbox_enabled,
        "google": _provider(google_live, "GOOGLE_CLIENT_ID not configured"),
        "facebook": _provider(facebook_live, "FACEBOOK_APP_ID/SECRET not configured"),
        "apple": _provider(apple_live, "APPLE_BUNDLE_ID not configured"),
    }


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
    if not data.get("email_verified"):
        raise OAuthError("Google account email is not verified. Please verify your Google account email first.")
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


def _b64url_decode(s: str) -> bytes:
    """Decode a base64url string without padding."""
    s = s.replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s)


def verify_apple_identity_token(identity_token: str) -> dict:
    """Return {email, sub, name} from an Apple Sign In identity token (JWT)."""
    token = (identity_token or "").strip()
    if not token:
        raise OAuthError("missing Apple identity_token")
    # Accept tokens from both the mobile app (bundle ID) and the web Services ID.
    bundle_id = os.environ.get("APPLE_BUNDLE_ID", "com.aiclassroom.app").strip()
    services_id = os.environ.get("APPLE_SERVICES_ID", "com.aiclassroom.web").strip()
    valid_audiences = list({bundle_id, services_id})  # deduplicated

    # Sandbox: accept prefixed fake tokens for local dev.
    if _deploy_mode() == "local" and token.startswith("sandbox_apple_"):
        email = token.removeprefix("sandbox_apple_")
        if "@" not in email:
            email = f"{email}@privaterelay.appleid.com"
        return {"email": email.lower(), "sub": f"apple:{email}", "name": ""}

    try:
        import jwt as pyjwt
        from jwt.algorithms import RSAAlgorithm
    except ImportError as exc:
        raise OAuthError("PyJWT[cryptography] not installed; add it to requirements.txt") from exc

    # Fetch Apple's public keys.
    jwks = _http_get_json("https://appleid.apple.com/auth/keys")

    # Identify the key used to sign this token.
    try:
        header = pyjwt.get_unverified_header(token)
    except Exception as exc:
        raise OAuthError(f"invalid Apple token header: {exc}") from exc
    kid = header.get("kid")
    key_data = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not key_data:
        raise OAuthError("Apple signing key not found in JWKS")

    public_key = RSAAlgorithm.from_jwk(json.dumps(key_data))
    try:
        claims = pyjwt.decode(
            token, public_key, algorithms=["RS256"],
            audience=valid_audiences,
            options={"verify_exp": True},
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise OAuthError("Apple token expired") from exc
    except pyjwt.InvalidTokenError as exc:
        raise OAuthError(f"Apple token invalid: {exc}") from exc

    sub = claims.get("sub", "")
    email = (claims.get("email") or "").lower()
    if not sub:
        raise OAuthError("Apple token missing sub claim")
    # Apple may withhold email on subsequent sign-ins; use sub as fallback identity.
    if not email:
        email = f"{sub}@privaterelay.appleid.com"
    return {"email": email, "sub": f"apple:{sub}", "name": ""}
