"""Live monitor UX regressions: demo seed, camera isolation, alerts."""

from __future__ import annotations

import math
import re

from fastapi.testclient import TestClient

from theodore_webcam_lab.demo_seed import build_demo_payload
from theodore_webcam_lab.imaging import analyze_luminance_grid
from theodore_webcam_lab.main import app
from theodore_webcam_lab.monitor_page import MONITOR_JS
from theodore_webcam_lab.types import WebcamSignal
from theodore_webcam_lab.vision_tuning import VisionTuning

client = TestClient(app)

# Helpers the webcam sampling loop calls. Deleting any of them during a refactor
# throws a ReferenceError that silently kills contours and expression tracking.
REQUIRED_MONITOR_JS_HELPERS = (
    "blendshapeMap",
    "emotionFromBlendshapes",
    "emotionFromLandmarkGeometry",
    "smoothMood",
    "headPoseFromMatrix",
    "headPoseFromLandmarks",
    "ensureFaceLandmarker",
    "drawFaceContoursOnOverlay",
    "drawDetectorFaceContour",
    "trackFaceContoursAndMood",
    "estimateFacialExperience",
    "sampleFrame",
    "ensureHandLandmarker",
    "trackHands",
    "handsOnFaceFromLandmarks",
    "drawHandContoursOnOverlay",
    "clamp01",
    "clampSignal",
    "holdSeconds",
    "smoothLabel",
    "smoothScore",
    "resetBehaviorSmoothing",
    "pollAudioDetector",
    "sampleClickDetector",
    "openRawMicStream",
    "resetClickDetectorState",
    "maybeToastAudio",
    "updateTiltLab",
    "renderTiltLab",
    "drawTiltGauge",
    "resetTiltPeaks",
    "loadTiltCalibration",
    "saveTiltCalibration",
)


def test_demo_seed_shows_cheating_silhouette_and_alerts():
    seeded = client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-demo-1", "frames": 12, "scenario": "group"},
    )
    assert seeded.status_code == 200
    body = seeded.json()
    assert body["scenario"] == "group"
    assert set(body["participant_ids"]) == {"student-a", "student-b", "student-c"}
    assert "student-b" in body["cheating_participant_ids"]
    assert "student-c" in body["silhouette_participant_ids"]
    assert "student_cheating_signal" in body["lesson_alert_codes"]
    assert "student_silhouette" in body["lesson_alert_codes"]

    metrics = client.get("/api/theodore/webcam/live-metrics/ux-demo-1")
    assert metrics.status_code == 200
    snap = metrics.json()
    ids = {p["participant_id"] for p in snap["participants"]}
    assert ids == {"student-a", "student-b", "student-c"}
    by_id = {p["participant_id"]: p["latest"] for p in snap["participants"]}
    assert by_id["student-b"]["suspected_cheating"] is True
    assert "phone_visible" in by_id["student-b"]["cheating_reasons"]
    assert by_id["student-c"]["silhouette_detected"] is True
    assert snap["group_student_windows"]
    assert snap["suspected_cheating_participant_ids"] == ["student-b"]
    assert snap["silhouette_participant_ids"] == ["student-c"]


def test_solo_demo_seed_has_one_student():
    """One webcam ⇒ one demo learner; group demo is opt-in."""
    seeded = client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-solo-1", "frames": 8, "scenario": "solo"},
    )
    assert seeded.status_code == 200
    body = seeded.json()
    assert body["scenario"] == "solo"
    assert body["mode"] == "solo"
    assert body["participant_ids"] == ["learner"]
    assert body["cheating_participant_ids"] == []
    assert body["silhouette_participant_ids"] == []

    snap = client.get("/api/theodore/webcam/live-metrics/ux-solo-1").json()
    assert {p["participant_id"] for p in snap["participants"]} == {"learner"}
    assert snap["mode"] == "solo"


def test_camera_local_evaluate_does_not_clobber_group_demo_metrics():
    client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-demo-2", "frames": 8},
    )
    before = client.get("/api/theodore/webcam/live-metrics/ux-demo-2").json()
    assert {p["participant_id"] for p in before["participants"]} == {
        "student-a",
        "student-b",
        "student-c",
    }

    cam = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "ux-demo-2",
            "mode": "solo",
            "persist_live_metrics": False,
            "signals": [
                {
                    "participant_id": "camera-local",
                    "timestamp_ms": 99_000,
                    "face_count": 0,
                    "foreground_ratio": 0.97,
                    "motion_score": 0.02,
                    "liveness_state": "unknown",
                }
            ],
        },
    )
    assert cam.status_code == 200
    assert cam.json()["participants"][0]["participant_id"] == "camera-local"

    after = client.get("/api/theodore/webcam/live-metrics/ux-demo-2").json()
    assert {p["participant_id"] for p in after["participants"]} == {
        "student-a",
        "student-b",
        "student-c",
    }
    assert "camera-local" not in {
        p["participant_id"] for p in after["participants"]
    }


def test_lesson_alert_acknowledge_is_recorded():
    client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-demo-3", "frames": 8},
    )
    ack = client.post(
        "/api/theodore/webcam/alerts/acknowledge",
        json={
            "session_id": "ux-demo-3",
            "code": "student_cheating_signal",
            "participant_id": "student-b",
        },
    )
    assert ack.status_code == 200
    assert "student_cheating_signal:student-b" in ack.json()["acknowledged_alert_keys"]
    metrics = client.get("/api/theodore/webcam/live-metrics/ux-demo-3").json()
    assert "student_cheating_signal:student-b" in metrics["acknowledged_alert_keys"]


def test_monitor_js_defines_every_helper_the_sampling_loop_calls():
    declared = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)", MONITOR_JS))
    missing = [name for name in REQUIRED_MONITOR_JS_HELPERS if name not in declared]
    assert not missing, f"monitor JS calls undeclared helpers: {missing}"


def test_monitor_js_clamps_every_unit_interval_signal_field():
    """An out-of-range 0..1 field 422s the whole frame, so none may be missed."""
    declared = re.search(
        r"const UNIT_SIGNAL_FIELDS = \[(.*?)\];", MONITOR_JS, re.DOTALL
    )
    assert declared, "UNIT_SIGNAL_FIELDS is no longer declared in the monitor JS"
    clamped = set(re.findall(r"'([a-z_]+)'", declared.group(1)))

    constrained = {
        name
        for name, field in WebcamSignal.model_fields.items()
        if any(getattr(m, "le", None) == 1.0 for m in field.metadata)
    }
    assert constrained - clamped == set()


def test_monitor_page_tracks_hands_only_while_they_are_in_frame():
    page = client.get("/theodore/webcam/live-monitor/demo-session")
    text = page.text
    assert "hand_landmarker.task" in text
    assert "HAND_CONNECTIONS" in text
    # Hand contours are skipped unless the detector returned landmarks this frame.
    assert "if (!faceContoursOn || !lastHandContours || !lastHandContours.hands.length) return;" in text


def test_monitor_page_smooths_attention_and_behavior_like_mood():
    text = client.get("/theodore/webcam/live-monitor/demo-session").text
    # Both labels go through the rolling majority vote, not the raw frame value.
    assert "attn = smoothLabel(attnHistory, attn);" in text
    assert "behavior = smoothLabel(behaviorHistory, behavior);" in text
    # The sub-line reports the averaged scores.
    assert "avg attention" in text
    assert "avg distraction" in text


def test_live_metrics_for_unseeded_session_is_empty_not_404():
    res = client.get("/api/theodore/webcam/live-metrics/never-seeded-session")
    assert res.status_code == 200
    body = res.json()
    assert body["updated_at_ms"] == 0
    assert body["participants"] == []


def test_monitor_page_declares_a_favicon():
    page = client.get("/theodore/webcam/live-monitor/demo-session")
    assert 'rel="icon"' in page.text


def test_monitor_page_includes_silhouette_and_demo_controls():
    page = client.get("/theodore/webcam/live-monitor/demo-session")
    assert page.status_code == 200
    text = page.text
    assert "Load solo demo (1 student)" in text
    assert "Load group demo (3 students)" in text
    assert "demo-seed-group" in text
    assert "simulated" in text.lower() or "Simulated" in text
    assert "Silhouette demo" in text
    assert "cam-overlay" in text
    assert "aspect-ratio: 16 / 9" in text
    assert "cam-res" in text
    assert "cam-sil-toggle" in text
    assert "cam-pause-overlay" in text
    assert "notifyLiveAway" in text
    assert "LIVE_AWAY_NOTIFY_MS" in text
    assert "liveCamTimestampMs" in text
    assert "LIVE_AWAY_REANNOUNCE_MS" in text
    assert "no_learner_detected" in text
    assert "PAUSED" in text
    assert "banner.pause" in text
    assert "Guide on" in text
    assert "full camera frame" in text or "full frame is scanned" in text
    assert "framing guide" in text
    assert "cam-contour-toggle" in text
    assert "Contours on" in text
    assert "trackFaceContoursAndMood" in text
    assert "emotionFromBlendshapes" in text
    assert "facial-hud" in text
    assert "facial-dist" in text
    assert "sampleLidarDistanceMeters" in text
    assert "sampleMicAudio" in text
    assert "audio-noise" in text
    assert "noiseSuppression" in text
    assert "estimateFacialFromGrid" in text
    assert "updateFacialHud" in text
    assert "updateAudioHud" in text
    assert "drawSilhouetteGuide" in text
    assert "silhouetteGuideOn" in text
    assert "you do not need to match this outline" in text
    assert "1920" in text and "1080" in text
    assert "face size in frame" in text or "LiDAR if available" in text
    assert "Run lesson action" in text
    assert "persist_live_metrics: false" in text
    assert "Timing policy" in text
    assert any(phrase in text for phrase in ("Try Theodore", "Theodore voice", "xAI Theodore"))
    assert "Issue challenge" in text
    assert "image_min_quality" in text
    assert "silhouette_foreground_threshold" in text
    assert "demo-degraded" in text
    assert "/api/theodore/webcam/alerts/action" in text


def test_lesson_alert_action_sends_private_message_and_game():
    client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-action-1", "frames": 8},
    )
    acted = client.post(
        "/api/theodore/webcam/alerts/action",
        json={
            "session_id": "ux-action-1",
            "code": "student_cheating_signal",
            "action": "notify_student_privately_and_reinforce_integrity",
            "participant_id": "student-b",
            "message": "test",
        },
    )
    assert acted.status_code == 200
    body = acted.json()
    assert body["ok"] is True
    assert "student-b" in body["summary"]
    assert body["details"]["challenge_id"]
    presentation = body["details"]["presentation"]
    assert presentation["visual_effect"] == "shield"
    assert presentation["visual_title"] == "Integrity focus challenge"
    assert "Student B" in presentation["speech_text"]
    metrics = client.get("/api/theodore/webcam/live-metrics/ux-action-1").json()
    assert metrics["private_messages"]
    assert any("Integrity" in m["body"] for m in metrics["private_messages"])
    assert "student_cheating_signal:student-b" in metrics["acknowledged_alert_keys"]


def test_lesson_actions_render_and_speak_as_theodore():
    page = client.get("/theodore/webcam/live-monitor/action-stage")
    assert page.status_code == 200
    text = page.text
    assert 'id="theodore-action"' in text
    assert 'id="theodore-action-speech"' in text
    assert 'id="theodore-action-speak"' in text
    assert "presentTheodoreAction" in text
    assert "speakCurrentAction" in text
    assert "speakTheodore(currentActionSpeech" in text
    assert "theodore-action show effect-" in text
    assert "theodore-action.speaking .theodore-mouth" in text
    assert "Theodore is taking action" in text


def test_face_mesh_loads_cdn_first_without_local_assets():
    """Regression: making the self-hosted /vendor/vision path first meant every
    session 404'd on it before reaching the CDN, so the face mesh — and the
    contours + mood cards it feeds — silently stopped appearing. With no local
    assets the page must say so and try the CDN, not the dead local path first."""
    page = client.get("/theodore/webcam/live-monitor/mesh-order").text
    assert "__VISION_LOCAL_ASSETS__" not in page, "server left the flag unsubstituted"
    assert "const VISION_LOCAL_ASSETS = false;" in page
    # The self-hosted source is only pushed when the flag is true.
    assert "if (VISION_LOCAL_ASSETS) {" in page
    # The CDN source is unconditional so it always loads out of the box.
    assert "cdn.jsdelivr.net/npm/@mediapipe/tasks-vision" in page


def test_coarse_mode_still_draws_a_contour_and_mood():
    """Regression: when the mesh cannot load and the browser has no FaceDetector,
    the accuracy pass left the panel blank. The coarse grid path must still draw
    an approximate outline (fallbackBox) and keep a mood label so the operator
    sees live face tracking — clearly badged 'coarse', not landmark-accurate."""
    page = client.get("/theodore/webcam/live-monitor/coarse-contour").text
    # Grid estimator exposes a normalised box for the coarse overlay.
    assert "grid_box" in page
    # estimateFacialExperience promotes it into a drawable fallback contour.
    assert "fallbackBox: {" in page
    assert "facial.source === 'coarse'" in page
    # The coarse oval is drawn by the existing fallback renderer.
    assert "function drawDetectorFaceContour" in page


def test_policy_timing_endpoint_and_all_vision_knobs_listed():
    policy = client.get("/api/theodore/vision/policy")
    assert policy.status_code == 200
    assert "gaze_away_grace_ms" in policy.json()["knobs"]
    patched = client.patch(
        "/api/theodore/vision/policy",
        json={"knobs": {"gaze_away_grace_ms": 2000}},
    )
    assert patched.status_code == 200
    assert patched.json()["knobs"]["gaze_away_grace_ms"] == 2000
    # restore
    client.patch("/api/theodore/vision/policy", json={"knobs": {"gaze_away_grace_ms": 45000}})

    tuning = client.get("/api/theodore/vision/tuning").json()["knobs"]
    page = client.get("/theodore/webcam/live-monitor/demo-session").text
    for name in tuning:
        assert name in page, f"vision knob {name} missing from monitor UI"


def test_click_detector_polls_faster_than_the_video_sampling_loop():
    """Keystrokes and ring onsets are missed if audio is only read per video frame.

    The analyser exposes ~21ms of audio per read, so sampling it on the 300ms
    video cadence observes about 7% of the stream and never lands on a transient.
    """
    poll_ms = re.search(r"const AUDIO_POLL_MS = (\d+)", MONITOR_JS)
    assert poll_ms, "AUDIO_POLL_MS must define the audio detector cadence"
    assert int(poll_ms.group(1)) <= 40

    assert "setInterval(pollAudioDetector, AUDIO_POLL_MS)" in MONITOR_JS
    # The video loop stays at its own slower cadence.
    assert "setInterval(sampleFrame, 300)" in MONITOR_JS

    # sampleClickDetector must be a pure reader of accumulated state; if it
    # pulls from the analyser itself we are back to the 7% duty cycle.
    reader = MONITOR_JS.split("function sampleClickDetector()")[1].split("\n    }")[0]
    assert "getFloatTimeDomainData" not in reader
    assert "getFloatFrequencyData" not in reader


def test_click_detector_listens_to_an_unprocessed_microphone_track():
    """Browser noise suppression is built to delete keystrokes and ringtones.

    The processed track is still what feeds noise-filter scoring, but detection
    has to run on a separate capture with all WebRTC processing disabled.
    """
    raw = MONITOR_JS.split("async function openRawMicStream()")[1].split("\n    }")[0]
    for constraint in ("echoCancellation: false", "noiseSuppression: false", "autoGainControl: false"):
        assert constraint in raw, f"raw mic capture must set {constraint}"

    # The detector analyser is fed by the raw source when one is available.
    assert "rawMicSource.connect(clickAnalyser)" in MONITOR_JS
    # ...and the processed graph still drives the noise-filter meter.
    assert "audioSource.connect(audioAnalyser)" in MONITOR_JS
    # The raw track must be released with the rest of the meter.
    stop = MONITOR_JS.split("function stopAudioMeter()")[1].split("\n    }")[0]
    assert "rawMicStream.getTracks().forEach((t) => t.stop())" in stop
    assert "clearInterval(audioPollTimer)" in stop


def test_audio_context_is_resumed_before_detection():
    """A suspended AudioContext reports silence forever, disabling every detector."""
    assert "audioCtx.state === 'suspended'" in MONITOR_JS
    assert "audioCtx.resume()" in MONITOR_JS
    # startAudioMeter awaits the resume + raw capture, so callers must await it.
    assert "async function startAudioMeter(stream)" in MONITOR_JS
    assert "await startAudioMeter(camStream)" in MONITOR_JS


def test_ringtone_detection_separates_a_steady_tone_from_speech():
    """A ring holds one prominent, stationary peak; a voice never stays still."""
    poll = MONITOR_JS.split("function pollAudioDetector()")[1].split("\n    }")[0]
    # Peak prominence over the band median, peak-bin stability, and spectral flux
    # are the three signals that keep a held vowel from reading as a ringtone.
    assert "prominence" in poll
    assert "steadyPeak" in poll
    assert "flux" in poll
    assert "const tonal = elevated && prominence >" in poll
    # Flux must ignore near-floor bins, which swing several dB on their own.
    assert "fluxGate" in poll
    # Ring cadences pause between bursts, so the verdict latches.
    assert "ringtoneLatchUntil" in poll
    assert "now < ringtoneLatchUntil" in MONITOR_JS


def test_keyboard_detection_uses_a_floor_that_cannot_swallow_typing():
    """A floor that rises with the signal would absorb a burst of keystrokes."""
    poll = MONITOR_JS.split("function pollAudioDetector()")[1].split("\n    }")[0]
    # Fast decay toward quiet, slow rise.
    assert "if (rms < clickNoiseFloor) clickNoiseFloor += (rms - clickNoiseFloor) * 0.25;" in poll
    assert "else clickNoiseFloor += (rms - clickNoiseFloor) * 0.002;" in poll
    # Keystrokes are sharp, HF-rich attacks - not just "louder than the floor".
    assert "sharpAttack" in poll
    assert "hfRatio" in poll


def test_audio_integrity_cards_stay_diagnosable_when_nothing_is_detected():
    """'none'/'silent' hides a dead mic; show the live input level instead."""
    hud = MONITOR_JS.split("function updateIntegrityHud(signals)")[1].split("\n    }\n\n    function")[0]
    assert "micDead" in hud
    assert "micHint" in hud
    assert "mic off" in hud


def _parse_pattern_stages() -> list[dict]:
    found = re.findall(
        r"\{\s*name:\s*'([^']+)',\s*dark:\s*(\d+),\s*light:\s*(\d+),"
        r"\s*sigma:\s*([\d.]+),\s*expects:\s*'([^']+)'\s*\}",
        MONITOR_JS,
    )
    return [
        {
            "name": name,
            "dark": int(dark),
            "light": int(light),
            "sigma": float(sigma),
            "expects": expects,
        }
        for name, dark, light, sigma, expects in found
    ]


def _render_pattern_grid(
    stage: dict, phase: int, *, period: int = 8, grid_w: int = 64, grid_h: int = 36
) -> list[list[float]]:
    """Mirror paintTestPattern() + the exact 20x box downsample to the grid.

    The JS renders at 1280 wide, which is exactly 20x the 64-wide Sobel grid, so
    the browser's drawImage reduction is a plain box average we can reproduce.
    """
    scale = 20
    hard = stage["sigma"] < 0.05
    harmonics = [] if hard else [
        (k, (2 / (k * math.pi)) * math.exp(
            -2 * math.pi**2 * stage["sigma"] ** 2 * (k / period) ** 2))
        for k in (1, 3, 5, 7, 9)
    ]
    shift = (phase % period) / period
    period_px = scale * period
    cols = []
    for x in range(grid_w * scale):
        u = ((x / period_px) + shift) % 1
        if hard:
            profile = 1.0 if u < 0.5 else 0.0
        else:
            profile = 0.5 + sum(a * math.sin(2 * math.pi * k * u) for k, a in harmonics)
            profile = min(1.0, max(0.0, profile))
        cols.append(round(stage["dark"] + (stage["light"] - stage["dark"]) * profile))
    row = [
        sum(cols[gx * scale:(gx + 1) * scale]) / scale / 255.0
        for gx in range(grid_w)
    ]
    return [list(row) for _ in range(grid_h)]


def test_test_pattern_stages_trip_exactly_their_documented_gates():
    """The pattern is only useful if each stage provably fires the gate it names.

    Renders every stage through the same maths the page uses and scores it with
    the real Sobel/exposure analyzer, so drifting a stage constant (or a default
    threshold) out of range fails here instead of silently making the button a
    no-op again.
    """
    expected = {
        "sharp · well lit": set(),
        "mild blur": set(),
        "heavy blur": {"image_blurry", "low_edge_detail"},
        "low contrast": {"low_edge_detail"},
        "underexposed": {"lighting_underexposed", "lighting_below_min_quality"},
        "overexposed": {"lighting_overexposed", "lighting_below_min_quality"},
    }
    stages = _parse_pattern_stages()
    assert {s["name"] for s in stages} == set(expected), "pattern stage set changed"

    tuning = VisionTuning()
    for stage in stages:
        # Every scroll phase must agree; a gate that flickers with the bar
        # offset would read as noise rather than a demonstration.
        for phase in range(8):
            grid = _render_pattern_grid(stage, phase)
            analysis = analyze_luminance_grid(grid, tuning=tuning)
            assert set(analysis.flags) == expected[stage["name"]], (
                f"stage {stage['name']!r} phase {phase} produced {analysis.flags}, "
                f"expected {sorted(expected[stage['name']])}"
            )


def test_test_pattern_renders_to_the_canvas_the_grid_is_sampled_from():
    """The old code drew bars into the offscreen grid only, so the preview was black."""
    paint = MONITOR_JS.split("function paintTestPattern()")[1].split("\n    }")[0]
    assert "patternCanvas.style.display = 'block'" in paint
    assert "camVideo.style.visibility = 'hidden'" in paint

    grid_fn = MONITOR_JS.split("function luminanceGrid()")[1].split("\n    }")[0]
    assert "paintTestPattern()" in grid_fn
    # The grid must come from the same canvas that is on screen.
    assert grid_fn.count("ctx.drawImage(patternCanvas, 0, 0, GRID_W, GRID_H)") == 2
    # The old invisible path must not come back.
    assert "patternPhase = (patternPhase + 1) % GRID_W" not in grid_fn


def test_test_pattern_replaces_the_person_guide_with_a_stage_caption():
    """There is nobody to frame in a synthetic pattern; the outline just confused it."""
    guide = MONITOR_JS.split("function refreshSilhouetteGuide()")[1].split("\n    }")[0]
    assert "if (usingPattern)" in guide
    assert "drawPatternCaption()" in guide
    # Caption text names the stage and what it should trip.
    caption = MONITOR_JS.split("function drawPatternCaption()")[1].split("\n    }")[0]
    assert "currentPatternStage()" in caption
    assert "stage.name" in caption
    assert "stage.expects" in caption


def test_tilt_is_measured_from_a_calibrated_neutral_not_from_level():
    """A low-mounted laptop makes the resting head pitch already negative.

    Measuring absolute pitch would call that a downward tilt, so the gauge has to
    subtract a per-seat neutral before it can separate "looking at the laptop
    webcam" from "looking at a phone".
    """
    update = MONITOR_JS.split("function updateTiltLab(facial, distanceM)")[1].split("\n    }")[0]
    assert "(tiltRawDeg - tiltNeutralDeg) * tiltDownSign" in update
    # Peaks track the calibrated value, which is what a trial is read off.
    assert "tiltPeakDown" in update and "tiltPeakUp" in update

    # The down direction is learned, because the matrix and landmark pose paths
    # do not agree on the sign of head_pose_pitch.
    assert "tiltSignCalibrated" in MONITOR_JS
    assert "tiltDownSign = delta > 0 ? 1 : -1" in MONITOR_JS


def test_the_gauge_self_starts_instead_of_waiting_for_a_button():
    """An uncalibrated gauge drew nothing but the trip line.

    That reads as a needle frozen at the trip degree, so the neutral is seeded
    from the first steady second of tracking and Set neutral only overrides it.
    """
    update = MONITOR_JS.split("function updateTiltLab(facial, distanceM)")[1].split("\n    }")[0]
    assert "if (tiltNeutralDeg == null)" in update
    assert "tiltNeutralSamples.length >= TILT_AUTO_NEUTRAL_FRAMES" in update
    assert "tiltNeutralAuto = true" in update
    # Pressing Set neutral has to clear the auto flag, otherwise the label lies.
    assert "tiltNeutralAuto = false" in MONITOR_JS
    # An auto neutral is per-seat, so it must not be persisted as a calibration.
    save = MONITOR_JS.split("function saveTiltCalibration()")[1].split("\n    }")[0]
    assert "tiltNeutralAuto ? null : tiltNeutralDeg" in save


def test_head_pitch_is_not_face_height_in_frame():
    """Pitch used to be ((chin.y - forehead.y) - 0.32) * 140.

    That is face height, i.e. how close the learner sits: it pinned raw pitch at
    a constant while the head nodded, and it never moved the gauge.
    """
    assert "((chin.y - forehead.y) - 0.32) * 140" not in MONITOR_JS
    pose = MONITOR_JS.split("function headPoseFromLandmarks(pts, aspect)")[1].split("\n    }")[0]
    assert "facePitchFromLandmarks(pts, aspect)" in pose

    # The proxy is a ratio of two spans of the same face, so it cannot move when
    # only the distance changes.
    pitch = MONITOR_JS.split("function facePitchFromLandmarks(pts, aspect)")[1].split("\n    }")[0]
    assert "geometricPitchDeg(upper, lower)" in pitch
    # Projected onto the face's own vertical axis, so head roll does not leak in.
    assert "along(chin)" in pitch and "along(forehead)" in pitch


def test_looking_down_is_scored_from_the_stare_residual():
    """A learner staring straight at the monitor scored 0.55 "looking down".

    The nose sits below the eye line and eyeLookDown rests around 0.2-0.3 for
    everyone seated, so both cues had to stop being absolute.
    """
    assert "(nose.y - midY) * 5.5" not in MONITOR_JS
    assert "lookDown * 1.35" not in MONITOR_JS
    mesh = MONITOR_JS.split("const lookDown = ((bs.eyeLookDownLeft")[1].split("const lids_down")[0]
    assert "clamp01((lookDown - lookUp - 0.25) / 0.5)" in mesh

    sample = MONITOR_JS.split("async function sampleFrame()")[1].split("const signal = {")[0]
    assert "if (stareGazeDown != null)" in sample
    assert "Math.max(stareGazeDown, facial.gaze_down_score || 0)" in sample


def test_down_direction_is_learned_from_the_signed_geometric_pitch():
    """Otherwise the operator has to press Set down before the gauge means anything."""
    learn = MONITOR_JS.split("function learnTiltSign(rawPitch, geomPitch)")[1].split("\n    }")[0]
    assert "tiltDownSign = cov > 0 ? 1 : -1" in learn
    # Only once the head has actually moved: a still head correlates noise.
    assert "TILT_SIGN_MIN_SPREAD_DEG" in learn


def test_stare_lab_reports_the_geometry_it_uses():
    page = client.get("/theodore/webcam/live-monitor/demo-session").text
    assert "Stare geometry lab" in page
    for chip in ("stare-distance", "stare-expected", "stare-residual", "stare-scores"):
        assert chip in page, f"stare chip {chip} missing from the page"
    # Layout is editable, because y_screen is what makes residual zero on-screen.
    assert "stare-layout" in page and "stare-yscreen" in page

    # The expected angle is drawn on the gauge, not just printed as a number.
    gauge = MONITOR_JS.split("function drawTiltGauge()")[1].split("\n    }\n")[0]
    assert "stareExpectedDeg" in gauge


def test_tilt_peak_reset_also_clears_the_smoothing_window():
    """Otherwise the previous pose bleeds into the next trial's recorded peak."""
    reset = MONITOR_JS.split("function resetTiltPeaks()")[1].split("\n    }")[0]
    assert "tiltPeakDown = null" in reset
    assert "tiltPeakUp = null" in reset
    assert "tiltRawHistory = []" in reset


def test_tilt_gauge_is_drawn_after_the_overlay_is_cleared():
    """drawSilhouetteGuide clears the overlay, so an earlier gauge would be wiped."""
    guide = MONITOR_JS.split("function refreshSilhouetteGuide()")[1].split("\n    }")[0]
    assert "drawTiltGauge()" in guide
    assert guide.index("drawSilhouetteGuide(") < guide.index("drawTiltGauge()")

    gauge = MONITOR_JS.split("function drawTiltGauge()")[1].split("\n    }\n")[0]
    # Reads degrees below neutral, marks the operator's trip line and the peak.
    assert "tiltTripDeg" in gauge
    assert "tiltPeakDown" in gauge
    assert "if (tiltRawDeg == null) return" in gauge


def test_tilt_lab_ignores_synthetic_camera_modes():
    """Test pattern and silhouette have no real head, so they must not log tilt."""
    assert "updateTiltLab(usingPattern || usingSilhouette ? null : facial," in MONITOR_JS


def test_tilt_calibration_survives_a_reload():
    """Re-calibrating on every page load would make trials incomparable."""
    assert "localStorage.getItem(TILT_STORE_KEY)" in MONITOR_JS
    assert "localStorage.setItem(TILT_STORE_KEY" in MONITOR_JS
    # Stored neutrals are only comparable within one definition of raw pitch, so
    # the key is versioned and v1 (pitch = face height in frame) stays retired.
    assert "twl.tilt.calibration.v2" in MONITOR_JS
    assert "twl.tilt.calibration.v1'" not in MONITOR_JS
    page = client.get("/theodore/webcam/live-monitor/demo-session").text
    for control in ("tilt-set-neutral", "tilt-set-down", "tilt-reset-peak", "tilt-trip"):
        assert control in page, f"tilt lab control {control} missing from the page"


def test_hands_on_face_falls_back_when_face_landmarks_are_missing():
    """Hand model alone cannot score hands-on-face without face points."""
    sample = MONITOR_JS.split("const handTrack = await trackHands(")[1].split(
        "signal.keyboard_typing_audio_score"
    )[0]
    assert "lastFaceContours && lastFaceContours.pts" in sample
    assert "detectHandsOnFace(" in sample


def test_integrity_hud_does_not_confirm_phone_from_raw_ear_alone():
    hud = MONITOR_JS.split("function updateIntegrityHud(signals)")[1].split(
        "\n    }\n\n    function"
    )[0]
    assert "const confirmed = phoneBelow;" in hud
    assert "phoneEar || phoneBelow" not in hud


def test_hands_confirmation_uses_hold_ms_not_behavior_label():
    assert "handsOnFaceConfirmed: (p.hands_on_face_for_ms || 0)" in MONITOR_JS
    assert "handsOnFaceConfirmed: p.behavior_label === 'hands_on_face'" not in MONITOR_JS


def test_hands_on_face_is_not_spoken_aloud():
    """Hands-on-face is fine posture — record it, do not coach over audio."""
    assert "hand on your face" not in MONITOR_JS
    assert "maybeAnnounceIntegrity('hands'" not in MONITOR_JS
    # Still wired into the integrity HUD / evaluate payload for telemetry.
    assert "handsOnFaceConfirmed:" in MONITOR_JS
    assert "hands_on_face_for_ms" in MONITOR_JS


def test_confused_expression_override_is_removed():
    assert "expression_label = 'confused'" not in MONITOR_JS
    assert "You look a bit confused" not in MONITOR_JS


def test_class_lighting_gate_panel_is_present():
    page = client.get("/theodore/webcam/live-monitor/demo-session").text
    assert "Class lighting gate" in page
    assert "class-gate-run" in page
    assert "Simulate class gate" in page


def test_build_demo_payload_accelerates_cheating_timeline():
    first = build_demo_payload(session_id="x", step=0)
    later = build_demo_payload(session_id="x", step=5)
    b0 = next(s for s in first["signals"] if s["participant_id"] == "student-b")
    b5 = next(s for s in later["signals"] if s["participant_id"] == "student-b")
    assert b5["timestamp_ms"] - b0["timestamp_ms"] >= 45_000
    sil = next(s for s in later["signals"] if s["participant_id"] == "student-c")
    assert sil["face_count"] == 0
    assert sil["foreground_ratio"] >= 0.95


def test_vision_preset_rescores_demo_session_immediately():
    client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-preset-1", "frames": 8},
    )
    before = client.get("/api/theodore/webcam/live-metrics/ux-preset-1").json()
    before_flags = before["quality_summary"]["quality_flag_counts"]
    before_dist = {
        p["participant_id"]: p["latest"]["distance_from_camera_m"]
        for p in before["participants"]
    }

    applied = client.post("/api/theodore/vision/tuning/preset/high_accuracy")
    assert applied.status_code == 200
    body = applied.json()
    assert "ux-preset-1" in body["rescored_sessions"]
    assert body["changed_knobs"]
    assert "light_min_quality" in body["changed_knobs"]

    after = client.get("/api/theodore/webcam/live-metrics/ux-preset-1").json()
    after_flags = after["quality_summary"]["quality_flag_counts"]
    # high_accuracy raises light/sharpness floors so student-b should trip gates.
    assert after_flags.get("lighting_below_min_quality", 0) >= 1 or after_flags != before_flags

    wide = client.post("/api/theodore/vision/tuning/preset/wide_angle_laptop")
    assert wide.status_code == 200
    after_wide = client.get("/api/theodore/webcam/live-metrics/ux-preset-1").json()
    after_dist = {
        p["participant_id"]: p["latest"]["distance_from_camera_m"]
        for p in after_wide["participants"]
    }
    assert after_dist["student-a"] != before_dist["student-a"]

    client.post("/api/theodore/vision/tuning/preset/balanced")


def test_synthetic_sources_render_to_the_visible_canvas():
    """Regression: "Test pattern" drew its bars straight into the hidden 64x36
    analysis canvas and left the empty <video> showing, so the operator saw a
    black box while the gates scored a pattern nobody could see."""
    text = client.get("/theodore/webcam/live-monitor/demo-session").text
    assert "function paintTestPattern" in text
    assert "function paintSilhouettePattern" in text
    # Both synthetic modes must sample the very canvas that is shown on screen.
    assert text.count("ctx.drawImage(patternCanvas, 0, 0, GRID_W, GRID_H)") == 2
    # Harmonic bars are sized in GRID pixels so the 20x box downsample matches Sobel.
    assert "const periodPx = (w / GRID_W) * PATTERN_PERIOD_GRID;" in text
    assert "synthetic frame, no face to read" in text


def test_trajectory_and_music_hud_are_wired():
    page = client.get("/theodore/webcam/live-monitor/demo-session").text
    assert "integrity-music" in page
    assert "Outside music" in page
    assert "integrity-held" in page
    assert "Held object" in page
    assert "integrity-traj" in page
    assert "obs-exc" in page and "obs-int" in page and "obs-doz" in page
    assert "external_music_score" in MONITOR_JS
    assert "held_object_score" in MONITOR_JS
    assert "excitement_score" in MONITOR_JS
    # Music must not fire the pause toast path.
    assert "maybeToastAudio('music'" not in MONITOR_JS
    assert "outside music" in MONITOR_JS.lower() or "Outside music" in page
