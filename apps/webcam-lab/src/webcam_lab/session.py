"""Webcam lab session store — solo / group / self-teach teaching modes."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from aoep_shared.vision.absence import (
    AbsenceDecision,
    AbsencePolicy,
    AbsenceTracker,
    FramePresenceInput,
)
from aoep_shared.vision.silhouette_signals import SilhouetteSignals, silhouette_from_counts
from aoep_shared.xai_realtime import VoiceSessionConfig, build_voice_session

MODE_SOLO = "solo"
MODE_GROUP = "group"
MODE_SELF_TEACH = "self_teach"
VALID_MODES = (MODE_SOLO, MODE_GROUP, MODE_SELF_TEACH)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class LabParticipant:
    participant_id: str
    display_name: str
    role: str = "learner"  # learner | host | self
    tracker: AbsenceTracker = field(default_factory=lambda: AbsenceTracker("pending"))
    last_decision: Optional[AbsenceDecision] = None

    def __post_init__(self) -> None:
        if self.tracker.participant_id == "pending":
            self.tracker = AbsenceTracker(self.participant_id)


@dataclass
class LabSession:
    session_id: str
    mode: str
    title: str
    lesson_context: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    participants: Dict[str, LabParticipant] = field(default_factory=dict)
    voice_config: Optional[VoiceSessionConfig] = None
    hold: bool = False
    status: str = "active"  # active | held | closed

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "title": self.title,
            "lesson_context": self.lesson_context,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "hold": self.hold,
            "participant_count": len(self.participants),
            "participants": [
                {
                    "participant_id": p.participant_id,
                    "display_name": p.display_name,
                    "role": p.role,
                    "presence": None
                    if p.last_decision is None
                    else {
                        "state": p.last_decision.state,
                        "present": p.last_decision.present,
                        "hold": p.last_decision.hold,
                        "face_count": p.last_decision.face_count,
                        "silhouette_present": p.last_decision.silhouette_present,
                        "attention": p.last_decision.attention,
                        "absent_for_seconds": p.last_decision.absent_for_seconds,
                        "reason": p.last_decision.reason,
                        "should_reengage": p.last_decision.should_reengage,
                    },
                }
                for p in self.participants.values()
            ],
            "voice": None
            if self.voice_config is None
            else {
                "persona": self.voice_config.persona,
                "voice": self.voice_config.voice,
                "model": self.voice_config.model,
                "session_update": self.voice_config.session_update_event(),
            },
        }


class LabSessionStore:
    """Thread-safe in-memory store for the private webcam lab."""

    def __init__(self, *, absence_policy: Optional[AbsencePolicy] = None) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, LabSession] = {}
        self._policy = absence_policy or AbsencePolicy(grace_seconds=8.0, stale_seconds=20.0)

    def create(
        self,
        mode: str,
        *,
        title: str = "",
        lesson_context: str = "",
        host_name: str = "Learner",
        learner_names: Optional[List[str]] = None,
        voice_id: str = "eve",
        voice_model: str = "grok-voice-latest",
    ) -> LabSession:
        mode_key = (mode or MODE_SOLO).strip().lower().replace("-", "_")
        if mode_key not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
        sid = f"wlab-{uuid.uuid4().hex[:12]}"
        names = list(learner_names or [])
        voice = build_voice_session(
            mode_key,
            voice=voice_id,
            model=voice_model,
            lesson_context=lesson_context,
            learner_names=names or [host_name],
        )
        # Enable presence tool so Grok can ask about webcam state.
        from aoep_shared.xai_realtime import presence_tool_schema

        voice.tools = [presence_tool_schema()]

        session = LabSession(
            session_id=sid,
            mode=mode_key,
            title=title or f"{mode_key} webcam lab",
            lesson_context=lesson_context,
            voice_config=voice,
        )
        # Seed the primary participant.
        role = "self" if mode_key == MODE_SELF_TEACH else "learner"
        primary = LabParticipant(
            participant_id=f"p-{uuid.uuid4().hex[:8]}",
            display_name=host_name or "Learner",
            role=role,
            tracker=AbsenceTracker(f"p-pending", policy=self._policy),
        )
        primary.tracker = AbsenceTracker(primary.participant_id, policy=self._policy)
        session.participants[primary.participant_id] = primary

        for name in names:
            if name.strip() and name.strip() != host_name:
                pid = f"p-{uuid.uuid4().hex[:8]}"
                session.participants[pid] = LabParticipant(
                    participant_id=pid,
                    display_name=name.strip(),
                    role="learner",
                    tracker=AbsenceTracker(pid, policy=self._policy),
                )

        with self._lock:
            self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Optional[LabSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> List[LabSession]:
        with self._lock:
            return list(self._sessions.values())

    def add_participant(
        self, session_id: str, display_name: str, *, role: str = "learner"
    ) -> LabParticipant:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            if session.mode == MODE_SOLO and len(session.participants) >= 1:
                raise ValueError("solo sessions allow only one learner")
            if session.mode == MODE_GROUP and len(session.participants) >= 8:
                raise ValueError("group lab capped at 8 learners")
            pid = f"p-{uuid.uuid4().hex[:8]}"
            part = LabParticipant(
                participant_id=pid,
                display_name=display_name.strip() or "Learner",
                role=role,
                tracker=AbsenceTracker(pid, policy=self._policy),
            )
            session.participants[pid] = part
            return part

    def report_presence(
        self,
        session_id: str,
        participant_id: str,
        *,
        face_count: int = 0,
        attention: float = 0.0,
        silhouette_present: Optional[bool] = None,
        silhouette_confidence: float = 0.8,
        silhouette: Optional[SilhouetteSignals] = None,
        liveness_ok: bool = True,
        reason: str = "",
        now: Optional[datetime] = None,
    ) -> AbsenceDecision:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            part = session.participants.get(participant_id)
            if part is None:
                raise KeyError(participant_id)

            sil = silhouette
            if sil is None and silhouette_present is not None:
                if silhouette_present:
                    sil = silhouette_from_counts(
                        person_count=1, confidence=silhouette_confidence
                    )
                else:
                    sil = silhouette_from_counts(person_count=0)

            decision = part.tracker.update(
                FramePresenceInput(
                    face_count=face_count,
                    attention=attention,
                    silhouette=sil,
                    liveness_ok=liveness_ok,
                    reason=reason,
                ),
                now=now,
            )
            part.last_decision = decision
            # Room-level hold if any learner is on hold (group) or the only
            # learner is on hold (solo / self-teach).
            session.hold = any(
                (p.last_decision is not None and p.last_decision.hold)
                for p in session.participants.values()
            )
            session.status = "held" if session.hold else "active"
            return decision

    def presence_snapshot(self, session_id: str, participant_id: str) -> dict:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            part = session.participants.get(participant_id)
            if part is None:
                raise KeyError(participant_id)
            d = part.last_decision
            return {
                "participant_id": participant_id,
                "display_name": part.display_name,
                "state": d.state if d else "unknown",
                "present": bool(d and d.present),
                "hold": bool(d and d.hold),
                "attention": d.attention if d else 0.0,
                "face_count": d.face_count if d else 0,
                "silhouette_present": bool(d and d.silhouette_present),
                "reason": d.reason if d else "no_signal",
                "should_reengage": bool(d and d.should_reengage),
                "observed_at": time.time(),
            }

    def close(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            session.status = "closed"
