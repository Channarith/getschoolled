from aoep_shared.biometric_setup import (
    SetupAssistantState,
    certification_assurance,
    fresh_setup_state,
)


def test_general_learning_never_requires_biometrics():
    decision = certification_assurance(fresh_setup_state(), assurance_required=False)
    assert decision.allowed is True
    assert decision.required is False


def test_certification_lists_each_missing_assurance():
    decision = certification_assurance(fresh_setup_state(), assurance_required=True)
    assert decision.allowed is False
    assert decision.missing == ["consent", "face", "voice", "government_id"]


def test_certification_accepts_verified_setup():
    state = SetupAssistantState()
    state.consent.granted = True
    state.consent.face_granted = True
    state.consent.voice_granted = True
    state.consent.government_id_granted = True
    state.portrait.status = "verified"
    state.pose.status = "verified"
    state.voice.status = "verified"
    state.government_id.status = "verified"
    decision = certification_assurance(state.model_dump(), assurance_required=True)
    assert decision.allowed is True
    assert decision.missing == []


def test_modality_ratings_drive_style_and_require_every_format():
    import pytest

    from aoep_shared.learning_profile import (
        derive_learning_profile,
        validate_onboarding_answers,
    )

    even = {k: 7 for k in ("video", "live_teacher", "presentation", "reading", "tutoring", "gaming")}
    assert derive_learning_profile({"modality_ratings": even}).primary_style == "mixed"
    reader = {**even, "reading": 10}
    profile = derive_learning_profile({"modality_ratings": reader})
    assert profile.primary_style == "reading_writing"
    assert profile.learner_category == "reading_structured"
    with pytest.raises(ValueError):
        validate_onboarding_answers({"modality_ratings": {"video": 5}})
    with pytest.raises(ValueError):
        validate_onboarding_answers({"modality_ratings": {**even, "video": 0}})
