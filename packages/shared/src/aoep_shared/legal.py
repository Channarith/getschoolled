"""Legal notices registry + user acceptance/agreement records.

A small, versioned registry of the user-facing legal documents (LICENSE + the
files in legal/) plus an acceptance store so the product can require users to
agree before use and prove they did. Pure/offline-testable; services hold the
store and expose it over HTTP.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Notice:
    id: str
    title: str
    version: str
    summary: str
    path: str          # repo-relative source of truth


NOTICES: List[Notice] = [
    Notice("disclaimer", "AI & Consent Disclaimer", "1.0",
           "One-time notice: AI-driven course; you consent, aware of legal terms "
           "and liabilities, and that regulatory requirements are met.",
           "legal/DISCLAIMER.txt"),
    Notice("license", "Software License", "1.0",
           "Proprietary license; lawful, authorized educational use only.", "LICENSE"),
    Notice("terms", "Terms of Use", "1.0",
           "AI disclosure, minors/school use, lawful use, academic integrity.",
           "legal/TERMS.txt"),
    Notice("privacy", "Privacy Notice", "1.0",
           "FERPA, COPPA (2025), GDPR, BIPA; data minimization, retention, rights.",
           "legal/PRIVACY.txt"),
    Notice("aup", "Acceptable Use Policy", "1.0",
           "Prohibited + region-restricted uses (incl. EU emotion-recognition ban).",
           "legal/ACCEPTABLE_USE.txt"),
    Notice("dpa", "Data Processing Addendum", "1.0",
           "School-official exception, residency, breach notification.", "legal/DPA.txt"),
    Notice("security", "Security Policy", "1.0",
           "Vulnerability disclosure + user breach-notification policy.", "SECURITY.txt"),
    Notice("sweepstakes", "Rewards & Sweepstakes Rules", "1.0",
           "Points/rewards + prize sweepstakes official rules (no purchase necessary).",
           "legal/SWEEPSTAKES.txt"),
]

# Notices a user MUST accept before using the service. The one-time AI & consent
# disclaimer is required first so users proceed fully informed.
REQUIRED_NOTICE_IDS = ("disclaimer", "terms", "privacy", "aup")


def notice_versions() -> Dict[str, str]:
    return {n.id: n.version for n in NOTICES}


class Acceptance(BaseModel):
    user_id: str
    accepted: Dict[str, str] = Field(default_factory=dict)  # notice_id -> version
    accepted_at: float = Field(default_factory=lambda: time.time())


class AcceptanceStore:
    def __init__(self) -> None:
        self._by_user: Dict[str, Acceptance] = {}

    def accept(self, user_id: str, notice_ids: List[str]) -> Acceptance:
        versions = notice_versions()
        rec = self._by_user.get(user_id) or Acceptance(user_id=user_id)
        for nid in notice_ids:
            if nid in versions:
                rec.accepted[nid] = versions[nid]
        rec.accepted_at = time.time()
        self._by_user[user_id] = rec
        return rec

    def get(self, user_id: str) -> Acceptance | None:
        return self._by_user.get(user_id)

    def has_accepted_required(self, user_id: str) -> bool:
        rec = self._by_user.get(user_id)
        if rec is None:
            return False
        versions = notice_versions()
        # Must have accepted the CURRENT version of every required notice.
        return all(rec.accepted.get(nid) == versions[nid] for nid in REQUIRED_NOTICE_IDS)

    def outstanding(self, user_id: str) -> List[str]:
        """Required notice ids the user still needs to accept (or re-accept)."""
        rec = self._by_user.get(user_id)
        versions = notice_versions()
        out: List[str] = []
        for nid in REQUIRED_NOTICE_IDS:
            if rec is None or rec.accepted.get(nid) != versions[nid]:
                out.append(nid)
        return out
