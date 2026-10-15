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
