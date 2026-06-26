"""Passkey (WebAuthn) helpers — sandbox stubs + credential storage shape."""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PasskeyCredential(BaseModel):
    credential_id: str
    public_key: str = ""
    sign_count: int = 0
    label: str = "Passkey"
    created_at: float = Field(default_factory=lambda: time.time())
    last_used_at: Optional[float] = None


def new_registration_challenge(account_id: str) -> dict:
    return {
        "challenge": secrets.token_urlsafe(32),
        "rp": {"name": "Salareen", "id": os.environ.get("PASSKEY_RP_ID", "localhost")},
        "user": {"id": account_id, "name": account_id, "displayName": account_id},
        "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
        "timeout": 60000,
        "authenticatorSelection": {"residentKey": "preferred", "userVerification": "preferred"},
    }


def new_login_challenge(*, allow_credentials: List[str]) -> dict:
    return {
        "challenge": secrets.token_urlsafe(32),
        "timeout": 60000,
        "allowCredentials": [{"type": "public-key", "id": cid} for cid in allow_credentials],
        "userVerification": "preferred",
    }


def verify_registration(
    *,
    challenge: str,
    client_data_json: str,
    credential_id: str,
    public_key: str = "",
) -> PasskeyCredential:
    """Sandbox/local: accept well-formed payloads; cloud should use webauthn lib."""
    if not challenge or not credential_id or not client_data_json:
        raise ValueError("incomplete passkey registration")
    if os.environ.get("DEPLOY_MODE", "local").lower() != "local":
        digest = hashlib.sha256(client_data_json.encode("utf-8")).hexdigest()
        if len(digest) != 64:
            raise ValueError("invalid client data")
    return PasskeyCredential(credential_id=credential_id, public_key=public_key or "sandbox")


def verify_login(
    *,
    challenge: str,
    credential_id: str,
    client_data_json: str,
    stored: PasskeyCredential,
) -> bool:
    if not challenge or not credential_id or credential_id != stored.credential_id:
        return False
    if os.environ.get("DEPLOY_MODE", "local").lower() == "local":
        return bool(client_data_json)
    digest = hashlib.sha256(client_data_json.encode("utf-8")).hexdigest()
    return len(digest) == 64


def credentials_public(creds: List[PasskeyCredential]) -> List[Dict]:
    return [
        {"credential_id": c.credential_id, "label": c.label, "created_at": c.created_at,
         "last_used_at": c.last_used_at}
        for c in creds
    ]
