from __future__ import annotations

from theodore_audio_translation_lab.audio_policy import AudioPolicy


def test_known_language_is_low_latency_and_auto_gets_more_context():
    policy = AudioPolicy()
    assert policy.window_ms("es") == 1200
    assert policy.window_ms("auto") == 2000
    assert policy.window_ms("auto") > policy.window_ms("es")


def test_adaptive_gate_tracks_noise_floor_but_has_absolute_floor():
    policy = AudioPolicy(noise_gate_margin_db=9, absolute_gate_db=-48)
    assert policy.gate_threshold_db(-70) == -48  # never too permissive
    assert policy.gate_threshold_db(-45) == -36  # noisy room raises gate


def test_noise_gate_skips_silence_and_keeps_speech():
    policy = AudioPolicy(min_speech_ratio=0.12)
    assert not policy.should_upload(
        noise_floor_db=-60, peak_db=-55, speech_ratio=0.03, bytes_size=1000
    )
    assert not policy.should_upload(
        noise_floor_db=-60, peak_db=-30, speech_ratio=0.05, bytes_size=1000
    )
    assert policy.should_upload(
        noise_floor_db=-60, peak_db=-25, speech_ratio=0.4, bytes_size=1000
    )
    assert not policy.should_upload(
        noise_floor_db=-60, peak_db=-25, speech_ratio=0.4, bytes_size=0
    )


def test_env_policy_is_clamped(monkeypatch):
    monkeypatch.setenv("AUDIO_CAPTURE_WINDOW_MS", "100")
    monkeypatch.setenv("AUDIO_AUTO_WINDOW_MS", "99999")
    monkeypatch.setenv("AUDIO_GATE_MARGIN_DB", "999")
    policy = AudioPolicy.from_env()
    assert policy.capture_window_ms == 600
    assert policy.auto_detect_window_ms == 5000
    assert policy.noise_gate_margin_db == 24


def test_public_policy_has_real_filter_chain():
    payload = AudioPolicy().public_dict()
    assert payload["browser_constraints"] == {
        "echoCancellation": True,
        "noiseSuppression": True,
        "autoGainControl": True,
    }
    assert payload["highpass_hz"] == 80
    assert payload["lowpass_hz"] == 7500
    assert payload["compressor"]["ratio"] == 4
