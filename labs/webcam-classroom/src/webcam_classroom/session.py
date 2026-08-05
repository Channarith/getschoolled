"""ClassroomSession: turn webcam signals into class pacing + a spoken reaction.

Ties the three lab pieces together for the four combinations we care about:

  class mode:    SOLO (one learner) | GROUP (many learners)
  teacher mode:  THEODORE (AI leads the lesson) | SELF (learner self-teaches)

On each :meth:`observe` (a frame or a pre-computed silhouette reading, plus an
optional attention score), the session:
  1. runs silhouette detection (if given a frame),
  2. advances the per-learner absence state machine,
  3. decides pacing:
       - Theodore SOLO : pause the lecture while the (only) learner is absent,
                         resume when they return.
       - Theodore GROUP: hold the class while ANY learner is absent (matching the
                         orchestrator's presence-hold semantics), resume when all
                         present.
       - SELF (either) : never "pause" a lecture (there isn't one) - instead the
                         coach nudges: waits patiently on absence, welcomes back.
  4. asks the xAI voice agent for the natural spoken line for that moment
     (offline-safe fallback when no key), and returns a :class:`SessionUpdate`.

It also exposes :meth:`presence_report`, which maps a learner's current state to
the keyword arguments of the orchestrator's ``LiveRoomStore.report_presence`` so
this lab plugs straight into the existing group-class presence-hold API.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from .absence import (
    ABSENT,
    BRIEFLY_ABSENT,
    LOOKING_AWAY,
    PRESENT_STATE,
    AbsenceConfig,
    AbsenceEvent,
    AbsenceTracker,
    GroupPresence,
)
from .config import WebcamLabConfig
from .silhouette import (
    SilhouetteConfig,
    SilhouetteReading,
    detect_silhouette,
)
from .xai_voice import SELF_COACH, THEODORE, XaiVoiceAgent

# Class + teacher modes.
SOLO = "solo"
GROUP = "group"
TEACHER_THEODORE = "theodore"
TEACHER_SELF = "self"

SOLO_DEFAULT_USER = "learner"


@dataclass
class SessionUpdate:
    """What changed after one observation."""

    user_id: str
    event: Optional[AbsenceEvent]
    paused: bool
    reason: str
    spoke: bool
    spoken_text: str = ""
    reading: Optional[SilhouetteReading] = None

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "event": self.event.to_dict() if self.event else None,
            "paused": self.paused,
            "reason": self.reason,
            "spoke": self.spoke,
            "spoken_text": self.spoken_text,
            "reading": self.reading.to_dict() if self.reading else None,
        }


class ClassroomSession:
    def __init__(
        self,
        *,
        mode: str = SOLO,
        teacher: str = TEACHER_THEODORE,
        config: Optional[WebcamLabConfig] = None,
        voice_agent: Optional[XaiVoiceAgent] = None,
        user_ids: Optional[List[str]] = None,
    ) -> None:
        self.config = config or WebcamLabConfig.from_env()
        self.mode = mode if mode in (SOLO, GROUP) else SOLO
        self.teacher = teacher if teacher in (TEACHER_THEODORE, TEACHER_SELF) else TEACHER_THEODORE
        self._sil_cfg = SilhouetteConfig(
            present_coverage=self.config.present_coverage,
            partial_coverage=self.config.partial_coverage,
            foreground_delta=self.config.foreground_delta,
        )
        abs_cfg = AbsenceConfig.from_lab(self.config)
        persona = THEODORE if self.teacher == TEACHER_THEODORE else SELF_COACH
        self.voice = voice_agent or XaiVoiceAgent(self.config, persona=persona)

        if self.mode == GROUP:
            self.group = GroupPresence(config=abs_cfg)
            for uid in user_ids or []:
                self.group.tracker(uid)
            self.solo: Optional[AbsenceTracker] = None
        else:
            self.solo = AbsenceTracker(
                (user_ids or [SOLO_DEFAULT_USER])[0], abs_cfg
            )
            self.group = None  # type: ignore[assignment]

        self.paused: bool = False
        self.pause_reason: str = ""
        self.transcript: List[str] = []

    # --- observation ------------------------------------------------------- #
    def observe(
        self,
        frame_or_reading: Union[SilhouetteReading, bytes, bytearray, object, List[List[float]]],
        *,
        user_id: Optional[str] = None,
        attention: Optional[float] = None,
        now: Optional[float] = None,
        speak: bool = True,
    ) -> SessionUpdate:
        ts = now if now is not None else time.monotonic()
        reading = self._as_reading(frame_or_reading)

        if self.mode == GROUP:
            uid = user_id or SOLO_DEFAULT_USER
            event = self.group.update(uid, reading, attention=attention, now=ts)
        else:
            uid = self.solo.user_id
            event = self.solo.update(reading, attention=attention, now=ts)

        return self._react(uid, event, reading, speak=speak)

    def _as_reading(self, item) -> SilhouetteReading:
        if isinstance(item, SilhouetteReading):
            return item
        return detect_silhouette(item, self._sil_cfg)

    # --- pacing + voice ---------------------------------------------------- #
    def _react(
        self,
        uid: str,
        event: Optional[AbsenceEvent],
        reading: SilhouetteReading,
        *,
        speak: bool,
    ) -> SessionUpdate:
        prev_paused = self.paused
        self._update_pause_flag()

        spoken = ""
        did_speak = False
        context = self._context_for(uid, event)

        # Speak on meaningful transitions (absence, return, distraction) or when
        # the pause flag flips - the moments a real class would say something.
        should_voice = speak and (
            (event is not None and (event.became_absent or event.returned
                                    or event.current == LOOKING_AWAY))
            or (self.paused != prev_paused)
        )
        if should_voice and context:
            spoken = self.voice.respond(self._voice_prompt(uid, event), context=context)
            if spoken:
                did_speak = True
                self.transcript.append(spoken)

        return SessionUpdate(
            user_id=uid,
            event=event,
            paused=self.paused,
            reason=self.pause_reason,
            spoke=did_speak,
            spoken_text=spoken,
            reading=reading,
        )

    def _update_pause_flag(self) -> None:
        """Recompute whether the lecture is paused. Self-teaching never pauses."""
        if self.teacher == TEACHER_SELF:
            self.paused = False
            self.pause_reason = ""
            return
        if self.mode == GROUP:
            absent = self.group.absent_users()
            self.paused = bool(absent)
            self.pause_reason = (
                f"{len(absent)} learner(s) absent: {', '.join(absent)}" if absent else ""
            )
        else:
            self.paused = self.solo.is_absent()
            self.pause_reason = f"learner {self.solo.state}" if self.paused else ""

    def _context_for(self, uid: str, event: Optional[AbsenceEvent]) -> str:
        if event is None:
            return ""
        if event.became_absent:
            return f"learner {uid} stepped away (absent from webcam)"
        if event.returned:
            return f"learner {uid} is back / returned to the webcam"
        if event.current == LOOKING_AWAY:
            return f"learner {uid} is present but distracted / looking away"
        return ""

    def _voice_prompt(self, uid: str, event: Optional[AbsenceEvent]) -> str:
        lecturing = self.teacher == TEACHER_THEODORE
        if event and event.became_absent:
            return (
                "The learner just stepped away from the webcam. Say one short, "
                + ("kind line and note you'll pause the class." if lecturing
                   else "kind line letting them take their time.")
            )
        if event and event.returned:
            return (
                "The learner just came back. Welcome them in one short line and "
                + ("resume the class." if lecturing else "invite them to continue.")
            )
        if event and event.current == LOOKING_AWAY:
            return "The learner seems distracted. Give one short, gentle nudge to refocus."
        return "Say one short, encouraging line to keep the session going."

    # --- bridges + introspection ------------------------------------------ #
    def presence_report(self, user_id: Optional[str] = None) -> dict:
        """Map a learner's state to ``LiveRoomStore.report_presence`` kwargs.

        Lets the orchestrator's existing group-class presence-hold logic consume
        this lab's output directly (present/face_count/liveness_state/reason).
        """
        tracker = self._tracker(user_id)
        state = tracker.state
        present = state == PRESENT_STATE
        # Map our richer state onto the orchestrator's liveness vocabulary.
        if state == PRESENT_STATE:
            liveness = "live"
        elif state in (ABSENT, BRIEFLY_ABSENT):
            liveness = "absent"
        else:  # looking_away / unknown
            liveness = "unknown"
        return {
            "participant_id": tracker.user_id,
            "present": present,
            "face_count": 1 if present else 0,
            "liveness_state": liveness,
            "reason": f"webcam:{state}",
            "source": "webcam-classroom",
        }

    def realtime_voice_session(self, *, instructions: Optional[str] = None) -> dict:
        """Convenience: the xAI Realtime Voice Agent wiring for this session."""
        from .xai_voice import build_voice_agent_session

        persona = THEODORE if self.teacher == TEACHER_THEODORE else SELF_COACH
        return build_voice_agent_session(
            self.config, persona=persona, instructions=instructions
        )

    def _tracker(self, user_id: Optional[str]) -> AbsenceTracker:
        if self.mode == GROUP:
            return self.group.tracker(user_id or SOLO_DEFAULT_USER)
        return self.solo

    def state(self, now: Optional[float] = None) -> dict:
        base: Dict[str, object] = {
            "mode": self.mode,
            "teacher": self.teacher,
            "paused": self.paused,
            "pause_reason": self.pause_reason,
            "xai_configured": self.voice.configured,
            "voice_model": self.config.xai_voice_model,
        }
        if self.mode == GROUP:
            base["learners"] = self.group.snapshot(now)
            base["absent_users"] = self.group.absent_users()
        else:
            base["learner"] = self.solo.snapshot(now)
        return base
