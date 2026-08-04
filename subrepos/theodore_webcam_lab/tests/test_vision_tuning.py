"""Tests for the recognition tuning knobs, Sobel imaging, and quality gates."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from theodore_webcam_lab.analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from theodore_webcam_lab.imaging import analyze_luminance_grid
from theodore_webcam_lab.main import app
from theodore_webcam_lab.types import ClassMode, WebcamSignal
from theodore_webcam_lab.vision_tuning import PRESETS, VisionTuning

client = TestClient(app)


def sharp_grid(n: int = 16, lo: float = 0.30, hi: float = 0.70) -> list[list[float]]:
    """A hard vertical step: high-percentile gradient, no exposure clipping."""
    return [[lo] * (n // 2) + [hi] * (n // 2) for _ in range(n)]


def blurred_grid(n: int = 16, lo: float = 0.35, hi: float = 0.65) -> list[list[float]]:
    """A smooth ramp: detail is spread out, so gradients stay low everywhere."""
    return [[lo + (hi - lo) * x / (n - 1) for x in range(n)] for _ in range(n)]


# --------------------------------------------------------------------- tuning
def test_defaults_are_valid_and_round_trip():
    tuning = VisionTuning()
    knobs = tuning.to_dict()
    assert knobs["silhouette_foreground_threshold"] == 0.95
    assert VisionTuning(**knobs) == tuning


def test_every_knob_is_env_overridable():
    tuning = VisionTuning.from_env(
        {
            "AOEP_VISION_LIGHT_UNDEREXPOSED_LUMA": "0.05",
            "AOEP_VISION_SOBEL_BINARY_THRESHOLD": "0.42",
            "AOEP_VISION_SILHOUETTE_CONSECUTIVE_FRAMES": "7",
            "AOEP_VISION_AUDIO_MAX_NOISE_LEVEL_DB": "61.5",
        }
    )
    assert tuning.light_underexposed_luma == 0.05
    assert tuning.sobel_binary_threshold == 0.42
    assert tuning.silhouette_consecutive_frames == 7
    assert isinstance(tuning.silhouette_consecutive_frames, int)
    assert tuning.audio_max_noise_level_db == 61.5


def test_blank_env_values_fall_back_to_defaults():
    tuning = VisionTuning.from_env({"AOEP_VISION_LIGHT_MIN_QUALITY": "  "})
    assert tuning.light_min_quality == VisionTuning().light_min_quality


def test_invalid_knob_values_are_rejected():
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        VisionTuning(light_min_quality=1.7)
    with pytest.raises(ValueError, match="below light_overexposed_luma"):
        VisionTuning(light_underexposed_luma=0.9, light_overexposed_luma=0.4)
    with pytest.raises(ValueError, match="audio_noise_clean_db"):
        VisionTuning(audio_noise_clean_db=80.0, audio_noise_loud_db=40.0)
    with pytest.raises(ValueError, match="must be numeric|must be a number"):
        VisionTuning.from_env({"AOEP_VISION_LIGHT_MIN_QUALITY": "bright"})


def test_patched_rejects_unknown_knobs_and_applies_known_ones():
    tuning = VisionTuning()
    updated = tuning.patched({"sobel_min_edge_density": 0.09})
    assert updated.sobel_min_edge_density == 0.09
    # original is frozen/unchanged
    assert tuning.sobel_min_edge_density == VisionTuning().sobel_min_edge_density
    with pytest.raises(ValueError, match="Unknown tuning knob"):
        tuning.patched({"make_it_better": 1.0})


def test_presets_are_all_valid_and_differ_from_defaults():
    default = VisionTuning()
    for name in PRESETS:
        preset = VisionTuning.preset(name)
        preset.validate()
        if name != "balanced":
            assert preset != default, f"preset {name} changed nothing"
    assert VisionTuning.preset("balanced") == default
    with pytest.raises(ValueError, match="Unknown preset"):
        VisionTuning.preset("cinema")


def test_analyzer_policy_reads_env():
    policy = AnalyzerPolicy.from_env(
        {"AOEP_VISION_GAZE_AWAY_GRACE_MS": "1500", "AOEP_VISION_SOLO_MAX_FACES": "2"}
    )
    assert policy.gaze_away_grace_ms == 1500
    assert policy.solo_max_faces == 2


# -------------------------------------------------------------- Sobel imaging
def test_sobel_separates_sharp_from_blurred():
    sharp = analyze_luminance_grid(sharp_grid())
    blurred = analyze_luminance_grid(blurred_grid())
    assert sharp.sharpness_score > blurred.sharpness_score * 3
    assert sharp.blurry is False
    assert blurred.blurry is True


def test_sobel_binary_threshold_knob_changes_edge_density():
    grid = sharp_grid()
    loose = analyze_luminance_grid(grid, tuning=VisionTuning(sobel_binary_threshold=0.01))
    tight = analyze_luminance_grid(grid, tuning=VisionTuning(sobel_binary_threshold=0.95))
    assert loose.edge_density > tight.edge_density
    assert tight.edge_density == 0.0


def test_exposure_flags_track_lighting_knobs():
    dark = analyze_luminance_grid([[0.05] * 8 for _ in range(8)])
    bright = analyze_luminance_grid([[0.97] * 8 for _ in range(8)])
    assert dark.underexposed is True and "lighting_underexposed" in dark.flags
    assert bright.overexposed is True and "lighting_overexposed" in bright.flags

    # Loosening the knob stops the same frame being flagged.
    tolerant = analyze_luminance_grid(
        [[0.05] * 8 for _ in range(8)],
        tuning=VisionTuning(light_underexposed_luma=0.01, light_max_clipped_black_ratio=1.0),
    )
    assert tolerant.underexposed is False


def test_grid_accepts_0_255_scale_and_validates_shape():
    scaled = analyze_luminance_grid([[0] * 8 + [255] * 8 for _ in range(16)])
    unit = analyze_luminance_grid([[0.0] * 8 + [1.0] * 8 for _ in range(16)])
    assert scaled.sharpness_score == unit.sharpness_score
    with pytest.raises(ValueError, match="at least 3x3"):
        analyze_luminance_grid([[0.1, 0.2], [0.3, 0.4]])
    with pytest.raises(ValueError, match="same length"):
        analyze_luminance_grid([[0.1, 0.2, 0.3], [0.1, 0.2], [0.1, 0.2, 0.3]])
    with pytest.raises(ValueError, match="must be numbers"):
        analyze_luminance_grid([["a", 0.2, 0.3], [0.1, 0.2, 0.3], [0.1, 0.2, 0.3]])


def test_pure_python_and_numpy_backends_agree():
    import theodore_webcam_lab.imaging as imaging

    grid = sharp_grid()
    original = imaging._np
    try:
        imaging._np = None
        python_result = analyze_luminance_grid(grid)
    finally:
        imaging._np = original
    numpy_result = analyze_luminance_grid(grid)
    assert python_result.backend == "python"
    assert python_result.sharpness_score == numpy_result.sharpness_score
    assert python_result.edge_density == numpy_result.edge_density
    assert python_result.mean_gradient == numpy_result.mean_gradient


# ------------------------------------------------------------- quality gates
def _signal(**overrides: object) -> WebcamSignal:
    base: dict[str, object] = {
        "participant_id": "learner",
        "timestamp_ms": 1_000,
        "face_count": 1,
        "liveness_state": "live",
        "foreground_ratio": 0.4,
        "motion_score": 0.2,
    }
    base.update(overrides)
    return WebcamSignal(**base)


def test_distance_calibration_knobs_change_estimated_metres():
    signal = _signal(face_size_ratio=0.20)
    default = WebcamSessionAnalyzer().evaluate(
        session_id="d1", mode=ClassMode.SOLO, signals=[signal]
    )
    assert default.participants[0].distance_from_camera_m == 1.0

    # A wide-angle lens sees a larger face at the same distance.
    wide = WebcamSessionAnalyzer(tuning=VisionTuning.preset("wide_angle_laptop")).evaluate(
        session_id="d2", mode=ClassMode.SOLO, signals=[signal]
    )
    assert wide.participants[0].distance_from_camera_m == 1.4


def test_distance_gates_flag_too_close_and_too_far():
    analyzer = WebcamSessionAnalyzer()
    close = analyzer.evaluate(
        session_id="d3", mode=ClassMode.SOLO, signals=[_signal(face_size_ratio=0.9)]
    )
    far = analyzer.evaluate(
        session_id="d4", mode=ClassMode.SOLO, signals=[_signal(face_size_ratio=0.07)]
    )
    assert "too_close_to_camera" in close.participants[0].quality_flags
    assert "too_far_from_camera" in far.participants[0].quality_flags


def test_lighting_and_audio_gates_are_reported():
    analyzer = WebcamSessionAnalyzer()
    result = analyzer.evaluate(
        session_id="gates",
        mode=ClassMode.SOLO,
        signals=[
            _signal(
                light_quality_score=0.10,
                mean_luminance=0.05,
                audio_noise_level_db=70.0,
                audio_snr_db=4.0,
                microphone_input_level_score=0.1,
                noise_filter_effectiveness_score=0.2,
            )
        ],
    )
    flags = result.participants[0].quality_flags
    assert "lighting_below_min_quality" in flags
    assert "lighting_underexposed" in flags
    assert "high_background_noise" in flags
    assert "low_audio_snr" in flags
    assert "microphone_quality_low" in flags
    assert "noise_filter_weak" in flags
    assert result.quality_summary.quality_flag_counts["lighting_underexposed"] == 1
    assert result.participants[0].recognition_confidence < 0.5


def test_clean_frame_has_high_confidence_and_no_flags():
    result = WebcamSessionAnalyzer().evaluate(
        session_id="clean",
        mode=ClassMode.SOLO,
        signals=[
            _signal(
                face_size_ratio=0.20,
                light_quality_score=0.85,
                mean_luminance=0.5,
                image_detection_confidence=0.95,
                sharpness_score=0.8,
                edge_density=0.2,
                microphone_input_level_score=0.9,
                noise_filter_effectiveness_score=0.85,
                audio_noise_level_db=34.0,
                audio_snr_db=26.0,
            )
        ],
    )
    participant = result.participants[0]
    assert participant.quality_flags == []
    assert participant.recognition_confidence > 0.8
    assert result.quality_summary.avg_recognition_confidence > 0.8


def test_server_derives_sobel_readings_from_a_luminance_grid():
    result = WebcamSessionAnalyzer().evaluate(
        session_id="grid",
        mode=ClassMode.SOLO,
        signals=[_signal(luminance_grid=blurred_grid())],
    )
    participant = result.participants[0]
    assert participant.sharpness_score is not None
    assert participant.edge_density is not None
    assert "image_blurry" in participant.quality_flags


def test_tuning_change_flips_the_same_frame_from_failing_to_passing():
    signal = _signal(luminance_grid=blurred_grid())
    strict = WebcamSessionAnalyzer().evaluate(
        session_id="t1", mode=ClassMode.SOLO, signals=[signal]
    )
    lenient = WebcamSessionAnalyzer(
        tuning=VisionTuning(sharpness_min_quality=0.02, sobel_min_edge_density=0.0)
    ).evaluate(session_id="t2", mode=ClassMode.SOLO, signals=[signal])
    assert "image_blurry" in strict.participants[0].quality_flags
    assert "image_blurry" not in lenient.participants[0].quality_flags


def test_audio_mapping_knobs_shift_microphone_quality():
    signal = _signal(audio_snr_db=15.0, audio_noise_level_db=50.0)
    default = WebcamSessionAnalyzer().evaluate(
        session_id="a1", mode=ClassMode.SOLO, signals=[signal]
    )
    noisy_room = WebcamSessionAnalyzer(tuning=VisionTuning.preset("noisy_room")).evaluate(
        session_id="a2", mode=ClassMode.SOLO, signals=[signal]
    )
    # The noisy-room preset expects a louder floor, so the same audio scores better.
    assert (
        noisy_room.participants[0].microphone_quality_score
        > default.participants[0].microphone_quality_score
    )


# ------------------------------------------------------------------ endpoints
def test_tuning_endpoints_get_patch_and_reject():
    original = client.get("/api/theodore/vision/tuning")
    assert original.status_code == 200
    body = original.json()
    assert "knobs" in body and "presets" in body
    assert body["env_prefix"] == "AOEP_VISION_"
    baseline = body["knobs"]["sobel_binary_threshold"]

    patched = client.patch(
        "/api/theodore/vision/tuning", json={"knobs": {"sobel_binary_threshold": 0.31}}
    )
    assert patched.status_code == 200
    assert patched.json()["knobs"]["sobel_binary_threshold"] == 0.31
    assert client.get("/api/theodore/vision/tuning").json()["knobs"][
        "sobel_binary_threshold"
    ] == 0.31

    bad_knob = client.patch("/api/theodore/vision/tuning", json={"knobs": {"nope": 1}})
    assert bad_knob.status_code == 422
    bad_value = client.patch(
        "/api/theodore/vision/tuning", json={"knobs": {"light_min_quality": 5.0}}
    )
    assert bad_value.status_code == 422

    restored = client.patch(
        "/api/theodore/vision/tuning",
        json={"knobs": {"sobel_binary_threshold": baseline}},
    )
    assert restored.status_code == 200


def test_preset_endpoint_applies_and_404s_on_unknown():
    applied = client.post("/api/theodore/vision/tuning/preset/high_accuracy")
    assert applied.status_code == 200
    assert applied.json()["knobs"]["image_min_quality"] == 0.60
    assert client.post("/api/theodore/vision/tuning/preset/nope").status_code == 404
    assert client.post("/api/theodore/vision/tuning/preset/balanced").status_code == 200


def test_imaging_analyze_endpoint():
    resp = client.post(
        "/api/theodore/vision/imaging/analyze", json={"luminance_grid": sharp_grid()}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["width"] == 16 and body["height"] == 16
    assert body["sharpness_score"] > 0.3
    assert body["blurry"] is False
    assert set(body["signal_fields"]) >= {"sharpness_score", "light_quality_score"}

    blurred = client.post(
        "/api/theodore/vision/imaging/analyze", json={"luminance_grid": blurred_grid()}
    )
    assert blurred.json()["blurry"] is True

    assert (
        client.post(
            "/api/theodore/vision/imaging/analyze",
            json={"luminance_grid": [[0.1, 0.2, 0.3], [0.1, 0.2], [0.1, 0.2, 0.3]]},
        ).status_code
        == 422
    )
