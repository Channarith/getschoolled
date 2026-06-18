"""Education-platform connectors: LMS / SIS (Integrations, Phase 18).

Offline-testable building blocks for the common standards:
- LTI 1.3 resource-link launch parsing (claim validation -> launch context).
- OneRoster roster sync (users/enrollments -> normalized members).
- LTI AGS grade passback payloads + xAPI statements for results export.
- A ConnectorProvider abstraction + MockLMS for tests.

Full JWT/JWKS signature validation and live HTTP calls are production concerns
(behind config/secrets); the data shapes + mapping logic are exercised here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_LTI = "https://purl.imsglobal.org/spec/lti/claim"


@dataclass
class LtiContext:
    user_id: str
    context_id: str
    roles: List[str]
    name: str = ""


def parse_lti_launch(claims: Dict) -> LtiContext:
    """Validate an LTI 1.3 resource-link launch and extract the context."""
    if claims.get(f"{_LTI}/message_type") != "LtiResourceLinkRequest":
        raise ValueError("not an LtiResourceLinkRequest")
    if str(claims.get(f"{_LTI}/version", "")) != "1.3.0":
        raise ValueError("unsupported LTI version (expected 1.3.0)")
    sub = claims.get("sub")
    if not sub:
        raise ValueError("missing subject (user id)")
    context = claims.get(f"{_LTI}/context", {}) or {}
    return LtiContext(
        user_id=str(sub),
        context_id=str(context.get("id", "")),
        roles=list(claims.get(f"{_LTI}/roles", []) or []),
        name=str(claims.get("name", "")),
    )


@dataclass
class RosterMember:
    user_id: str
    role: str
    name: str


def parse_oneroster(payload: Dict) -> List[RosterMember]:
    """Map a OneRoster users payload to normalized roster members."""
    members: List[RosterMember] = []
    for u in payload.get("users", []) or []:
        name = " ".join(p for p in (u.get("givenName"), u.get("familyName")) if p) \
            or u.get("name", "")
        members.append(RosterMember(
            user_id=str(u.get("sourcedId") or u.get("id") or ""),
            role=str(u.get("role", "student")),
            name=name,
        ))
    return [m for m in members if m.user_id]


def build_ags_score(user_id: str, score: float, maximum: float, *,
                    line_item: str = "homework") -> Dict:
    """LTI Assignment & Grade Services score payload (grade passback)."""
    return {
        "userId": user_id,
        "lineItem": line_item,
        "scoreGiven": score,
        "scoreMaximum": maximum,
        "activityProgress": "Completed",
        "gradingProgress": "FullyGraded",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def build_xapi_statement(actor: str, verb: str, object_id: str, *,
                         scaled: Optional[float] = None) -> Dict:
    """An xAPI statement for results export to an LRS (SCORM/xAPI)."""
    stmt: Dict = {
        "actor": {"name": actor},
        "verb": {"id": f"http://adlnet.gov/expapi/verbs/{verb}", "display": {"en-US": verb}},
        "object": {"id": object_id},
    }
    if scaled is not None:
        stmt["result"] = {"score": {"scaled": scaled}}
    return stmt


class ConnectorProvider:
    """Base for an LMS/SIS connector (Canvas/Moodle/Classroom/...)."""

    name = "lms"

    def roster(self, context_id: str) -> List[RosterMember]:
        raise NotImplementedError

    def push_grade(self, score_payload: Dict) -> Dict:
        raise NotImplementedError


@dataclass
class MockLMS(ConnectorProvider):
    name: str = "mock-lms"
    _roster: List[RosterMember] = field(default_factory=list)
    pushed: List[Dict] = field(default_factory=list)

    def roster(self, context_id: str) -> List[RosterMember]:
        return list(self._roster)

    def push_grade(self, score_payload: Dict) -> Dict:
        self.pushed.append(score_payload)
        return {"accepted": True, "resultUrl": f"mock-lms://results/{score_payload.get('userId')}"}
