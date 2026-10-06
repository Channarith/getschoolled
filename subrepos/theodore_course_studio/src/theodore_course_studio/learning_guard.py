"""Course Studio bridge to the webcam and audio-translation labs.

The webcam lab decides presence, absence, and cheating. The audio-translation
lab translates a spoken answer and lets Theodore follow up. This module turns
those decisions into a hold: the lesson does not continue while the learner is
away, sharing the camera, or answering without connecting to the page.
"""

from __future__ import annotations

import re
import sys
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
_ANALYZER: Any = None
_LAB_READY = False
_LAB_ERROR = ""
_ADAPT_NEXT: dict[str, int] = {}
_ADAPT_STEP: dict[str, int] = {}
_ADAPT_COOLDOWN_MS = 45_000

# Short, professional asides. They hand the learner back to the idea; they are
# not a second lesson.
_WAKE_LINES = (
    "I caught a yawn. I'll keep this to one idea so you can stay with it.",
    "Energy dipped. Shorter page, brighter picture. Here is the part that matters.",
    "You look ready to drift. Fair. One clean point, then we move.",
)
_REFOCUS_LINES = (
    "I lost your eyes for a moment. Let me turn this into one clear picture.",
    "Still with me? Good. I'll change the pace and put the idea up front.",
    "Attention slipped. No extra lecture. Watch this, then the point.",
)

_STOP = {
    "the", "and", "for", "that", "this", "with", "you", "your", "are", "was",
    "were", "have", "has", "had", "but", "not", "from", "they", "them", "his",
    "her", "she", "its", "our", "out", "what", "when", "where", "which", "who",
    "why", "how", "can", "could", "would", "should", "just", "like", "really",
    "very", "about", "into", "than", "then", "also", "because", "dont", "don't",
    "know", "yes", "yeah", "yep", "okay", "ok", "uh", "um", "hmm", "hello",
    "thanks", "thank", "please", "maybe", "something", "anything", "nothing",
}

_CHEAT_REASONS = {
    "phone_visible",
    "owner_face_mismatch",
    "secondary_faces_in_frame",
    "eyes_away_long",
}


def _lab_src(name: str) -> Path:
    return Path(__file__).resolve().parents[3] / name / "src"


def ensure_labs() -> None:
    """Import the sibling labs, installing their source trees if needed."""
    global _LAB_READY, _LAB_ERROR
    if _LAB_READY:
        return
    for name in ("theodore_webcam_lab", "theodore_audio_translation_lab"):
        src = _lab_src(name)
        if src.is_dir() and str(src) not in sys.path:
            sys.path.insert(0, str(src))
    try:
        import theodore_audio_translation_lab.theodore  # noqa: F401
        import theodore_webcam_lab.analysis  # noqa: F401
    except Exception as exc:  # noqa: BLE001 — surface a clear status to the page
        _LAB_ERROR = str(exc)
        raise
    _LAB_READY = True
    _LAB_ERROR = ""


def lab_status() -> dict[str, Any]:
    try:
        ensure_labs()
    except Exception as exc:  # noqa: BLE001
        return {"ready": False, "error": str(exc), "webcam": False, "audio": False}
    return {
        "ready": True,
        "error": "",
        "webcam": True,
        "audio": True,
        "features": [
            "presence",
            "absence",
            "cheating",
            "spoken_learning_check",
            "translated_reply",
            "attention_adapt",
        ],
    }


def reset_for_tests() -> None:
    global _ANALYZER
    with _LOCK:
        _ANALYZER = None
        _ADAPT_NEXT.clear()
        _ADAPT_STEP.clear()


def _analyzer() -> Any:
    global _ANALYZER
    ensure_labs()
    with _LOCK:
        if _ANALYZER is None:
            from dataclasses import replace

            from theodore_webcam_lab.analysis import AnalyzerPolicy, WebcamSessionAnalyzer
            from theodore_webcam_lab.attention_formula import AttentionFormulaTuning
            from theodore_webcam_lab.vision_tuning import VisionTuning

            # The lab's seat calibration pauses past 0.70 m and treats one quiet
            # second as "left the class". A lesson camera samples about once a
            # second, and a learner at a desk is often farther than 0.70 m.
            tuning = replace(VisionTuning(), distance_too_far_m=1.6)
            formula = replace(AttentionFormulaTuning(), max_class_distance_m=1.6)
            policy = AnalyzerPolicy(
                absence_grace_ms=2_500,
                pause_training_no_presence_ms=3_000,
            )
            _ANALYZER = WebcamSessionAnalyzer(
                policy=policy,
                tuning=tuning,
                attention_formula=formula,
            )
        return _ANALYZER


def _speech_for(reason: str, cheating: bool) -> str:
    if cheating or reason in {"owner_face_mismatch", "attention_integrity"}:
        return (
            "Pause. I need to see that you are the one learning. "
            "Look at the lesson, and put other screens and people out of the frame."
        )
    if reason in {"no_learner_detected", "absence_grace_exceeded"}:
        return (
            "I can't see you at the camera, so the lesson is paused. "
            "Come back into view and we will continue where you left off."
        )
    if reason in {"pitch_dark_needs_light", "camera_quality"}:
        return "I need a clearer picture of you. Turn on a light and face the camera."
    if reason == "too_far_from_camera":
        return "Please sit a little closer so I can tell you are here for the lesson."
    if reason == "multiple_faces":
        return (
            "I see more than one person. This lesson is for you. "
            "Ask others to step out of the camera, then look back at the page."
        )
    return "The lesson is waiting until you are present and focused."


def _attention_shift(participant: Any) -> dict[str, str] | None:
    """Choose a delivery change when the learner is fading but still here."""
    state = getattr(getattr(participant, "state", None), "value", None)
    if participant is None or state != "present":
        return None
    advanced = participant.advanced_behavior or {}
    observatory = str(advanced.get("observatory_label") or "")
    try:
        fatigue = float(advanced.get("fatigue_score") or 0)
        boredom = float(advanced.get("boredom_score") or 0)
    except (TypeError, ValueError):
        fatigue = 0.0
        boredom = 0.0
    label = str(participant.behavior_label or "")
    if (
        label in {"drowsy", "yawning"}
        or observatory == "drowsy"
        or fatigue >= 0.62
        or int(participant.yawn_for_ms or 0) >= 1_500
    ):
        return {"mode": "wake", "style": "brisk", "flow": "shorten"}
    if (
        label in {"inattentive", "distracted"}
        or observatory in {"disengaged", "distracted"}
        or boredom >= 0.58
        or int(participant.inattentive_for_ms or 0) >= 4_000
    ):
        return {"mode": "refocus", "style": "spotlight", "flow": "question"}
    return None


def _adapt_payload(session_id: str, timestamp_ms: int, shift: dict[str, str] | None) -> dict[str, Any] | None:
    if shift is None:
        return None
    key = session_id or "studio"
    with _LOCK:
        if timestamp_ms < _ADAPT_NEXT.get(key, 0):
            return None
        step = _ADAPT_STEP.get(key, 0)
        _ADAPT_STEP[key] = step + 1
        _ADAPT_NEXT[key] = timestamp_ms + _ADAPT_COOLDOWN_MS
    lines = _WAKE_LINES if shift["mode"] == "wake" else _REFOCUS_LINES
    return {
        "mode": shift["mode"],
        "style": shift["style"],
        "flow": shift["flow"],
        "speech": lines[step % len(lines)],
    }


def observe_camera(
    *,
    session_id: str,
    participant_id: str,
    timestamp_ms: int,
    signal: dict[str, Any],
) -> dict[str, Any]:
    """Run one webcam-lab frame and say whether the lesson must wait."""
    ensure_labs()
    from theodore_webcam_lab.types import ClassMode, PresenceState, WebcamSignal

    payload = {
        "participant_id": participant_id or "learner",
        "timestamp_ms": max(0, int(timestamp_ms)),
    }
    incoming = _prepare_signal(signal)
    allowed = set(WebcamSignal.model_fields)
    for key, value in incoming.items():
        if key in allowed and key not in payload and value is not None:
            payload[key] = value
    model = WebcamSignal.model_validate(payload)
    evaluation = _analyzer().evaluate(
        session_id=session_id or "studio",
        mode=ClassMode.SOLO,
        signals=[model],
        expected_participant_ids=[model.participant_id],
    )
    participant = evaluation.participants[0] if evaluation.participants else None
    reasons = list(participant.cheating_reasons) if participant else []
    alerts = list(evaluation.alerts)
    if participant:
        alerts.extend(participant.alerts)
    multiple = any("solo_mode_multiple_faces" in item for item in alerts)
    cheating = bool(participant and participant.suspected_cheating) or any(
        reason in _CHEAT_REASONS for reason in reasons
    )
    absent = bool(
        participant and participant.state is PresenceState.ABSENT
    ) or model.participant_id in evaluation.absent_participant_ids
    hold = bool(evaluation.training_paused or absent or cheating or multiple)
    reason = evaluation.pause_reason or (participant.reason if participant else "")
    if multiple and not reason:
        reason = "multiple_faces"
    if cheating and not reason:
        reason = reasons[0] if reasons else "attention_integrity"
    if absent and not reason:
        reason = "no_learner_detected"
    # Delivery stays on while the learner is fading so the picture and wording
    # keep changing. The spoken aside is paced so it does not talk over the lesson.
    shift = None if hold else _attention_shift(participant)
    adapt = _adapt_payload(session_id or "studio", model.timestamp_ms, shift)
    return {
        "hold": hold,
        "reason": reason,
        "speech": _speech_for(reason, cheating or multiple) if hold else "",
        "adapt": adapt,
        "delivery": shift,
        "state": participant.state.value if participant else "unknown",
        "training_paused": bool(evaluation.training_paused),
        "suspected_cheating": bool(cheating or multiple),
        "cheating_reasons": reasons,
        "absent": absent,
        "alerts": alerts[:8],
    }


def _content_words(text: str) -> list[str]:
    """Words in any writing system, minus fillers that do not show understanding."""
    raw = re.findall(r"[^\W\d_]{2,}", (text or "").casefold())
    return [word for word in raw if word not in _STOP]


_GAZE_FIELDS = (
    "gaze_frontal",
    "gaze_down_score",
    "gaze_up_score",
    "gaze_left_score",
    "gaze_right_score",
)


def _prepare_signal(signal: dict[str, Any]) -> dict[str, Any]:
    """Use the webcam lab's own face estimate when no real detector ran.

    A FaceDetector or face-mesh miss stays a miss. A coarse luminance frame can
    still show that someone is sitting there, without pretending it measured gaze.
    The 64×36 sample is then dropped: it is too coarse for the lab's blur gate,
    which would pause a normal lesson as a bad camera.
    """
    prepared = dict(signal)
    detector = str(prepared.get("detector_source") or "").strip().lower()
    face_count = int(prepared.get("face_count") or 0)
    grid = prepared.get("luminance_grid")
    if face_count <= 0 and detector in {"", "coarse"} and grid:
        from theodore_webcam_lab.facial_experience import estimate_from_luminance_grid

        estimate = estimate_from_luminance_grid(grid)
        if estimate is not None and estimate.face_present:
            prepared["face_count"] = 1
            prepared["detector_source"] = "coarse"
            prepared["liveness_state"] = "live"
            for key in _GAZE_FIELDS:
                prepared.pop(key, None)
            if not prepared.get("face_size_ratio") and estimate.face_size_ratio:
                prepared["face_size_ratio"] = estimate.face_size_ratio
    if detector == "face_detector":
        down = prepared.get("gaze_down_score")
        frontal = prepared.get("gaze_frontal")
        if down is None or float(down) < 0.55:
            prepared.pop("gaze_down_score", None)
        if frontal is None or float(frontal) >= 0.40:
            prepared.pop("gaze_frontal", None)
        for key in ("gaze_up_score", "gaze_left_score", "gaze_right_score"):
            value = prepared.get(key)
            if value is None or float(value) < 0.35:
                prepared.pop(key, None)
    if grid and prepared.get("mean_luminance") is None:
        flat = [float(value) for row in grid for value in row]
        if flat:
            prepared["mean_luminance"] = sum(flat) / len(flat)
    if prepared.get("light_quality_score") is None and prepared.get("mean_luminance") is not None:
        mean = float(prepared["mean_luminance"])
        prepared["light_quality_score"] = max(0.0, min(1.0, 1.0 - abs(mean - 0.45) / 0.45))
    prepared.pop("luminance_grid", None)
    return prepared


def theodore_followup(
    *,
    session_id: str,
    spoken: str,
    lesson_text: str,
    language: str,
    accepted: bool,
    reply_language: str = "",
) -> str:
    """Ask the audio-translation lab for Theodore's next spoken line."""
    ensure_labs()
    from theodore_audio_translation_lab.languages import normalize_language
    from theodore_audio_translation_lab.models import TheodoreMode
    from theodore_audio_translation_lab.theodore import TheodoreReplyEngine

    reply = normalize_language(reply_language or language or "en", "en") or "en"
    mode = TheodoreMode.TEACH if accepted else TheodoreMode.COACH
    event = TheodoreReplyEngine().reply(
        session_id=session_id or "studio",
        sequence=1,
        learner_text=spoken or lesson_text or "the lesson",
        learner_language=reply,
        reply_language=reply,
        mode=mode,
        context=(lesson_text or "")[:1200],
    )
    return (event.text or "").strip()


def _translate_to_lesson(
    spoken: str, spoken_language: str, lesson_language: str
) -> tuple[str, bool]:
    """Return the lesson-language text and whether that translation is real."""
    if not spoken or spoken_language == lesson_language:
        return spoken, True
    ensure_labs()
    from theodore_audio_translation_lab.providers import TranslationEngine

    try:
        result = TranslationEngine().translate(spoken, spoken_language, lesson_language)
    except Exception:
        return spoken, False
    if not result.translated:
        return spoken, False
    return result.text or spoken, True


def check_spoken_learning(
    *,
    session_id: str,
    lesson_text: str,
    spoken: str,
    language: str = "en",
    spoken_language: str = "",
) -> dict[str, Any]:
    """Accept a spoken answer only when it connects to the page just taught."""
    ensure_labs()
    from theodore_audio_translation_lab.languages import normalize_language

    lesson_language = normalize_language(language or "en", "en") or "en"
    heard_language = normalize_language(spoken_language or "", lesson_language) or lesson_language
    heard, translated = _translate_to_lesson(spoken.strip(), heard_language, lesson_language)
    spoken_words = _content_words(heard)
    lesson_words = set(_content_words(lesson_text))
    overlap = [word for word in spoken_words if word in lesson_words]
    if heard_language != lesson_language and not translated:
        accepted = False
        local = (
            "I could not translate that into the lesson language. "
            "Say one idea from the page in the lesson language."
        )
        overlap = []
    elif len(spoken_words) < 2:
        accepted = False
        local = (
            "Use a full sentence. Tell me one idea from the page you just heard "
            "before the lesson continues."
        )
    elif lesson_words and not overlap:
        accepted = False
        local = (
            "That answer does not connect to this page yet. "
            "Name one idea from what you just learned."
        )
    else:
        accepted = True
        local = "That connects to the lesson. We can continue."
    followup = ""
    try:
        followup = theodore_followup(
            session_id=session_id,
            spoken=heard,
            lesson_text=lesson_text,
            language=lesson_language,
            reply_language=heard_language,
            accepted=accepted,
        )
    except Exception:
        followup = ""
    return {
        "accepted": accepted,
        "speech": followup or local,
        "overlap": overlap[:6],
        "translated_text": heard,
    }
