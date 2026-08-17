from __future__ import annotations

from theodore_webcam_lab.analysis import WebcamSessionAnalyzer
from theodore_webcam_lab.audio_quality import estimate_noise_filter_effectiveness
from theodore_webcam_lab.types import ClassMode, WebcamSignal
from theodore_webcam_lab.vision_tuning import VisionTuning


def test_noise_filter_derived_from_noise_floor_and_snr():
    quiet = estimate_noise_filter_effectiveness(
        noise_filter_effectiveness_score=None,
        audio_noise_level_db=32.0,
        audio_snr_db=22.0,
        noise_suppression_enabled=True,
        tuning=VisionTuning(),
    )
    loud = estimate_noise_filter_effectiveness(
        noise_filter_effectiveness_score=None,
        audio_noise_level_db=68.0,
        audio_snr_db=6.0,
        noise_suppression_enabled=False,
        tuning=VisionTuning(),
    )
    assert quiet is not None and loud is not None
    assert quiet > loud
    assert quiet >= 0.5


def test_explicit_noise_filter_score_is_kept():
    score = estimate_noise_filter_effectiveness(
        noise_filter_effectiveness_score=0.91,
        audio_noise_level_db=60.0,
        audio_snr_db=5.0,
    )
    assert score == 0.91


def test_analyzer_no_longer_leaves_noise_filter_na_when_audio_present():
    result = WebcamSessionAnalyzer().evaluate(
        session_id="audio-1",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="camera-local",
                timestamp_ms=1,
                face_count=1,
                liveness_state="live",
                audio_noise_level_db=38.0,
                audio_snr_db=18.0,
                microphone_input_level_score=0.55,
                mic_clipping_ratio=0.01,
            )
        ],
    )
    p = result.participants[0]
    assert p.noise_filter_effectiveness_score is not None
    assert p.microphone_quality_score is not None
    assert p.noise_filter_effectiveness_score > 0.4
