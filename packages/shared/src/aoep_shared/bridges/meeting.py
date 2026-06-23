"""Meeting-reference parsing + platform SDK auth.

Everything here is pure (stdlib only): it turns the join URL/id a teacher pastes
into a normalized :class:`MeetingRef`, and mints the Zoom Meeting SDK signature.
This is the real auth/identity logic the bots need; it is fully testable without
any platform SDK.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

from .registry import BridgePlatform


@dataclass(frozen=True)
class MeetingRef:
    platform: BridgePlatform
    meeting_id: str
    passcode: Optional[str] = None
    tenant_id: Optional[str] = None     # Teams: AAD tenant
    raw: str = ""


# Zoom: https://zoom.us/j/123456789?pwd=..., https://us05web.zoom.us/wc/123/join,
# or a bare meeting number (real ids are 9-11 digits; we accept 3+ so short test
# ids and spaced numbers like "123 456 789" parse too).
_ZOOM_ID = re.compile(r"/(?:j|wc)/(\d{3,12})")
# Teams: a 19:...@thread.v2 conversation id, possibly embedded in a meetup-join URL.
_TEAMS_THREAD = re.compile(r"(19:[^/\"\s]+?@thread\.v2)")
# Meet: meet.google.com/abc-defg-hij or a bare xxx-xxxx-xxx code.
_MEET_CODE = re.compile(r"([a-z]{3}-[a-z]{4}-[a-z]{3})")


def parse_meeting_ref(platform: BridgePlatform, ref: str) -> MeetingRef:
    """Normalize a join URL or id into a :class:`MeetingRef`.

    Raises ``ValueError`` when the reference can't be parsed for ``platform``.
    """
    if not ref or not ref.strip():
        raise ValueError("empty meeting reference")
    ref = ref.strip()

    if platform is BridgePlatform.ZOOM:
        m = _ZOOM_ID.search(ref)
        if m:
            qs = parse_qs(urlparse(ref).query)
            passcode = (qs.get("pwd") or [None])[0]
            return MeetingRef(platform, meeting_id=m.group(1), passcode=passcode, raw=ref)
        compact = ref.replace(" ", "")
        if compact.isdigit() and 3 <= len(compact) <= 12:
            return MeetingRef(platform, meeting_id=compact, raw=ref)
        raise ValueError(f"unrecognized Zoom meeting reference: {ref!r}")

    if platform is BridgePlatform.TEAMS:
        m = _TEAMS_THREAD.search(unquote(ref))
        if not m:
            raise ValueError(f"unrecognized Teams meeting reference: {ref!r}")
        tenant = None
        qs = parse_qs(urlparse(ref).query)
        ctx = (qs.get("context") or [None])[0]
        if ctx:
            try:
                tenant = json.loads(ctx).get("Tid")
            except (ValueError, TypeError):
                tenant = None
        return MeetingRef(platform, meeting_id=m.group(1), tenant_id=tenant, raw=ref)

    if platform is BridgePlatform.MEET:
        m = _MEET_CODE.search(ref.lower())
        if not m:
            raise ValueError(f"unrecognized Google Meet reference: {ref!r}")
        return MeetingRef(platform, meeting_id=m.group(1), raw=ref)

    raise ValueError(f"unsupported platform {platform!r}")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def zoom_sdk_signature(
    sdk_key: str,
    sdk_secret: str,
    meeting_number: str,
    *,
    role: int = 0,
    now: Optional[int] = None,
    expires_in: int = 7200,
) -> str:
    """Mint a Zoom Meeting SDK JWT (HS256) for ``meeting_number``.

    Matches Zoom's current Meeting SDK auth contract: an HS256 JWT whose payload
    carries ``appKey``/``sdkKey``, the meeting number ``mn``, the ``role``
    (0 = participant, 1 = host), and ``iat``/``exp``/``tokenExp``. The bot uses
    this to authenticate before joining; minting it is a pure HMAC operation, so
    it is implemented and verifiable here without the native SDK.
    """
    if not sdk_key or not sdk_secret:
        raise ValueError("zoom sdk_key and sdk_secret are required")
    iat = int(now if now is not None else time.time())
    exp = iat + int(expires_in)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "appKey": sdk_key,
        "sdkKey": sdk_key,
        "mn": str(meeting_number),
        "role": int(role),
        "iat": iat,
        "exp": exp,
        "tokenExp": exp,
    }
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    signature = hmac.new(sdk_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + _b64url(signature)
