"""Tunable knobs for webcam recognition accuracy and audio quality scoring.

Everything the recognition pipeline used to hardcode lives here so it can be tuned
per deployment (camera, room lighting, microphone) without editing code:

  lighting     exposure limits and the fallback used when a client sends no reading
  sharpness    Sobel binary-edge thresholds used to detect defocus/motion blur
  distance     focal calibration that turns a face-box ratio into metres
  detection    presence/gaze/typing decision thresholds
  scoring      how confidence and behaviour signals are weighted into 0..1 scores
  audio        SNR/noise-floor/clipping mapping plus noise-filter expectations

Knobs are flat (not nested) on purpose: a flat set makes environment loading and
partial runtime PATCHes trivial, which is what live tuning needs.

Every field can be overridden by an environment variable named
AOEP_VISION_<FIELD_NAME_UPPERCASED>, e.g.

    AOEP_VISION_LIGHT_UNDEREXPOSED_LUMA=0.18
    AOEP_VISION_SOBEL_BINARY_THRESHOLD=0.22

Named presets give a fast starting point for common rooms; see PRESETS.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .tuning_base import env_overrides, patch_knobs

_ENV_PREFIX = "AOEP_VISION_"


@dataclass(frozen=True)
class VisionTuning:
    # --- Lighting / exposure -------------------------------------------------
    # Mean luminance is 0..1. Below/above these the frame is flagged and the
    # recognition confidence is discounted.
    light_underexposed_luma: float = 0.22
    light_overexposed_luma: float = 0.82
    light_max_clipped_black_ratio: float = 0.18
    light_max_clipped_white_ratio: float = 0.12
    light_min_quality: float = 0.35
    # Used when a client reports no light reading at all.
    light_default_quality: float = 0.5

    # --- Sharpness / Sobel binary imaging ------------------------------------
    # Gradient magnitudes are normalised to 0..1. Pixels above the binary
    # threshold count as edges; too few edges means a defocused or blurred frame.
    sobel_binary_threshold: float = 0.18
    sobel_min_edge_density: float = 0.035
    sharpness_reference_gradient: float = 0.35
    sharpness_min_quality: float = 0.30
    # Sharpness reads a high percentile of the gradient, not the mean: a genuinely
    # sharp frame can have edges on only a few percent of pixels, which a mean
    # cannot distinguish from an evenly blurred frame.
    sharpness_gradient_percentile: float = 95.0

    # --- Distance calibration ------------------------------------------------
    # distance = reference_metres * (reference_face_ratio / observed_face_ratio)
    distance_reference_face_ratio: float = 0.20
    distance_reference_metres: float = 1.0
    distance_min_face_ratio: float = 0.06
    distance_min_metres: float = 0.30
    distance_max_metres: float = 4.0
    distance_too_close_m: float = 0.45
    distance_too_far_m: float = 2.20

    # --- Detection decision thresholds ---------------------------------------
    silhouette_foreground_threshold: float = 0.95
    silhouette_motion_threshold: float = 0.08
    silhouette_consecutive_frames: int = 3
    gaze_frontal_min_threshold: float = 0.40
    gaze_down_min_threshold: float = 0.38
    eyes_closed_min_threshold: float = 0.45
    yawn_min_threshold: float = 0.48
    attention_min_threshold: float = 0.40
    distraction_min_threshold: float = 0.55
    typing_activity_min_threshold: float = 0.70
    keyboard_typing_audio_min_threshold: float = 0.65
    hands_on_face_min_threshold: float = 0.50

    # --- Sustained-posture gating --------------------------------------------
    # A single frame above threshold is noise, not a behaviour: a hand passing the
    # face or one glance down would otherwise flip the learner to "hands on face"
    # or "on their phone". Both must hold for this long before they are reported.
    hands_on_face_min_hold_ms: float = 5_000.0
    phone_visible_min_hold_ms: float = 5_000.0
    # Detection flickers frame to frame (a finger leaves the cheek, the phone is
    # briefly occluded). Drop-outs shorter than this do not restart the timer,
    # otherwise the hold above could never be reached in practice.
    posture_release_grace_ms: float = 1_200.0

    # --- Trajectory attention (face/hand history) ----------------------------
    excitement_min_threshold: float = 0.42
    interest_min_threshold: float = 0.45
    dozing_min_threshold: float = 0.48
    interest_min_hold_ms: float = 1_500.0
    dozing_min_hold_ms: float = 2_500.0
    excitement_attention_boost: float = 0.12
    interest_attention_boost: float = 0.18
    # Outside music + held object — record-only holds (no cheating).
    external_music_min_threshold: float = 0.45
    external_music_min_hold_ms: float = 2_500.0
    held_object_min_threshold: float = 0.45
    held_object_min_hold_ms: float = 2_500.0

    # --- Image detection quality scoring -------------------------------------
    image_detection_confidence_weight: float = 0.60
    image_liveness_weight: float = 0.40
    image_no_face_penalty: float = 0.35
    image_default_confidence_with_face: float = 0.85
    image_default_confidence_no_face: float = 0.35
    image_min_quality: float = 0.45

    # --- Expression / behaviour scoring weights ------------------------------
    behavior_happy_weight: float = 0.35
    behavior_known_expression_weight: float = 0.20
    behavior_unknown_expression_weight: float = 0.10
    behavior_focus_weight: float = 0.35
    behavior_integrity_weight: float = 0.30

    # --- Audio / noise filtering --------------------------------------------
    # SNR maps linearly to 0..1 across [floor, floor + span].
    audio_snr_floor_db: float = 5.0
    audio_snr_span_db: float = 25.0
    # Noise floor maps 0..1 across [clean_db (best) .. loud_db (worst)].
    audio_noise_clean_db: float = 30.0
    audio_noise_loud_db: float = 70.0
    audio_clipping_penalty: float = 2.5
    audio_min_mic_quality: float = 0.45
    audio_min_noise_filter_effectiveness: float = 0.50
    audio_max_noise_level_db: float = 55.0
    audio_min_snr_db: float = 12.0

    def __post_init__(self) -> None:
        self.validate()

    # ------------------------------------------------------------------ helpers
    def validate(self) -> None:
        """Reject knob values that would make scoring meaningless."""
        unit_interval = (
            "light_underexposed_luma",
            "light_overexposed_luma",
            "light_max_clipped_black_ratio",
            "light_max_clipped_white_ratio",
            "light_min_quality",
            "light_default_quality",
            "sobel_binary_threshold",
            "sobel_min_edge_density",
            "sharpness_reference_gradient",
            "sharpness_min_quality",
            "distance_reference_face_ratio",
            "distance_min_face_ratio",
            "silhouette_foreground_threshold",
            "silhouette_motion_threshold",
            "gaze_frontal_min_threshold",
            "gaze_down_min_threshold",
            "eyes_closed_min_threshold",
            "yawn_min_threshold",
            "attention_min_threshold",
            "distraction_min_threshold",
            "typing_activity_min_threshold",
            "keyboard_typing_audio_min_threshold",
            "excitement_min_threshold",
            "interest_min_threshold",
            "dozing_min_threshold",
            "excitement_attention_boost",
            "interest_attention_boost",
            "external_music_min_threshold",
            "held_object_min_threshold",
            "image_detection_confidence_weight",
            "image_liveness_weight",
            "image_no_face_penalty",
            "image_default_confidence_with_face",
            "image_default_confidence_no_face",
            "image_min_quality",
            "behavior_happy_weight",
            "behavior_known_expression_weight",
            "behavior_unknown_expression_weight",
            "behavior_focus_weight",
            "behavior_integrity_weight",
            "audio_min_mic_quality",
            "audio_min_noise_filter_effectiveness",
        )
        for name in unit_interval:
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0 (got {value})")

        if self.light_underexposed_luma >= self.light_overexposed_luma:
            raise ValueError(
                "light_underexposed_luma must be below light_overexposed_luma"
            )
        if self.silhouette_consecutive_frames < 1:
            raise ValueError("silhouette_consecutive_frames must be >= 1")
        if self.sharpness_reference_gradient <= 0.0:
            raise ValueError("sharpness_reference_gradient must be > 0")
        if not 50.0 <= self.sharpness_gradient_percentile <= 100.0:
            raise ValueError("sharpness_gradient_percentile must be between 50 and 100")
        if self.distance_reference_face_ratio <= 0.0:
            raise ValueError("distance_reference_face_ratio must be > 0")
        if self.distance_reference_metres <= 0.0:
            raise ValueError("distance_reference_metres must be > 0")
        if self.distance_min_metres <= 0.0:
            raise ValueError("distance_min_metres must be > 0")
        if self.distance_min_metres >= self.distance_max_metres:
            raise ValueError("distance_min_metres must be below distance_max_metres")
        if self.distance_too_close_m >= self.distance_too_far_m:
            raise ValueError("distance_too_close_m must be below distance_too_far_m")
        if self.audio_snr_span_db <= 0.0:
            raise ValueError("audio_snr_span_db must be > 0")
        if self.audio_noise_clean_db >= self.audio_noise_loud_db:
            raise ValueError("audio_noise_clean_db must be below audio_noise_loud_db")
        if self.audio_clipping_penalty < 0.0:
            raise ValueError("audio_clipping_penalty must be >= 0")
        for name in (
            "hands_on_face_min_hold_ms",
            "phone_visible_min_hold_ms",
            "posture_release_grace_ms",
            "interest_min_hold_ms",
            "dozing_min_hold_ms",
            "external_music_min_hold_ms",
            "held_object_min_hold_ms",
        ):
            if float(getattr(self, name)) < 0.0:
                raise ValueError(f"{name} must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def patched(self, overrides: dict[str, Any]) -> VisionTuning:
        """Return a new tuning with `overrides` applied (validated)."""
        return patch_knobs(self, overrides)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> VisionTuning:
        return cls(**env_overrides(cls, _ENV_PREFIX, environ))

    @classmethod
    def preset(cls, name: str) -> VisionTuning:
        key = (name or "").strip().lower()
        if key not in PRESETS:
            available = ", ".join(sorted(PRESETS))
            raise ValueError(f"Unknown preset '{name}'. Available: {available}")
        return cls(**PRESETS[key])


# Presets are partial: unspecified knobs keep their default.
PRESETS: dict[str, dict[str, Any]] = {
    # Shipping defaults.
    "balanced": {},
    # Dim rooms / evening classes: tolerate darker frames and softer edges before
    # complaining, but demand a cleaner microphone to compensate.
    # Dim rooms genuinely produce softer frames: longer exposure plus sensor
    # denoising smooths fine detail, so the sharpness and edge gates have to relax
    # far enough to accept a correctly-exposed dark room, not just a slightly dim one.
    "low_light": {
        "light_underexposed_luma": 0.08,
        "light_max_clipped_black_ratio": 0.45,
        "light_min_quality": 0.15,
        "sobel_binary_threshold": 0.10,
        "sobel_min_edge_density": 0.008,
        "sharpness_min_quality": 0.12,
        "image_min_quality": 0.35,
    },
    # Bright/backlit rooms: clamp down on blown highlights.
    "bright_room": {
        "light_overexposed_luma": 0.72,
        "light_max_clipped_white_ratio": 0.06,
        "light_min_quality": 0.45,
    },
    # Shared/noisy spaces: relax the audio gates so narration still works, and
    # raise the typing-audio bar so keyboard chatter is not read as cheating.
    "noisy_room": {
        "audio_noise_clean_db": 40.0,
        "audio_noise_loud_db": 85.0,
        "audio_max_noise_level_db": 68.0,
        "audio_min_snr_db": 8.0,
        "audio_min_mic_quality": 0.35,
        "audio_min_noise_filter_effectiveness": 0.65,
        "keyboard_typing_audio_min_threshold": 0.80,
    },
    # Proctoring/high-stakes: demand crisp, well-lit, well-framed video and treat
    # weaker distraction evidence as actionable.
    "high_accuracy": {
        "light_min_quality": 0.50,
        "sobel_min_edge_density": 0.055,
        "sharpness_min_quality": 0.45,
        "image_min_quality": 0.60,
        "distance_too_far_m": 1.60,
        "gaze_down_min_threshold": 0.50,
        "typing_activity_min_threshold": 0.55,
        "keyboard_typing_audio_min_threshold": 0.55,
        "audio_min_mic_quality": 0.55,
    },
    # Laptop webcams sit closer and have a wider field of view than the default
    # calibration assumes.
    "wide_angle_laptop": {
        "distance_reference_face_ratio": 0.28,
        "distance_too_close_m": 0.30,
        "distance_too_far_m": 1.80,
    },
}
