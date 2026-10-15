import math

import pytest

from aoep_shared.voice_identity import SherpaSpeakerProvider, _validate_signal


def test_voice_quality_accepts_ten_second_natural_signal():
    samples = [0.2 * math.sin(index / 20) for index in range(16000 * 10)]
    _validate_signal(samples, 16000)


def test_voice_quality_rejects_short_silent_and_clipped_audio():
    with pytest.raises(ValueError, match="between 8 and 15"):
        _validate_signal([0.1] * 16000 * 3, 16000)
    with pytest.raises(ValueError, match="silent"):
        _validate_signal([0.0] * 16000 * 10, 16000)
    with pytest.raises(ValueError, match="clipped"):
        _validate_signal([1.0] * 16000 * 10, 16000)


def test_speaker_match_uses_calibrated_cosine_threshold():
    match = SherpaSpeakerProvider.compare([1.0, 0.0], [0.8, 0.2], threshold=0.65)
    mismatch = SherpaSpeakerProvider.compare([1.0, 0.0], [0.1, 0.9], threshold=0.65)
    assert match.matched is True
    assert mismatch.matched is False
