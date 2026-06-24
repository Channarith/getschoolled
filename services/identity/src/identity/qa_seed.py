"""Fixed QA personas seeded at identity startup (env-gated).

Three accounts cover the main manual-test paths: a free learner, a parent with
a child profile, and a Pro-tier member for entitlement checks. Log in with the
email OR the short username alias (qa1 / qa2 / qa3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from aoep_shared.schemas import PlanTier

from .store import Account, AccountStore


@dataclass(frozen=True)
class QaPersona:
    email: str
    display_name: str
    tier: PlanTier = PlanTier.FREE
    username: str = ""
    student_display_name: str = ""
    student_age_band: str = "child"


QA_PERSONAS: List[QaPersona] = [
    QaPersona(
        "qa-learner@salareen.com",
        "QA Learner",
        username="qa1",
    ),
    QaPersona(
        "qa-parent@salareen.com",
        "QA Parent",
        username="qa2",
        student_display_name="QA Kid",
        student_age_band="child",
    ),
    QaPersona(
        "qa-pro@salareen.com",
        "QA Pro",
        tier=PlanTier.PRO,
        username="qa3",
    ),
]


def seed_qa_accounts(store: AccountStore, password: str) -> List[Account]:
    """Create the QA personas idempotently (shared password from env)."""
    seeded: List[Account] = []
    for persona in QA_PERSONAS:
        acct = store.seed_account(
            persona.email,
            password,
            display_name=persona.display_name,
            tier=persona.tier,
            username=persona.username,
        )
        if persona.student_display_name and not store.list_students(acct.id):
            store.add_student(
                acct.id,
                persona.student_display_name,
                age_band=persona.student_age_band,
            )
        seeded.append(acct)
    return seeded
