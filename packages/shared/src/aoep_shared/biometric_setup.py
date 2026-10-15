"""Shared contracts for setup-assistant identity assurance.

Raw camera, microphone, and identity-document media is intentionally absent
from these durable contracts. Services may process media ephemerally, but only
template references, decisions, consent, and audit timestamps are persisted.
"""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field

SETUP_SCHEMA_VERSION = 1
BIOMETRIC_CONSENT_VERSION = "2026-10-14"
VOICE_PROMPT = (
    "Today I'm ready to learn with Salareen. Can you hear my voice clearly? "
    "Yes—I'm speaking naturally and confidently."
)

SetupStep = Literal[
    "welcome",
    "learner",
    "plan",
    "preferences",
    "privacy",
    "biometrics",
    "complete",
]
VerificationState = Literal[
    "not_started", "in_progress", "pending", "verified", "failed", "declined", "revoked"
]


class VerificationRecord(BaseModel):
    status: VerificationState = "not_started"
    template_ref: str = ""
    updated_at: float | None = None
    attempts: int = 0
    reason: str = ""


class DocumentVerificationRecord(VerificationRecord):
    document_type: str = ""
    provider_reference: str = ""
    expires_at: float | None = None
    # No document number, image, or extracted identity fields may be added.


class BiometricConsent(BaseModel):
    granted: bool = False
    face_granted: bool = False
    voice_granted: bool = False
    government_id_granted: bool = False
    guardian_granted: bool = False
    policy_version: str = BIOMETRIC_CONSENT_VERSION
    retention_days: int = Field(default=365, ge=1, le=3650)
    updated_at: float | None = None


class SetupAssistantState(BaseModel):
    schema_version: int = SETUP_SCHEMA_VERSION
    current_step: SetupStep = "welcome"
    completed_at: float | None = None
    skipped_biometrics: bool = False
    assurance_level: Literal["none", "biometric", "verified_identity"] = "none"
    consent_events: list[dict[str, object]] = Field(default_factory=list)
    consent: BiometricConsent = Field(default_factory=BiometricConsent)
    portrait: VerificationRecord = Field(default_factory=VerificationRecord)
    pose: VerificationRecord = Field(default_factory=VerificationRecord)
    voice: VerificationRecord = Field(default_factory=VerificationRecord)
    government_id: DocumentVerificationRecord = Field(
        default_factory=DocumentVerificationRecord
    )


class AssuranceDecision(BaseModel):
    allowed: bool
    required: bool
    missing: list[str] = Field(default_factory=list)
    reason: str = ""


def fresh_setup_state() -> dict:
    return SetupAssistantState().model_dump()


def normalize_setup_state(value: object) -> SetupAssistantState:
    if not isinstance(value, dict):
        return SetupAssistantState()
    try:
        return SetupAssistantState.model_validate(value)
    except Exception:
        # Old or partially-written snapshots must recover to a safe state.
        return SetupAssistantState()


def certification_assurance(state: object, *, assurance_required: bool) -> AssuranceDecision:
    """Return the server-authoritative pre-start decision for a course."""
    if not assurance_required:
        return AssuranceDecision(allowed=True, required=False)
    setup = normalize_setup_state(state)
    missing: list[str] = []
    if not (
        setup.consent.granted
        and setup.consent.face_granted
        and setup.consent.voice_granted
        and setup.consent.government_id_granted
    ):
        missing.append("consent")
    if setup.portrait.status != "verified" or setup.pose.status != "verified":
        missing.append("face")
    if setup.voice.status != "verified":
        missing.append("voice")
    if setup.government_id.status != "verified":
        missing.append("government_id")
    return AssuranceDecision(
        allowed=not missing,
        required=True,
        missing=missing,
        reason="" if not missing else "identity_assurance_required",
    )


def mark_record(record: VerificationRecord, status: VerificationState, **values: object) -> dict:
    data = record.model_dump()
    data.update(values)
    data["status"] = status
    data["updated_at"] = time.time()
    data["attempts"] = record.attempts + (1 if status in {"failed", "verified", "pending"} else 0)
    return data
