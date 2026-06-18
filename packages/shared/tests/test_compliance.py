"""Region compliance policy engine tests."""

from aoep_shared.compliance import (
    FEATURE_EMOTION_RECOGNITION,
    FEATURE_FACE_RECOGNITION,
    compliance_summary,
    emotion_recognition_allowed,
    feature_allowed,
    policy_for,
    requires_parental_consent,
    requires_written_consent,
)
from aoep_shared.schemas import Region


def test_eu_prohibits_emotion_recognition():
    assert emotion_recognition_allowed(Region.EU) is False
    assert feature_allowed(Region.EU, FEATURE_EMOTION_RECOGNITION) is False
    # Face recognition (with consent) is still allowed.
    assert feature_allowed(Region.EU, FEATURE_FACE_RECOGNITION) is True


def test_us_allows_emotion_but_il_requires_written_consent():
    assert emotion_recognition_allowed(Region.US) is True
    assert requires_written_consent(Region.US) is False
    assert requires_written_consent(Region.US_IL) is True  # BIPA


def test_parental_consent_age_thresholds():
    assert requires_parental_consent(Region.US, 12) is True    # COPPA under 13
    assert requires_parental_consent(Region.US, 13) is False
    assert requires_parental_consent(Region.EU, 15) is True    # GDPR default 16
    assert requires_parental_consent(Region.EU, 16) is False


def test_eu_is_high_risk_under_ai_act():
    assert policy_for(Region.EU).ai_high_risk is True
    assert policy_for(Region.US).ai_high_risk is False


def test_string_region_coercion_and_summary():
    summary = compliance_summary("eu")
    assert summary["region"] == "eu"
    assert "EU AI Act" in summary["frameworks"]
    assert summary["emotion_recognition_allowed"] is False
    # Unknown region falls back to the safe baseline.
    assert compliance_summary("atlantis")["emotion_recognition_allowed"] is False
