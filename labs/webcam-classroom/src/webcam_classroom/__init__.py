"""Salareen Webcam Classroom lab.

Public surface:
  * silhouette detection  -> detect_silhouette / silhouette_from_faces / SilhouetteReading
  * user-absence tracking -> AbsenceTracker / GroupPresence / AbsenceEvent
  * xAI (Grok) voice agent -> XaiVoiceAgent / build_voice_agent_session
  * pacing glue           -> ClassroomSession (solo/group x Theodore/self-teaching)
"""

from .absence import (
    ABSENT,
    BRIEFLY_ABSENT,
    LOOKING_AWAY,
    PRESENT_STATE,
    UNKNOWN,
    AbsenceConfig,
    AbsenceEvent,
    AbsenceTracker,
    GroupPresence,
)
from .config import WebcamLabConfig
from .session import (
    GROUP,
    SOLO,
    TEACHER_SELF,
    TEACHER_THEODORE,
    ClassroomSession,
    SessionUpdate,
)
from .silhouette import (
    PARTIAL,
    PRESENT,
    SilhouetteConfig,
    SilhouetteReading,
    SilhouetteUnavailable,
    detect_silhouette,
    silhouette_from_faces,
)
from .xai_voice import (
    SELF_COACH,
    THEODORE,
    ChatTurn,
    XaiVoiceAgent,
    XaiVoiceError,
    build_voice_agent_session,
)

__all__ = [
    # config
    "WebcamLabConfig",
    # silhouette
    "detect_silhouette",
    "silhouette_from_faces",
    "SilhouetteReading",
    "SilhouetteConfig",
    "SilhouetteUnavailable",
    "PRESENT",
    "PARTIAL",
    # absence
    "AbsenceTracker",
    "GroupPresence",
    "AbsenceEvent",
    "AbsenceConfig",
    "PRESENT_STATE",
    "LOOKING_AWAY",
    "BRIEFLY_ABSENT",
    "ABSENT",
    "UNKNOWN",
    # xai voice
    "XaiVoiceAgent",
    "build_voice_agent_session",
    "ChatTurn",
    "XaiVoiceError",
    "THEODORE",
    "SELF_COACH",
    # session
    "ClassroomSession",
    "SessionUpdate",
    "SOLO",
    "GROUP",
    "TEACHER_THEODORE",
    "TEACHER_SELF",
]
