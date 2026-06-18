"""Region-aware compliance policy engine.

Turns the legal requirements (FERPA, COPPA 2025, GDPR, BIPA/CUBI, EU AI Act) into
ENFORCEABLE runtime checks so the platform's "sole usage model follows local
laws" is not just documented but actually gated. Pure/offline-testable.

Key enforced rules:
- EU AI Act PROHIBITS emotion recognition in education -> emotion_recognition is
  disabled in the EU region (the vision provider honors this).
- Illinois (BIPA) requires WRITTEN biometric consent + a retention schedule.
- COPPA: users under 13 (US) need verifiable parental / school consent; GDPR
  uses 16 by default for the digital-consent age.
- Retention defaults are conservative and overridable per institution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .schemas import Region

# Feature identifiers the policy can gate.
FEATURE_FACE_RECOGNITION = "face_recognition"
FEATURE_ATTENTION_TRACKING = "attention_tracking"
FEATURE_EMOTION_RECOGNITION = "emotion_recognition"
FEATURE_REALTIME_BIOMETRIC_ID = "realtime_biometric_id"


@dataclass(frozen=True)
class RegionPolicy:
    region: Region
    frameworks: List[str]
    parental_consent_age: int           # consent required for users under this age
    written_biometric_consent: bool     # BIPA-style written consent
    emotion_recognition_allowed: bool   # EU AI Act bans this in education
    realtime_biometric_id_allowed: bool
    default_retention_days: int
    ai_high_risk: bool                  # EU AI Act Annex III (education)
    required_notices: List[str] = field(default_factory=lambda: ["terms", "privacy", "aup"])

    def feature_allowed(self, feature: str) -> bool:
        return {
            FEATURE_FACE_RECOGNITION: True,        # allowed with consent everywhere
            FEATURE_ATTENTION_TRACKING: True,
            FEATURE_EMOTION_RECOGNITION: self.emotion_recognition_allowed,
            FEATURE_REALTIME_BIOMETRIC_ID: self.realtime_biometric_id_allowed,
        }.get(feature, True)


_POLICIES = {
    Region.US: RegionPolicy(
        region=Region.US, frameworks=["FERPA", "COPPA", "CIPA", "PPRA"],
        parental_consent_age=13, written_biometric_consent=False,
        emotion_recognition_allowed=True, realtime_biometric_id_allowed=True,
        default_retention_days=365, ai_high_risk=False,
    ),
    Region.US_IL: RegionPolicy(
        region=Region.US_IL, frameworks=["FERPA", "COPPA", "BIPA"],
        parental_consent_age=13, written_biometric_consent=True,
        emotion_recognition_allowed=True, realtime_biometric_id_allowed=True,
        default_retention_days=365, ai_high_risk=False,
    ),
    Region.EU: RegionPolicy(
        region=Region.EU, frameworks=["GDPR", "EU AI Act"],
        parental_consent_age=16, written_biometric_consent=True,
        emotion_recognition_allowed=False,           # EU AI Act prohibition
        realtime_biometric_id_allowed=False,         # heavily restricted
        default_retention_days=180, ai_high_risk=True,
    ),
    Region.OTHER: RegionPolicy(
        region=Region.OTHER, frameworks=["baseline"],
        parental_consent_age=13, written_biometric_consent=True,
        emotion_recognition_allowed=False,           # safe default: opt-in by law
        realtime_biometric_id_allowed=False,
        default_retention_days=180, ai_high_risk=True,
    ),
}


def _coerce_region(region) -> Region:
    if isinstance(region, Region):
        return region
    try:
        return Region(str(region).lower())
    except ValueError:
        return Region.OTHER


def policy_for(region) -> RegionPolicy:
    return _POLICIES[_coerce_region(region)]


def feature_allowed(region, feature: str) -> bool:
    return policy_for(region).feature_allowed(feature)


def emotion_recognition_allowed(region) -> bool:
    return policy_for(region).emotion_recognition_allowed


def requires_parental_consent(region, age: int) -> bool:
    return age < policy_for(region).parental_consent_age


def requires_written_consent(region) -> bool:
    return policy_for(region).written_biometric_consent


def compliance_summary(region) -> dict:
    p = policy_for(region)
    return {
        "region": p.region.value,
        "frameworks": p.frameworks,
        "parental_consent_age": p.parental_consent_age,
        "written_biometric_consent": p.written_biometric_consent,
        "emotion_recognition_allowed": p.emotion_recognition_allowed,
        "realtime_biometric_id_allowed": p.realtime_biometric_id_allowed,
        "default_retention_days": p.default_retention_days,
        "ai_high_risk": p.ai_high_risk,
        "required_notices": p.required_notices,
    }
