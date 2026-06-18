"""Cloud / collaboration connectors (Integrations, Phase 19).

Offline-testable building blocks for:
- Notifications (Slack / Google Workspace chat) - message payloads + Mock notifier.
- Calendar scheduling (auto-create a class event) - event payload + Mock calendar.
- SSO (OAuth2/OIDC + SAML) - claim/attribute validation -> identity.

Live HTTP and JWT signature/JWKS verification are production concerns (behind
config/secrets); the payload shapes + validation logic are exercised here. Live
class media bridging reuses bridges/{zoom,teams,meet}.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
def build_slack_message(text: str, *, channel: str = "#general") -> Dict:
    return {"channel": channel, "text": text,
            "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]}


class NotificationConnector:
    name = "notify"

    def send(self, channel: str, text: str) -> Dict:
        raise NotImplementedError


@dataclass
class MockNotifier(NotificationConnector):
    name: str = "mock-notify"
    sent: List[Dict] = field(default_factory=list)

    def send(self, channel: str, text: str) -> Dict:
        msg = build_slack_message(text, channel=channel)
        self.sent.append(msg)
        return {"ok": True, "channel": channel}


# --------------------------------------------------------------------------- #
# Calendar scheduling
# --------------------------------------------------------------------------- #
def schedule_event(title: str, start_iso: str, duration_min: int,
                   attendees: Optional[List[str]] = None) -> Dict:
    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    end = start + timedelta(minutes=duration_min)
    return {
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "attendees": list(attendees or []),
    }


class CalendarConnector:
    name = "calendar"

    def create_event(self, event: Dict) -> Dict:
        raise NotImplementedError


@dataclass
class MockCalendar(CalendarConnector):
    name: str = "mock-calendar"
    events: List[Dict] = field(default_factory=list)

    def create_event(self, event: Dict) -> Dict:
        self.events.append(event)
        return {"id": f"evt-{len(self.events)}", **event}


# --------------------------------------------------------------------------- #
# SSO (OIDC + SAML)
# --------------------------------------------------------------------------- #
@dataclass
class SsoIdentity:
    subject: str
    email: str = ""
    name: str = ""
    provider: str = ""


def verify_oidc_claims(claims: Dict, *, audience: str, now: Optional[float] = None) -> SsoIdentity:
    """Validate the essential OIDC ID-token claims and return the identity.

    (Signature/JWKS verification is done by the OIDC library in production; this
    enforces iss/aud/sub presence and expiry.)
    """
    now = time.time() if now is None else now
    if not claims.get("iss"):
        raise ValueError("missing iss")
    if claims.get("aud") != audience:
        raise ValueError("audience mismatch")
    if not claims.get("sub"):
        raise ValueError("missing sub")
    if "exp" in claims and float(claims["exp"]) < now:
        raise ValueError("token expired")
    return SsoIdentity(subject=str(claims["sub"]), email=str(claims.get("email", "")),
                       name=str(claims.get("name", "")), provider=str(claims.get("iss", "")))


def parse_saml_attributes(attributes: Dict) -> SsoIdentity:
    """Map a SAML assertion's attributes to an identity."""
    nameid = attributes.get("NameID") or attributes.get("nameid") or attributes.get("uid")
    if not nameid:
        raise ValueError("missing SAML NameID")
    return SsoIdentity(subject=str(nameid), email=str(attributes.get("email", "")),
                       name=str(attributes.get("displayName", "")), provider="saml")
