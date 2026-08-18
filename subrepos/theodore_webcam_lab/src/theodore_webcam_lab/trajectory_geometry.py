"""Face/hand trajectory features for excitement, interest, and dozing.

Per-frame landmarks cannot tell a lean-in from a restless fidget or a slow
head sag from sitting still. These formulas run over a short history of face
(and optional hand) points and emit 0..1 scores the analyzer folds into
attention / behavior.

The browser duplicates the pure arithmetic (it needs scores before the round
trip). ``tests/test_trajectory_geometry.py`` pins the JS constants and formula
shapes against this module.
"""

from __future__ import annotations

from dataclasses import dataclass


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class TrajectoryTuning:
    # Global frame motion above this suppresses excitement (whole-body shift).
    global_motion_suppress: float = 0.55
    # Face-local energy scale: average landmark speed (norm units / s).
    face_energy_ref: float = 0.35
    hand_energy_ref: float = 0.55
    # Pitch-down degrees per second that saturates the sag score.
    sag_ref_deg_per_s: float = 8.0
    # Soft boost weights used by the analyzer (mirrored for documentation).
    excitement_attention_boost: float = 0.12
    interest_attention_boost: float = 0.18
    # Hold gates (also on VisionTuning for live knobs).
    dozing_min_hold_ms: float = 2_500.0
    interest_min_hold_ms: float = 1_500.0
    music_min_hold_ms: float = 2_500.0
    held_object_min_hold_ms: float = 2_500.0


DEFAULT_TRAJECTORY_TUNING = TrajectoryTuning()


@dataclass(frozen=True)
class LandmarkSample:
    """One history frame of the points the scores need."""

    timestamp_ms: int
    nose_y: float
    brow_y: float
    chin_y: float
    eye_mid_x: float
    eye_mid_y: float
    face_size: float
    pitch_deg: float | None = None
    brow_raise: float = 0.0
    smile: float = 0.0
    gaze_frontal: float = 0.5
    hand_wrist_y: float | None = None
    hand_tip_y: float | None = None
    hand_wrist_x: float | None = None


@dataclass(frozen=True)
class TrajectoryReading:
    face_motion_energy: float
    hand_gesture_energy: float
    head_sag_rate: float
    excitement_score: float
    interest_score: float
    dozing_score: float


def _mean_speed(
    history: list[LandmarkSample],
    getter,
    *,
    min_pairs: int = 2,
) -> float:
    """Average absolute velocity of one scalar channel across consecutive samples."""
    if len(history) < min_pairs + 1:
        return 0.0
    speeds: list[float] = []
    for i in range(1, len(history)):
        prev, cur = history[i - 1], history[i]
        raw_dt = cur.timestamp_ms - prev.timestamp_ms
        if raw_dt <= 0:
            # Duplicate/out-of-order timestamp — clamping dt to 1ms amplified
            # tiny jitter into a 1000x phantom speed.
            continue
        dt = raw_dt / 1000.0
        a, b = getter(prev), getter(cur)
        if a is None or b is None:
            continue
        speeds.append(abs(float(b) - float(a)) / dt)
    if not speeds:
        return 0.0
    return sum(speeds) / len(speeds)


def face_motion_energy(
    history: list[LandmarkSample],
    tuning: TrajectoryTuning = DEFAULT_TRAJECTORY_TUNING,
) -> float:
    """High-frequency face-local motion (nose / brow / chin), scale-normalized."""
    if len(history) < 3:
        return 0.0
    sizes = [max(0.05, s.face_size) for s in history]
    size = sum(sizes) / len(sizes)

    def scaled(getter):
        return _mean_speed(history, getter) / size

    energy = (
        scaled(lambda s: s.nose_y)
        + scaled(lambda s: s.brow_y)
        + scaled(lambda s: s.chin_y)
        + scaled(lambda s: s.eye_mid_x) * 0.5
    ) / 3.5
    return _clamp01(energy / max(1e-6, tuning.face_energy_ref))


def hand_gesture_energy(
    history: list[LandmarkSample],
    tuning: TrajectoryTuning = DEFAULT_TRAJECTORY_TUNING,
) -> float:
    if len(history) < 3:
        return 0.0
    wrist = _mean_speed(history, lambda s: s.hand_wrist_y)
    tip = _mean_speed(history, lambda s: s.hand_tip_y)
    energy = max(wrist, tip)
    return _clamp01(energy / max(1e-6, tuning.hand_energy_ref))


def head_sag_rate(
    history: list[LandmarkSample],
    tuning: TrajectoryTuning = DEFAULT_TRAJECTORY_TUNING,
) -> float:
    """Monotonic pitch-down drift in deg/s, clamped 0..1. Positive = down."""
    pitched = [s for s in history if s.pitch_deg is not None]
    if len(pitched) < 3:
        return 0.0
    first, last = pitched[0], pitched[-1]
    if last.timestamp_ms <= first.timestamp_ms:
        return 0.0  # no real interval — a 1ms clamp would amplify jitter 1000x
    dt = (last.timestamp_ms - first.timestamp_ms) / 1000.0
    delta = float(last.pitch_deg) - float(first.pitch_deg)  # type: ignore[arg-type]
    # Only count downward sag; looking up is not dozing.
    rate = max(0.0, delta) / dt
    # Require mostly monotonic: average step should share the sign of the net.
    steps = 0
    down_steps = 0
    for i in range(1, len(pitched)):
        d = float(pitched[i].pitch_deg) - float(pitched[i - 1].pitch_deg)  # type: ignore[arg-type]
        steps += 1
        if d > 0.05:
            down_steps += 1
    if steps and down_steps / steps < 0.55:
        rate *= 0.35
    return _clamp01(rate / max(1e-6, tuning.sag_ref_deg_per_s))


def excitement_score(
    *,
    face_energy: float,
    hand_energy: float,
    global_motion: float,
    brow_raise: float = 0.0,
    smile: float = 0.0,
    tuning: TrajectoryTuning = DEFAULT_TRAJECTORY_TUNING,
) -> float:
    """Burst of face/hand energy that is not a whole-frame camera shift."""
    if global_motion >= tuning.global_motion_suppress:
        return 0.0
    burst = max(face_energy, hand_energy * 0.85)
    express = max(brow_raise, smile) * 0.35
    # Mid-band: tiny jitter is noise; sustained thrash is fidget, not excitement.
    shaped = _clamp01((burst - 0.18) / 0.55) * (1.0 - _clamp01((burst - 0.85) / 0.20))
    return _clamp01(shaped * 0.75 + express + face_energy * 0.15)


def interest_score(
    *,
    face_size_delta: float,
    gaze_frontal: float,
    brow_raise: float,
    face_energy: float,
    global_motion: float,
    fidget: float = 0.0,
    tuning: TrajectoryTuning = DEFAULT_TRAJECTORY_TUNING,
) -> float:
    """Sustained lean-in + stable frontal gaze with low restlessness."""
    if global_motion >= tuning.global_motion_suppress or fidget >= 0.70:
        return 0.0
    # Positive face_size_delta = moved closer (lean toward the camera).
    lean = _clamp01(face_size_delta / 0.08)
    stable = _clamp01(gaze_frontal)
    quiet_face = 1.0 - _clamp01((face_energy - 0.25) / 0.55)
    return _clamp01(0.45 * lean + 0.30 * stable + 0.15 * brow_raise + 0.10 * quiet_face)


def dozing_score(
    *,
    sag: float,
    face_energy: float,
    eyes_closed_score: float = 0.0,
    tuning: TrajectoryTuning = DEFAULT_TRAJECTORY_TUNING,
) -> float:
    """Still face + head sagging down; eyes-closed strengthens but is not required."""
    still = 1.0 - _clamp01(face_energy / 0.40)
    base = 0.55 * sag + 0.35 * still + 0.25 * _clamp01(eyes_closed_score)
    # Need some sag or closed eyes; pure stillness is not dozing.
    if sag < 0.15 and eyes_closed_score < 0.35:
        base *= 0.25
    return _clamp01(base)


def face_size_delta(history: list[LandmarkSample]) -> float:
    if len(history) < 2:
        return 0.0
    return float(history[-1].face_size) - float(history[0].face_size)


def evaluate_trajectory(
    history: list[LandmarkSample],
    *,
    global_motion: float = 0.0,
    fidget: float = 0.0,
    eyes_closed_score: float = 0.0,
    tuning: TrajectoryTuning = DEFAULT_TRAJECTORY_TUNING,
) -> TrajectoryReading:
    face_e = face_motion_energy(history, tuning)
    hand_e = hand_gesture_energy(history, tuning)
    sag = head_sag_rate(history, tuning)
    last = history[-1] if history else None
    brow = float(last.brow_raise) if last else 0.0
    smile = float(last.smile) if last else 0.0
    gaze = float(last.gaze_frontal) if last else 0.5
    return TrajectoryReading(
        face_motion_energy=face_e,
        hand_gesture_energy=hand_e,
        head_sag_rate=sag,
        excitement_score=excitement_score(
            face_energy=face_e,
            hand_energy=hand_e,
            global_motion=global_motion,
            brow_raise=brow,
            smile=smile,
            tuning=tuning,
        ),
        interest_score=interest_score(
            face_size_delta=face_size_delta(history),
            gaze_frontal=gaze,
            brow_raise=brow,
            face_energy=face_e,
            global_motion=global_motion,
            fidget=fidget,
            tuning=tuning,
        ),
        dozing_score=dozing_score(
            sag=sag,
            face_energy=face_e,
            eyes_closed_score=eyes_closed_score,
            tuning=tuning,
        ),
    )


def external_music_score(
    *,
    elevated: bool,
    flux: float,
    prominence: float,
    steady_peak: bool,
    speech_ratio: float,
    sharp_attack: bool,
    music_active_ms: float,
    hold_ms: float = 2000.0,
) -> float:
    """Broadband / moving-spectrum ambient music — opposite of a ringtone.

    Ringtone wants high prominence + steady peak + low flux. Music wants the
    inverse: sustained elevation with flux or a moving peak, without keystroke
    attacks. Speech-only phone calls stay on the phonecall path.
    """
    if sharp_attack or not elevated:
        return 0.0
    musical = (flux >= 2.0 or not steady_peak) and prominence < 14.0
    # Pure voice (high speech, low flux) is a call, not outside music.
    if speech_ratio > 0.62 and flux < 2.0:
        musical = False
    if not musical:
        return 0.0
    return _clamp01(music_active_ms / max(1.0, hold_ms))


def held_object_score(
    *,
    phone_grid: float,
    phone_stare: float,
    hand_below_face: float,
    lower_blob: float = 0.0,
) -> float:
    """Fuse luminance phone cues, stare residual, and hand-below-face geometry.

    Record-only in this pass — does not replace the existing ``phone_visible``
    cheating path.
    """
    grid = _clamp01(phone_grid)
    stare = _clamp01(phone_stare)
    hand = _clamp01(hand_below_face)
    blob = _clamp01(lower_blob)
    fused = max(grid * 0.55 + hand * 0.45, stare * 0.70 + hand * 0.30, blob * 0.50 + hand * 0.40)
    # Need at least one visual cue and preferably a hand.
    if grid < 0.20 and stare < 0.25 and blob < 0.25:
        return 0.0
    return _clamp01(fused)
