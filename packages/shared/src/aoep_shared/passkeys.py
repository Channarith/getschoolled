"""Passkey (WebAuthn) helpers — local sandbox + fail-closed cloud verify."""

from __future__ import annotations

import base64
import hashlib
import json
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


def _sandbox_allowed() -> bool:
    mode = os.environ.get("DEPLOY_MODE", "local").lower()
    if mode == "local":
        return True
    return os.environ.get("PASSKEY_SANDBOX", "").lower() in ("1", "true", "yes")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _client_data_binds_challenge(client_data_json: str, challenge: str) -> bool:
    """Require clientDataJSON to be webauthn.* and embed the issued challenge."""
    try:
        data = json.loads(client_data_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    typ = str(data.get("type") or "")
    if typ not in ("webauthn.create", "webauthn.get"):
        return False
    raw_chal = str(data.get("challenge") or "")
    if not raw_chal or not challenge:
        return False
    # Browsers send the challenge as base64url; also accept raw equality for
    # local sandbox fixtures that echo the challenge string.
    if raw_chal == challenge:
        return True
    try:
        decoded = _b64url_decode(raw_chal).decode("utf-8", errors="ignore")
        if decoded == challenge:
            return True
    except Exception:
        pass
    try:
        if _b64url_decode(raw_chal) == challenge.encode("utf-8"):
            return True
    except Exception:
        pass
    # Some clients hash the challenge into clientData; accept sha256 hex match.
    digest = hashlib.sha256(challenge.encode("utf-8")).hexdigest()
    return raw_chal == digest


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
    """Local/sandbox: accept well-formed payloads with challenge binding.

    Cloud without PASSKEY_SANDBOX fails closed until a real WebAuthn verifier
    (signature over authenticatorData+clientDataHash) is wired.
    """
    if not challenge or not credential_id or not client_data_json:
        raise ValueError("incomplete passkey registration")
    if not _client_data_binds_challenge(client_data_json, challenge):
        raise ValueError("clientDataJSON does not bind the issued challenge")
    if not _sandbox_allowed():
        raise ValueError(
            "passkey registration requires a WebAuthn verifier in cloud; "
            "set PASSKEY_SANDBOX=1 only for non-production testing"
        )
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
    if not client_data_json or not _client_data_binds_challenge(client_data_json, challenge):
        return False
    if not _sandbox_allowed():
        # Fail closed: without cryptographic assertion verify, do not mint sessions.
        return False
    return True


def credentials_public(creds: List[PasskeyCredential]) -> List[Dict]:
    return [
        {"credential_id": c.credential_id, "label": c.label, "created_at": c.created_at,
         "last_used_at": c.last_used_at}
        for c in creds
    ]
