"""Advanced webcam behavioral observatory.

Fuses gaze, expression, head pose, motion, audio, and integrity signals into a
rich engagement / cognitive-state snapshot plus a short timeline of behavior
events. Designed to be additive: callers without the new WebcamSignal fields
still get a useful snapshot from existing scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import WebcamSignal
from .vision_tuning import VisionTuning


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _ema(prev: float | None, value: float, alpha: float = 0.35) -> float:
    if prev is None:
        return value
    return (1.0 - alpha) * prev + alpha * value


@dataclass
class BehaviorEvent:
    timestamp_ms: int
    code: str
    level: str = "info"
    message: str = ""
    score: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "code": self.code,
            "level": self.level,
            "message": self.message,
            "score": self.score,
        }


@dataclass
class AdvancedBehaviorSnapshot:
    engagement_index: float = 0.0
    flow_score: float = 0.0
    confusion_score: float = 0.0
    boredom_score: float = 0.0
    fatigue_score: float = 0.0
    curiosity_score: float = 0.0
    fidget_score: float = 0.0
    multitask_score: float = 0.0
    excitement_score: float = 0.0
    interest_score: float = 0.0
    dozing_score: float = 0.0
    head_pose_pitch: float | None = None
    head_pose_yaw: float | None = None
    head_pose_roll: float | None = None
    head_pose_quality: float = 0.0
    cognitive_label: str = "unknown"
    observatory_label: str = "unknown"
    confidence: float = 0.0
    signals_used: list[str] = field(default_factory=list)
    events: list[BehaviorEvent] = field(default_factory=list)
    timeline_hint: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "engagement_index": round(self.engagement_index, 4),
            "flow_score": round(self.flow_score, 4),
            "confusion_score": round(self.confusion_score, 4),
            "boredom_score": round(self.boredom_score, 4),
            "fatigue_score": round(self.fatigue_score, 4),
            "curiosity_score": round(self.curiosity_score, 4),
            "fidget_score": round(self.fidget_score, 4),
            "multitask_score": round(self.multitask_score, 4),
            "excitement_score": round(self.excitement_score, 4),
            "interest_score": round(self.interest_score, 4),
            "dozing_score": round(self.dozing_score, 4),
            "head_pose_pitch": self.head_pose_pitch,
            "head_pose_yaw": self.head_pose_yaw,
            "head_pose_roll": self.head_pose_roll,
            "head_pose_quality": round(self.head_pose_quality, 4),
            "cognitive_label": self.cognitive_label,
            "observatory_label": self.observatory_label,
            "confidence": round(self.confidence, 4),
            "signals_used": list(self.signals_used),
            "events": [e.as_dict() for e in self.events],
            "timeline_hint": self.timeline_hint,
        }


@dataclass
class _ObsState:
    engagement_ema: float | None = None
    confusion_ema: float | None = None
    boredom_ema: float | None = None
    fatigue_ema: float | None = None
    fidget_ema: float | None = None
    last_motion: float | None = None
    motion_delta_ema: float | None = None
    last_label: str = "unknown"
    last_event_ms: dict[str, int] = field(default_factory=dict)
    focused_streak_ms: int = 0
    last_ts: int | None = None


class AdvancedBehaviorEngine:
    """Stateful per-participant behavioral fusion for the observatory."""

    def __init__(self) -> None:
        self._state: dict[str, dict[str, _ObsState]] = {}

    def reset_session(self, session_id: str) -> None:
        self._state.pop(session_id, None)

    def boot_participant(self, *, session_id: str, participant_id: str) -> None:
        room = self._state.get(session_id)
        if room is not None:
            room.pop(participant_id, None)

    def evaluate(
        self,
        *,
        session_id: str,
        signal: WebcamSignal,
        attention_score: float,
        distraction_score: float,
        behavior_label: str,
        eyes_away_for_ms: int,
        eyes_closed_for_ms: int,
        yawn_for_ms: int,
        inattentive_for_ms: int,
        dominant_expression: str,
        expression_confidence: float | None,
        suspected_cheating: bool,
        tuning: VisionTuning,
        phone_visible: bool | None = None,
    ) -> AdvancedBehaviorSnapshot:
        # The analyzer passes the sustained verdict; fall back to the raw frame
        # flag for callers that predate the hold window.
        if phone_visible is None:
            phone_visible = bool(signal.phone_visible)
        room = self._state.setdefault(session_id, {})
        st = room.setdefault(signal.participant_id, _ObsState())
        used: list[str] = ["attention", "distraction", "expression", "gaze"]

        pitch = signal.head_pose_pitch
        yaw = signal.head_pose_yaw
        roll = signal.head_pose_roll
        pose_quality = 0.0
        if pitch is not None or yaw is not None or roll is not None:
            used.append("head_pose")
            pose_quality = 0.85
        else:
            # Proxy head pose from gaze scores when landmarks aren't available.
            pitch = (signal.gaze_down_score or 0.0) * 35.0 - 8.0
            yaw = ((0.5 - (signal.gaze_frontal or 0.5)) * 2.0) * 28.0
            roll = 0.0
            pose_quality = 0.45 if signal.gaze_frontal is not None else 0.2
            used.append("gaze_pose_proxy")

        motion = float(signal.motion_score or 0.0)
        body = signal.body_motion_score
        if body is not None:
            motion = max(motion, float(body))
            used.append("body_motion")
        motion_delta = 0.0
        if st.last_motion is not None:
            motion_delta = abs(motion - st.last_motion)
        st.last_motion = motion
        st.motion_delta_ema = _ema(st.motion_delta_ema, motion_delta, 0.4)
        fidget = _clamp01(
            motion * 0.55
            + (st.motion_delta_ema or 0.0) * 2.2
            + (float(signal.fidget_score) if signal.fidget_score is not None else 0.0)
        )
        st.fidget_ema = _ema(st.fidget_ema, fidget, 0.3)
        fidget = st.fidget_ema or fidget

        expr = (dominant_expression or "unknown").lower()
        conf = float(expression_confidence or 0.0)
        brow = float(signal.brow_raise_score or 0.0)
        smile = float(signal.smile_score or 0.0)
        if signal.brow_raise_score is not None:
            used.append("brow_raise")
        if signal.smile_score is not None:
            used.append("smile")

        # Cognitive state heuristics (pedagogical, not clinical).
        # Confusion is not inferred from brow raise / "confused" labels — resting
        # faces vary widely and that path false-positived on ordinary neutrals.
        confusion = 0.0
        boredom = _clamp01(
            (0.50 if expr in {"neutral", "tired"} and attention_score < 0.55 else 0.0)
            + max(0.0, distraction_score - 0.35) * 0.55
            + max(0.0, (eyes_away_for_ms / 12_000.0)) * 0.4
            + (0.35 if expr == "sad" and conf >= 0.4 else 0.0)
            - smile * 0.25
            - max(0.0, attention_score - 0.6) * 0.4
        )
        fatigue = _clamp01(
            (0.55 if expr in {"tired", "yawning"} else 0.0)
            + min(1.0, yawn_for_ms / 4_000.0) * 0.7
            + min(1.0, eyes_closed_for_ms / 5_000.0) * 0.65
            + max(0.0, (pitch or 0.0) / 40.0) * 0.25
            + float(signal.dozing_score or 0.0) * 0.55
            + float(signal.head_sag_rate or 0.0) * 0.35
            - smile * 0.15
        )
        excitement = float(signal.excitement_score or 0.0)
        interest = float(signal.interest_score or 0.0)
        if signal.excitement_score is not None or signal.interest_score is not None:
            used.append("trajectory")
        curiosity = _clamp01(
            (0.45 if expr in {"surprised", "happy"} else 0.0)
            + brow * 0.35
            + max(0.0, attention_score - 0.55) * 0.5
            + smile * 0.25
            + excitement * 0.40
            + interest * 0.35
            - boredom * 0.35
            - fatigue * 0.25
        )
        flow = _clamp01(
            attention_score * 0.55
            + (1.0 - distraction_score) * 0.25
            + smile * 0.15
            + interest * 0.20
            + (0.2 if behavior_label == "focused" else 0.0)
            - fidget * 0.2
            - confusion * 0.15
            - fatigue * 0.2
        )

        st.confusion_ema = _ema(st.confusion_ema, confusion, 0.3)
        st.boredom_ema = _ema(st.boredom_ema, boredom, 0.3)
        st.fatigue_ema = _ema(st.fatigue_ema, fatigue, 0.3)
        confusion = st.confusion_ema or confusion
        boredom = st.boredom_ema or boredom
        fatigue = st.fatigue_ema or fatigue

        screen_loss = 0.0
        if signal.screen_focus_score is not None:
            screen_loss = _clamp01(1.0 - float(signal.screen_focus_score))
            used.append("screen_focus")
        multitask = _clamp01(
            (0.85 if phone_visible else 0.0)
            + float(signal.typing_activity_score or 0.0) * 0.7
            + float(signal.keyboard_typing_audio_score or 0.0) * 0.65
            + (0.45 if eyes_away_for_ms >= 2_000 and distraction_score >= 0.55 else 0.0)
            + (0.35 if suspected_cheating else 0.0)
            + screen_loss * 0.5
        )
        if phone_visible or signal.typing_activity_score or signal.keyboard_typing_audio_score:
            used.append("multitask")

        engagement = _clamp01(
            0.38 * attention_score
            + 0.18 * flow
            + 0.12 * curiosity
            + 0.08 * excitement
            + 0.08 * interest
            + 0.10 * (1.0 - boredom)
            + 0.08 * (1.0 - fatigue)
            + 0.07 * (1.0 - confusion)
            + 0.07 * (1.0 - multitask)
            - 0.12 * fidget
            - 0.10 * distraction_score
        )
        if signal.face_count <= 0:
            engagement = min(engagement, 0.08)
            used.append("absence")
        st.engagement_ema = _ema(st.engagement_ema, engagement, 0.28)
        engagement = st.engagement_ema or engagement

        # Cognitive / observatory labels (priority order).
        if signal.face_count <= 0:
            cognitive = "disengaged"
            observatory = "away"
        elif suspected_cheating or multitask >= 0.75:
            cognitive = "multitasking"
            observatory = "integrity_risk"
        elif fatigue >= 0.62 or yawn_for_ms >= 1_500 or eyes_closed_for_ms >= 1_500 or (
            float(signal.dozing_score or 0.0) >= tuning.dozing_min_threshold
        ):
            cognitive = "fatigued"
            observatory = "drowsy"
        elif boredom >= 0.58 or inattentive_for_ms >= 4_000:
            cognitive = "bored"
            observatory = "disengaged"
        elif distraction_score >= tuning.distraction_min_threshold and eyes_away_for_ms >= 2_000:
            cognitive = "distracted"
            observatory = "distracted"
        elif flow >= 0.68 and engagement >= 0.62:
            cognitive = "in_flow"
            observatory = "deeply_engaged"
        elif excitement >= tuning.excitement_min_threshold and engagement >= 0.50:
            cognitive = "curious"
            observatory = "excited"
        elif interest >= tuning.interest_min_threshold and attention_score >= tuning.attention_min_threshold:
            cognitive = "curious"
            observatory = "interested"
        elif engagement >= 0.55 and attention_score >= tuning.attention_min_threshold:
            cognitive = "engaged"
            observatory = "focused"
        elif curiosity >= 0.55:
            cognitive = "curious"
            observatory = "exploring"
        else:
            cognitive = "neutral"
            observatory = behavior_label if behavior_label != "unknown" else "monitoring"

        # Focused streak for timeline hints.
        dt = 0
        if st.last_ts is not None:
            dt = max(0, signal.timestamp_ms - st.last_ts)
        st.last_ts = signal.timestamp_ms
        if observatory in {"focused", "deeply_engaged", "exploring"}:
            st.focused_streak_ms += dt
        else:
            st.focused_streak_ms = 0

        events: list[BehaviorEvent] = []
        def _emit(code: str, level: str, message: str, score: float | None = None, cooldown_ms: int = 8_000) -> None:
            last = st.last_event_ms.get(code, -10_000_000)
            if signal.timestamp_ms - last < cooldown_ms:
                return
            st.last_event_ms[code] = signal.timestamp_ms
            events.append(
                BehaviorEvent(
                    timestamp_ms=signal.timestamp_ms,
                    code=code,
                    level=level,
                    message=message,
                    score=score,
                )
            )

        if engagement >= 0.75 and (st.last_label not in {"engaged", "in_flow"}):
            _emit("engagement_peak", "info", "High engagement detected", engagement)
        if engagement <= 0.28 and signal.face_count > 0:
            _emit("engagement_drop", "medium", "Engagement dropped sharply", engagement, 10_000)
        if boredom >= 0.62:
            _emit("boredom_rising", "low", "Boredom / zoning-out signals rising", boredom)
        if fatigue >= 0.62:
            _emit("fatigue_rising", "medium", "Fatigue / drowsiness rising", fatigue)
        if float(signal.dozing_score or 0.0) >= tuning.dozing_min_threshold:
            _emit("dozing_onset", "medium", "Head-sag / dozing trajectory", float(signal.dozing_score or 0.0))
        if excitement >= tuning.excitement_min_threshold:
            _emit("excitement_burst", "info", "Excited / animated face-hand motion", excitement)
        if interest >= tuning.interest_min_threshold:
            _emit("interest_lean", "info", "Lean-in / interest trajectory", interest, 10_000)
        if multitask >= 0.70:
            _emit("multitask_detected", "high", "Multitasking / secondary device activity", multitask)
        if fidget >= 0.70:
            _emit("restlessness", "low", "Restless / fidgeting motion", fidget)
        if abs(yaw or 0.0) >= 28.0 and pose_quality >= 0.4:
            _emit("head_turn_away", "low", "Head turned away from camera", abs(yaw or 0.0) / 45.0)
        if st.focused_streak_ms >= 20_000 and observatory in {"focused", "deeply_engaged"}:
            _emit(
                "focus_streak",
                "info",
                f"Sustained focus for {st.focused_streak_ms / 1000:.0f}s",
                engagement,
                20_000,
            )

        st.last_label = cognitive

        hint = (
            f"{observatory.replace('_', ' ')} · engagement {engagement:.0%} · "
            f"flow {flow:.0%} · fatigue {fatigue:.0%}"
        )
        confidence = _clamp01(
            0.35
            + 0.15 * pose_quality
            + 0.10 * min(1.0, len(used) / 6.0)
            + 0.20 * conf
            + 0.20 * (1.0 if signal.face_count > 0 else 0.0)
        )

        return AdvancedBehaviorSnapshot(
            engagement_index=engagement,
            flow_score=flow,
            confusion_score=confusion,
            boredom_score=boredom,
            fatigue_score=fatigue,
            curiosity_score=curiosity,
            fidget_score=fidget,
            multitask_score=multitask,
            excitement_score=excitement,
            interest_score=interest,
            dozing_score=float(signal.dozing_score or 0.0),
            head_pose_pitch=None if pitch is None else round(float(pitch), 2),
            head_pose_yaw=None if yaw is None else round(float(yaw), 2),
            head_pose_roll=None if roll is None else round(float(roll), 2),
            head_pose_quality=pose_quality,
            cognitive_label=cognitive,
            observatory_label=observatory,
            confidence=confidence,
            signals_used=sorted(set(used)),
            events=events,
            timeline_hint=hint,
        )
