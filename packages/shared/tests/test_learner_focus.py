"""Attention windows, identity honesty, and report-card grading."""

from __future__ import annotations

from pathlib import Path

from aoep_shared.learner_focus import (
    AWAY_HOLD_MS,
    BLIND_ARM_MS,
    GAZE_DOWN_MIN,
    PHONE_PITCH_POSE_ONLY_DEG,
    PHONE_PITCH_WITH_GAZE_DEG,
    RETURN_HOLD_MS,
    SIGNAL_HOLD_MS,
    YAW_AWAY_DEG,
    IdentityRejected,
    PresenceWatch,
    apply_event,
    apply_identity_check,
    apply_preferences,
    geometric_pitch_deg,
    phone_signal,
    report_card,
)

ROOT = Path(__file__).resolve().parents[3]


def test_pitch_is_zero_at_the_neutral_face_fraction():
    assert geometric_pitch_deg(0.42, 0.58) == 0
    assert geometric_pitch_deg(0.50, 0.50) > 10


def test_phone_needs_pitch_and_gaze_unless_pose_only_is_allowed():
    assert phone_signal(pitch_deg=20, gaze_down=0.5, allow_pose_only=True) == "pitch_and_gaze"
    assert phone_signal(pitch_deg=20, gaze_down=0.1, allow_pose_only=True) is None
    assert phone_signal(pitch_deg=20, gaze_down=None, allow_pose_only=True) is None
    assert phone_signal(pitch_deg=32, gaze_down=None, allow_pose_only=True) == "head_pose_only"
    # YuNet five-point faces must not be called a phone.
    assert phone_signal(pitch_deg=40, gaze_down=None, allow_pose_only=False) is None
    assert phone_signal(pitch_deg=None, gaze_down=0.9, allow_pose_only=True) is None


def test_away_and_phone_wait_for_a_sustained_window():
    watch = PresenceWatch()
    face = {
        "face_present": True,
        "pitch_deg": 22,
        "gaze_down": 0.6,
        "yaw_deg": 0,
        "allow_pose_only": True,
        "source": "face_mesh",
    }
    assert watch.update({**face, "at_ms": 0}) == []
    assert watch.update({**face, "at_ms": SIGNAL_HOLD_MS - 1}) == []
    noticed = watch.update({**face, "at_ms": SIGNAL_HOLD_MS})
    assert noticed[0]["kind"] == "looking_at_phone"
    assert noticed[0]["signal"] == "pitch_and_gaze"
    assert watch.update({**face, "at_ms": SIGNAL_HOLD_MS + 400}) == []

    gone = {"face_present": False, "source": "face_mesh"}
    assert watch.update({**gone, "at_ms": 5000}) == []
    paused = watch.update({**gone, "at_ms": 5000 + AWAY_HOLD_MS})
    assert paused[0]["type"] == "pause"
    assert watch.update({**gone, "at_ms": 9000}) == []

    back = {**face, "pitch_deg": 2, "gaze_down": 0.0}
    assert watch.update({**back, "at_ms": 10000}) == []
    resumed = watch.update({**back, "at_ms": 10000 + RETURN_HOLD_MS})
    assert resumed[0]["type"] == "resume"
    assert resumed[0]["away_ms"] >= AWAY_HOLD_MS


def test_a_blind_camera_does_not_pause_on_the_first_frames():
    watch = PresenceWatch()
    assert watch.update({"face_present": False, "at_ms": 0, "source": "yunet"}) == []
    assert watch.update({"face_present": False, "at_ms": 3000, "source": "yunet"}) == []
    paused = watch.update({"face_present": False, "at_ms": BLIND_ARM_MS, "source": "yunet"})
    assert paused[0]["type"] == "pause"
    assert paused[0]["signal"] == "yunet"


def test_explicit_away_pauses_immediately_and_yunet_yaw_can_look_away():
    watch = PresenceWatch()
    paused = watch.update({
        "face_present": False,
        "explicit_away": True,
        "at_ms": 10,
        "source": "app_background",
    })
    assert paused[0]["signal"] == "app_background"

    watch = PresenceWatch()
    sample = {
        "face_present": True,
        "pitch_deg": None,
        "gaze_down": None,
        "yaw_deg": YAW_AWAY_DEG + 2,
        "gaze_frontal": 0.9,
        "allow_pose_only": False,
        "source": "yunet",
    }
    assert watch.update({**sample, "at_ms": 0}) == []
    noticed = watch.update({**sample, "at_ms": SIGNAL_HOLD_MS})
    assert noticed[0]["kind"] == "looking_away"
    assert noticed[0]["signal"] == "yaw"


def test_identity_check_rejects_documents_and_does_not_self_verify():
    try:
        apply_identity_check({}, {"status": "verified", "document_number": "D1234567"})
        raise AssertionError("document number should be rejected")
    except IdentityRejected:
        pass
    try:
        apply_identity_check({}, {"status": "verified", "image_b64": "aaaa"})
        raise AssertionError("image should be rejected")
    except IdentityRejected:
        pass
    try:
        apply_identity_check({}, {"status": "verified"})
        raise AssertionError("verified without a reference should fail")
    except ValueError:
        pass
    pending = apply_identity_check({}, {"status": "pending", "document_type": "license", "reference": "chk-1"})
    assert pending["identity_check"]["status"] == "pending"
    assert "document_number" not in pending["identity_check"]
    verified = apply_identity_check(pending, {
        "status": "verified",
        "document_type": "license",
        "reference": "chk-1",
    })
    assert verified["identity_check"]["status"] == "verified"
    assert "image" not in str(verified["identity_check"])


def test_report_card_is_not_a_single_quiz_and_names_its_limits():
    profile = apply_preferences({}, {
        "class_length": "short",
        "modality": "video",
        "materials": "games",
        "quiz_style": "intermixed",
        "attention_span": "short",
    })
    profile = apply_event(profile, {
        "kind": "quiz",
        "surface": "class",
        "context": "accredited",
        "evidence": {"score": 100},
    })
    card = report_card(profile, context="accredited", learner_name="Ava")
    assessments = next(row for row in card["categories"] if row["id"] == "assessments")
    attendance = next(row for row in card["categories"] if row["id"] == "attendance")
    assert assessments["grade"] in {"A", "B"}
    assert assessments["score"] is not None and assessments["score"] <= 86
    assert attendance["grade"] == "Not enough yet"
    assert card["overall"]["summary"].lower().startswith("partial")
    assert any("ID image" in line for line in card["limits"])
    assert card["preferences"]["materials"] == "games"

    fuller = profile
    for kind in ("camera_on", "raise_hand", "chat", "breakout_unmute", "screen_share", "presentation", "mic_clear"):
        fuller = apply_event(fuller, {"kind": kind, "surface": "live_room", "context": "children"})
    fuller = apply_event(fuller, {
        "kind": "looking_at_phone",
        "surface": "children_lab",
        "evidence": {"signal": "pitch_and_gaze"},
    })
    fuller = apply_event(fuller, {
        "kind": "returned",
        "surface": "class",
        "evidence": {"away_ms": 4000, "signal": "no_face"},
    })
    graded = report_card(fuller, context="children", learner_name="Ava")
    assert graded["title"].startswith("Children")
    assert graded["overall"]["grade"] != "Not enough yet"
    assert "not a single quiz" in graded["overall"]["summary"]
    phone_count = graded["tendencies"]["looking_at_phone"]
    assert phone_count == 1


def test_client_thresholds_match_the_children_lab_and_web_helper():
    js = (ROOT / "subrepos/theodore_children_webcam_lab/src/theodore_children_webcam_lab/static/vision_math.js").read_text()
    ts = (ROOT / "apps/web/app/lib/learnerFocus.ts").read_text()
    mobile = (ROOT / "apps/mobile/src/learnerFocus.ts").read_text()
    needles = [
        f"AWAY_HOLD_MS = {AWAY_HOLD_MS}",
        f"RETURN_HOLD_MS = {RETURN_HOLD_MS}",
        f"SIGNAL_HOLD_MS = {SIGNAL_HOLD_MS}",
        f"PHONE_PITCH_WITH_GAZE_DEG = {int(PHONE_PITCH_WITH_GAZE_DEG)}",
        f"PHONE_PITCH_POSE_ONLY_DEG = {int(PHONE_PITCH_POSE_ONLY_DEG)}",
        f"GAZE_DOWN_MIN = {GAZE_DOWN_MIN}",
        f"YAW_AWAY_DEG = {int(YAW_AWAY_DEG)}",
    ]
    for needle in needles:
        assert needle in js, needle
        assert needle in ts, needle
        assert needle in mobile, needle
