"""Bridge live-room virtual gifts to the identity rewards ledger.

When a participant joins with a valid session token, gift balance and spend
use identity ``/rewards`` instead of the sandbox ``LiveRoomGiftLedger``.
Host credits for gifts received go through an internal earn endpoint.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from .identity_sync import identity_base_url, internal_token


class LiveRoomRewardsError(Exception):
    """Identity rewards call failed (insufficient balance, auth, etc.)."""


def account_from_authorization(authorization: str, *, timeout_s: float = 5.0) -> Optional[str]:
    """Resolve account id from a Bearer session token via identity ``/auth/me``."""
    auth = (authorization or "").strip()
    if not auth.lower().startswith("bearer "):
        return None
    url = f"{identity_base_url()}/auth/me"
    req = urllib.request.Request(url, headers={"Authorization": auth})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None
    return str(data.get("id") or "").strip() or None


def rewards_balance_from_auth(authorization: str, *, timeout_s: float = 5.0) -> Optional[int]:
    """Return identity rewards balance for the bearer token, or None if unavailable."""
    auth = (authorization or "").strip()
    if not auth.lower().startswith("bearer "):
        return None
    url = f"{identity_base_url()}/rewards"
    req = urllib.request.Request(url, headers={"Authorization": auth})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None
    try:
        return int(data.get("balance", 0))
    except (TypeError, ValueError):
        return None


def spend_rewards_via_auth(
    authorization: str,
    amount: int,
    *,
    reason: str,
    ref: str = "",
    timeout_s: float = 5.0,
) -> int:
    """Deduct points from the caller's identity ledger. Returns new balance."""
    auth = (authorization or "").strip()
    if not auth.lower().startswith("bearer "):
        raise LiveRoomRewardsError("sign in to spend reward points on gifts")
    url = f"{identity_base_url()}/rewards/spend"
    body = json.dumps({"amount": amount, "reason": reason, "ref": ref}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": auth},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = "insufficient points"
        try:
            payload = json.loads(exc.read().decode())
            detail = payload.get("detail") or detail
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        raise LiveRoomRewardsError(str(detail)) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LiveRoomRewardsError("could not reach identity rewards") from exc
    try:
        return int(data.get("balance", 0))
    except (TypeError, ValueError) as exc:
        raise LiveRoomRewardsError("invalid rewards response") from exc


def earn_rewards_internal(
    account_id: str,
    amount: int,
    *,
    reason: str,
    ref: str = "",
    timeout_s: float = 5.0,
) -> bool:
    """Credit an account via the internal earn endpoint (orchestrator → identity)."""
    acct = (account_id or "").strip()
    if not acct or amount <= 0:
        return False
    url = f"{identity_base_url()}/internal/rewards/earn"
    body = json.dumps(
        {"account_id": acct, "amount": amount, "reason": reason, "ref": ref}
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Internal-Token": internal_token(),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False
