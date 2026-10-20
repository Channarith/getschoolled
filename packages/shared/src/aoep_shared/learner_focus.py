"""Learner focus profile, attention signals, and school-style report cards.

Stored on the identity student record (Redis snapshot), not a second database.
The camera cannot see a phone, another browser tab, or a document. This module
only names a signal the current face model can actually support:

* MediaPipe face mesh (children lab, studio): pitch from the same hairline/chin
  ratio as ``theodore_webcam_lab.stare_geometry.geometric_pitch_deg`` (positive
  means down), plus debiased eye-look blendshapes for gaze. Looking at a phone
  is pitch down AND gaze down, held, because a lesson on a laptop also pitches
  the head down a little.
* Head pose only: if eye gaze blendshapes are missing, a stronger pitch can be
  recorded as ``head_pose_only``. It is not iris tracking.
* YuNet's five landmarks (web class / live room): yaw from the nose vs the eyes,
  same idea as ``aoep_shared.vision.engagement``. They do not support pitch or
  gaze, so this module will not call that a phone.
* Camera toggle or leaving the app: absence only, labeled as such.

Speech stops within a second of the learner leaving the camera. A single
dropped frame or a glance does not pause the lesson or count as cheating.
"""

from __future__ import annotations

import time
from typing import Any

AWAY_HOLD_MS = 800
RETURN_HOLD_MS = 1200
SIGNAL_HOLD_MS = 1500
# No face at all for this long still pauses, so a camera that never locks on
# does not talk forever. Shorter gaps while the model is loading do not.
BLIND_ARM_MS = 8000
PHONE_PITCH_WITH_GAZE_DEG = 18.0
PHONE_PITCH_POSE_ONLY_DEG = 28.0
GAZE_DOWN_MIN = 0.38
YAW_AWAY_DEG = 25.0
TENDENCY_REPEAT = 3

NEUTRAL_FACE_UPPER_FRACTION = 0.42
FACE_FRACTION_DEG_PER_UNIT = 250.0
GEOMETRIC_PITCH_LIMIT_DEG = 60.0

PAUSE_LINE = (
    "We detected that you left the camera. "
    "The lesson is paused and will resume when you return."
)
RESUME_LINE = "You're back on the camera. We'll continue from the same place."
PHONE_LINE = (
    "Looks like you might be looking down at a phone. "
    "The lesson is still here when you look up."
)
LOOK_AWAY_LINE = "Look back at the screen when you can. I'll keep going from here."
LEFT_LINE = (
    "We detected that you left the camera. "
    "The lesson is paused and will resume when you return."
)

IDENTITY_STATUSES = ("unverified", "pending", "verified")
DOCUMENT_TYPES = ("", "license", "passport", "school_id", "other")
# Never persist these. A reference is an opaque check id, not the document.
# A set so callers can intersect a request body. A tuple has no .intersection
# and turned every identity-check write into a 500.
REJECTED_IDENTITY_FIELDS = frozenset({
    "image",
    "image_b64",
    "photo",
    "document_number",
    "number",
    "raw",
    "license_number",
    "id_number",
})

EVENT_KINDS = (
    "looking_at_phone",
    "looking_away",
    "left_frame",
    "returned",
    "camera_on",
    "camera_off",
    "login_on_time",
    "late",
    "raise_hand",
    "unmute",
    "chat",
    "poll",
    "whiteboard",
    "breakout_unmute",
    "breakout_work",
    "screen_share",
    "screen_share_fair",
    "screen_share_hog",
    "lms_navigate",
    "file_correct",
    "file_wrong",
    "tab_hidden",
    "quiz",
    "integrity_clear",
    "identity_mismatch",
    "presentation",
    "mic_clear",
    "mic_unclear",
    "focus_period",
)

_MAX_EVENTS = 400
_MAX_INTERVALS = 80

_CATEGORIES = (
    (
        "attendance",
        "Attendance & Punctuality",
        "Digital Login & Camera Status",
        {"login_on_time", "camera_on", "returned"},
        {"late", "camera_off", "left_frame"},
    ),
    (
        "participation",
        "Class Participation",
        "Active Digital Engagement",
        {"raise_hand", "unmute", "chat", "poll", "whiteboard"},
        set(),
    ),
    (
        "collaboration",
        "Collaboration & Social Skills",
        "Breakout Room Behavior",
        {"breakout_unmute", "breakout_work", "screen_share_fair"},
        {"screen_share_hog"},
    ),
    (
        "work_habits",
        "Work Habits & Organization",
        "LMS Management & Tab Tracking",
        {"lms_navigate", "file_correct"},
        {"file_wrong", "tab_hidden"},
    ),
    (
        "assessments",
        "Tests, Quizzes & Assignments",
        "Proctored Digital Assessments",
        {"quiz", "integrity_clear"},
        {"looking_at_phone", "looking_away", "identity_mismatch"},
    ),
    (
        "presentation",
        "Projects & Presentations",
        "Digital Screen-Sharing",
        {"presentation", "mic_clear", "screen_share"},
        {"mic_unclear"},
    ),
)


def geometric_pitch_deg(upper_span: float, lower_span: float) -> float | None:
    """Pitch proxy, positive = looking down. Matches stare_geometry."""
    total = upper_span + lower_span
    if total != total or total <= 1e-6:  # NaN
        return None
    fraction = upper_span / total
    deg = (fraction - NEUTRAL_FACE_UPPER_FRACTION) * FACE_FRACTION_DEG_PER_UNIT
    return max(-GEOMETRIC_PITCH_LIMIT_DEG, min(GEOMETRIC_PITCH_LIMIT_DEG, deg))


def debiased_gaze_down(look_down: float, look_up: float) -> float:
    """Eye-look blendshape difference. Resting faces sit near 0.2–0.3 down."""
    score = (float(look_down) - float(look_up) - 0.25) / 0.5
    return max(0.0, min(1.0, score))


def empty_focus() -> dict[str, Any]:
    return {
        "identity_check": {
            "status": "unverified",
            "document_type": "",
            "reference": "",
            "updated_at": 0.0,
            "note": "No ID scan is on file. Unverified is the honest starting state.",
        },
        "preferences": {},
        "focus_periods": [],
        "events": [],
        "away_intervals": [],
        "tendencies": {
            "looking_at_phone": 0,
            "looking_away": 0,
            "left_frame": 0,
        },
    }


def _profile(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_focus()
    if not isinstance(raw, dict):
        return base
    for key in base:
        if key in raw and raw[key] is not None:
            base[key] = raw[key]
    if not isinstance(base["identity_check"], dict):
        base["identity_check"] = empty_focus()["identity_check"]
    if not isinstance(base["preferences"], dict):
        base["preferences"] = {}
    if not isinstance(base["events"], list):
        base["events"] = []
    if not isinstance(base["away_intervals"], list):
        base["away_intervals"] = []
    if not isinstance(base["focus_periods"], list):
        base["focus_periods"] = []
    if not isinstance(base["tendencies"], dict):
        base["tendencies"] = empty_focus()["tendencies"]
    return base


def _now(at: float | None) -> float:
    return float(at if at is not None else time.time())


class IdentityRejected(ValueError):
    """Caller tried to store a document image or full document number."""


def apply_identity_check(
    raw: dict[str, Any] | None,
    payload: dict[str, Any],
    *,
    at: float | None = None,
) -> dict[str, Any]:
    leaked = set(REJECTED_IDENTITY_FIELDS).intersection(payload)
    if leaked:
        raise IdentityRejected(
            "identity checks store status, document type, and a reference only"
        )
    status = str(payload.get("status") or "unverified").strip().lower()
    if status not in IDENTITY_STATUSES:
        raise ValueError("status must be unverified, pending, or verified")
    document_type = str(payload.get("document_type") or "").strip().lower()
    if document_type not in DOCUMENT_TYPES:
        raise ValueError("document_type must be license, passport, school_id, or other")
    reference = str(payload.get("reference") or "").strip()[:80]
    if status == "verified" and not reference:
        raise ValueError("verified requires a check reference, not a document number")
    # Nothing in this service reads an ID image. verified means a person
    # recorded a reference, and only when they explicitly say so.
    profile = _profile(raw)
    profile["identity_check"] = {
        "status": status,
        "document_type": document_type,
        "reference": reference,
        "updated_at": _now(at),
        "note": (
            "Verified means a check reference was recorded. "
            "No document photo or full number is stored."
            if status == "verified"
            else "Not verified from a document scan."
        ),
    }
    return profile


def apply_preferences(
    raw: dict[str, Any] | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    allowed = {
        "class_length",
        "modality",
        "materials",
        "quiz_style",
        "attention_span",
        "historical_performance",
        "notes",
    }
    profile = _profile(raw)
    prefs = dict(profile["preferences"])
    for key in allowed:
        if key not in payload or payload[key] is None:
            continue
        value = payload[key]
        if key == "historical_performance":
            try:
                prefs[key] = max(0.0, min(100.0, float(value)))
            except (TypeError, ValueError):
                continue
        else:
            prefs[key] = str(value).strip()[:240]
    profile["preferences"] = prefs
    return profile


def apply_focus_period(
    raw: dict[str, Any] | None,
    payload: dict[str, Any],
    *,
    at: float | None = None,
) -> dict[str, Any]:
    kind = str(payload.get("kind") or "").strip().lower()[:40]
    if not kind:
        raise ValueError("focus period kind is required")
    profile = _profile(raw)
    periods = list(profile["focus_periods"])
    periods.append({
        "kind": kind,
        "note": str(payload.get("note") or "").strip()[:240],
        "active": bool(payload.get("active", True)),
        "at": _now(at),
    })
    profile["focus_periods"] = periods[-40:]
    return profile


def apply_event(
    raw: dict[str, Any] | None,
    event: dict[str, Any],
    *,
    at: float | None = None,
) -> dict[str, Any]:
    kind = str(event.get("kind") or "").strip().lower()
    if kind not in EVENT_KINDS:
        raise ValueError("unknown focus event")
    profile = _profile(raw)
    evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else {}
    # Drop anything that looks like a document or an image blob.
    safe_evidence = {
        key: value
        for key, value in evidence.items()
        if key not in REJECTED_IDENTITY_FIELDS and not str(key).endswith("_b64")
    }
    row = {
        "kind": kind,
        "surface": str(event.get("surface") or "")[:40],
        "course_id": str(event.get("course_id") or "")[:80],
        "context": str(event.get("context") or "")[:40],
        "note": str(event.get("note") or "")[:240],
        "evidence": safe_evidence,
        "at": _now(at if at is not None else event.get("at")),
    }
    events = list(profile["events"])
    events.append(row)
    profile["events"] = events[-_MAX_EVENTS:]
    if kind in profile["tendencies"]:
        profile["tendencies"][kind] = int(profile["tendencies"].get(kind) or 0) + 1
    if kind == "returned":
        away_ms = safe_evidence.get("away_ms")
        try:
            away_ms_n = max(0, int(away_ms))
        except (TypeError, ValueError):
            away_ms_n = 0
        intervals = list(profile["away_intervals"])
        intervals.append({
            "away_ms": away_ms_n,
            "surface": row["surface"],
            "at": row["at"],
            "signal": str(safe_evidence.get("signal") or "")[:40],
        })
        profile["away_intervals"] = intervals[-_MAX_INTERVALS:]
    return profile


def phone_signal(
    *,
    pitch_deg: float | None,
    gaze_down: float | None,
    allow_pose_only: bool,
) -> str | None:
    """Return why this frame looks like a phone, or None.

    ``allow_pose_only`` is false for YuNet. Five-point faces do not expose a
    trustworthy pitch, and a low face box is not a phone.
    """
    if pitch_deg is None:
        return None
    pitch = float(pitch_deg)
    if gaze_down is not None:
        if pitch >= PHONE_PITCH_WITH_GAZE_DEG and float(gaze_down) >= GAZE_DOWN_MIN:
            return "pitch_and_gaze"
        return None
    if allow_pose_only and pitch >= PHONE_PITCH_POSE_ONLY_DEG:
        return "head_pose_only"
    return None


def looking_away_reason(
    *,
    yaw_deg: float | None,
    gaze_frontal: float | None,
) -> str | None:
    if yaw_deg is not None and abs(float(yaw_deg)) >= YAW_AWAY_DEG:
        return "yaw"
    if gaze_frontal is not None and float(gaze_frontal) < 0.40:
        return "gaze_frontal"
    return None


class PresenceWatch:
    """Sustained-window attention and away/back cues. One event per episode."""

    def __init__(self) -> None:
        self.phase = "unknown"
        # None means "not started". 0 is a real clock value from the first frame.
        self.away_since: int | None = None
        self.back_since: int | None = None
        self.away_started = 0
        self.phone_since: int | None = None
        self.look_since: int | None = None
        self.phone_open = False
        self.look_open = False
        self.seen_face = False
        self.started: int | None = None

    def update(self, sample: dict[str, Any]) -> list[dict[str, Any]]:
        raw_at = sample.get("at_ms")
        now = int(raw_at) if raw_at is not None else 0
        if self.started is None:
            self.started = now
        face = bool(sample.get("face_present"))
        explicit = bool(sample.get("explicit_away"))
        events: list[dict[str, Any]] = []
        if face:
            self.seen_face = True
            self.away_since = None
            if self.phase == "away":
                if self.back_since is None:
                    self.back_since = now
                if now - self.back_since >= RETURN_HOLD_MS:
                    away_ms = max(0, now - self.away_started)
                    self.phase = "here"
                    self.back_since = None
                    events.append({
                        "type": "resume",
                        "kind": "returned",
                        "line": RESUME_LINE,
                        "away_ms": away_ms,
                        "at_ms": now,
                        "signal": str(sample.get("source") or ""),
                    })
            elif self.phase == "unknown":
                self.phase = "here"
            if self.phase == "here":
                events.extend(self._attention(sample, now))
            return events

        self.back_since = None
        self.phone_since = None
        self.look_since = None
        self.phone_open = False
        self.look_open = False
        if explicit:
            if self.phase != "away":
                self.phase = "away"
                self.away_started = now
                self.away_since = now
                events.append({
                    "type": "pause",
                    "kind": "left_frame",
                    "line": PAUSE_LINE,
                    "at_ms": now,
                    "signal": str(sample.get("source") or "explicit"),
                })
            return events
        armed = self.seen_face or (now - (self.started or 0)) >= BLIND_ARM_MS
        if not armed:
            return events
        if self.away_since is None:
            self.away_since = now
        held = AWAY_HOLD_MS if self.seen_face else 0
        if self.phase != "away" and now - self.away_since >= held:
            self.phase = "away"
            self.away_started = self.away_since
            events.append({
                "type": "pause",
                "kind": "left_frame",
                "line": PAUSE_LINE,
                "notice": LEFT_LINE,
                "at_ms": now,
                "signal": str(sample.get("source") or "no_face"),
            })
        return events

    def _attention(self, sample: dict[str, Any], now: int) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        phone = phone_signal(
            pitch_deg=sample.get("pitch_deg"),
            gaze_down=sample.get("gaze_down"),
            allow_pose_only=bool(sample.get("allow_pose_only")),
        )
        if phone:
            if self.phone_since is None:
                self.phone_since = now
            if not self.phone_open and now - self.phone_since >= SIGNAL_HOLD_MS:
                self.phone_open = True
                events.append({
                    "type": "notice",
                    "kind": "looking_at_phone",
                    "line": PHONE_LINE,
                    "signal": phone,
                    "at_ms": now,
                })
        else:
            self.phone_since = None
            self.phone_open = False
        away = None if phone else looking_away_reason(
            yaw_deg=sample.get("yaw_deg"),
            gaze_frontal=sample.get("gaze_frontal"),
        )
        if away:
            if self.look_since is None:
                self.look_since = now
            if not self.look_open and now - self.look_since >= SIGNAL_HOLD_MS:
                self.look_open = True
                events.append({
                    "type": "notice",
                    "kind": "looking_away",
                    "line": LOOK_AWAY_LINE,
                    "signal": away,
                    "at_ms": now,
                })
        else:
            self.look_since = None
            self.look_open = False
        return events


def _letter(score: float | None) -> str:
    if score is None:
        return "Not enough yet"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "Needs support"


def _quiz_scores(events: list[dict[str, Any]]) -> list[float]:
    scores: list[float] = []
    for event in events:
        if event.get("kind") != "quiz":
            continue
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else {}
        try:
            scores.append(max(0.0, min(100.0, float(evidence.get("score")))))
        except (TypeError, ValueError):
            continue
    return scores


def _category_score(
    events: list[dict[str, Any]],
    positive: set[str],
    negative: set[str],
    *,
    quizzes: list[float],
) -> float | None:
    pos = sum(1 for event in events if event.get("kind") in positive)
    neg = sum(1 for event in events if event.get("kind") in negative)
    if "quiz" in positive and quizzes:
        base = round(sum(quizzes) / len(quizzes))
    elif pos or neg:
        base = 78
    else:
        return None
    score = base + pos * 4 - neg * 8
    if "quiz" in positive and quizzes and not any(
        event.get("kind") in {"camera_on", "looking_at_phone", "looking_away", "integrity_clear"}
        for event in events
    ):
        # A quiz alone is not a proctored grade. Cap it until camera or voice
        # integrity was actually observed.
        score = min(score, 86)
    return float(max(0, min(100, score)))


def _evidence_summary(events: list[dict[str, Any]], kinds: set[str]) -> str:
    counts: dict[str, int] = {}
    for event in events:
        kind = str(event.get("kind") or "")
        if kind in kinds:
            counts[kind] = counts.get(kind, 0) + 1
    if not counts:
        return "No observations in this category yet."
    parts = [f"{kind.replace('_', ' ')} {count}" for kind, count in sorted(counts.items())]
    return ", ".join(parts)


def report_card(
    raw: dict[str, Any] | None,
    *,
    context: str = "children",
    learner_name: str = "",
) -> dict[str, Any]:
    profile = _profile(raw)
    events = [event for event in profile["events"] if isinstance(event, dict)]
    ctx = "accredited" if context == "accredited" else "children"
    quizzes = _quiz_scores(events)
    categories = []
    scored: list[float] = []
    for key, title, indicator, positive, negative in _CATEGORIES:
        kinds = set(positive) | set(negative)
        score = _category_score(events, set(positive), set(negative), quizzes=quizzes)
        if score is not None:
            scored.append(score)
        summary = _evidence_summary(events, kinds)
        if key == "work_habits":
            summary += (
                " Other browser tabs are not visible to the page. "
                "Backgrounding this lesson is the signal we can record."
            )
        if key == "assessments" and quizzes and score is not None and score <= 86:
            if not any(event.get("kind") in {"camera_on", "looking_at_phone", "looking_away"} for event in events):
                summary += " Quiz scores are included. Camera integrity was not observed, so this is not a full proctored grade."
        if key == "attendance":
            intervals = profile["away_intervals"]
            if intervals:
                summary += f" Recorded {len(intervals)} return(s) from away."
        categories.append({
            "id": key,
            "category": title,
            "indicator": indicator,
            "grade": _letter(score),
            "score": None if score is None else round(score),
            "summary": summary.strip(),
        })
    overall_score = round(sum(scored) / len(scored)) if scored else None
    tendencies = profile["tendencies"]
    tendency_notes = []
    for name in ("looking_at_phone", "looking_away", "left_frame"):
        count = int(tendencies.get(name) or 0)
        if count >= TENDENCY_REPEAT:
            tendency_notes.append(f"{name.replace('_', ' ')} showed up {count} times")
    title = (
        "Accredited course report card"
        if ctx == "accredited"
        else "Children's report card"
    )
    partial = len(scored) < 3
    identity = profile["identity_check"]
    limits = [
        "No ID image or full document number is stored. "
        f"Identity status is {identity.get('status', 'unverified')}.",
        "Looking down at a phone is only recorded when head pitch and eye gaze "
        "agree, or when pitch alone is extreme and labeled head pose only. "
        "A five-point face box is not treated as a phone.",
        "Fair screen sharing, file format, and locked-browser mode are recorded "
        "only when the class page reports them. The camera cannot see them.",
        "One glance does not lock the lesson. Repeated episodes are counted on the profile.",
    ]
    summary = (
        "Not enough class activity yet to grade. Camera, voice, and coursework observations fill this in."
        if overall_score is None
        else (
            "Partial card: several categories still need camera, voice, or class activity."
            if partial
            else "Grades use camera presence, voice pauses, and class activity together, not a single quiz."
        )
    )
    if tendency_notes:
        summary += " Repeated focus notes: " + "; ".join(tendency_notes) + "."
    return {
        "context": ctx,
        "title": title,
        "learner_name": learner_name,
        "overall": {"grade": _letter(overall_score), "score": overall_score, "summary": summary},
        "categories": categories,
        "identity_check": identity,
        "preferences": profile["preferences"],
        "focus_periods": profile["focus_periods"][-12:],
        "tendencies": tendencies,
        "limits": limits,
    }
