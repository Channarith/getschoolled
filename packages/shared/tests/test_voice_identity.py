import math

import pytest

from aoep_shared import voice_identity
from aoep_shared.voice_identity import (
    SherpaSpeakerProvider,
    VoiceIdentityUnavailable,
    _validate_signal,
    resolve_model_path,
)


def test_explicit_model_path_must_exist(tmp_path, monkeypatch):
    model = tmp_path / "speaker.onnx"
    model.write_bytes(b"x")
    monkeypatch.setenv("VOICEPRINT_MODEL_PATH", str(model))
    assert resolve_model_path() == str(model)
    monkeypatch.setenv("VOICEPRINT_MODEL_PATH", str(tmp_path / "missing.onnx"))
    with pytest.raises(VoiceIdentityUnavailable, match="not found"):
        resolve_model_path()


def test_default_model_downloads_once_and_checks_hash(tmp_path, monkeypatch):
    monkeypatch.delenv("VOICEPRINT_MODEL_PATH", raising=False)
    monkeypatch.setenv("VISION_MODEL_DIR", str(tmp_path))
    payload = b"pinned speaker model"
    monkeypatch.setattr(voice_identity, "DEFAULT_MODEL_SHA256", __import__("hashlib").sha256(payload).hexdigest())
    calls = []

    def fake_download(url, dest):
        calls.append(url)
        with open(dest, "wb") as stream:
            stream.write(payload)

    monkeypatch.setattr("aoep_shared.vision.models._download", fake_download)
    path = resolve_model_path()
    assert path == str(tmp_path / voice_identity.DEFAULT_MODEL_NAME)
    assert resolve_model_path() == path
    assert calls == [voice_identity.DEFAULT_MODEL_URL]


def test_default_model_rejects_tampered_download(tmp_path, monkeypatch):
    monkeypatch.delenv("VOICEPRINT_MODEL_PATH", raising=False)
    monkeypatch.setenv("VISION_MODEL_DIR", str(tmp_path))

    def fake_download(url, dest):
        with open(dest, "wb") as stream:
            stream.write(b"not the pinned model")

    monkeypatch.setattr("aoep_shared.vision.models._download", fake_download)
    with pytest.raises(VoiceIdentityUnavailable, match="checksum"):
        resolve_model_path()
    assert not (tmp_path / voice_identity.DEFAULT_MODEL_NAME).exists()


def test_default_model_download_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("VOICEPRINT_MODEL_PATH", raising=False)
    monkeypatch.setenv("VISION_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("VOICEPRINT_MODEL_DOWNLOAD", "0")
    with pytest.raises(VoiceIdentityUnavailable, match="disabled"):
        resolve_model_path()


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


def test_gallery_read_with_wrong_key_is_unavailable_not_empty(tmp_path):
    from aoep_shared.voice_identity import EncryptedVoiceGallery, VoiceIdentityUnavailable

    path = str(tmp_path / "voiceprints.bin")
    EncryptedVoiceGallery(path, "old-key")._write({"s1": [0.1, 0.2]})
    rotated = EncryptedVoiceGallery(path, "new-key")
    with pytest.raises(VoiceIdentityUnavailable):
        rotated.remove("s1")
    # The unreadable file is left alone rather than overwritten with an empty gallery.
    assert EncryptedVoiceGallery(path, "old-key")._read() == {"s1": [0.1, 0.2]}
