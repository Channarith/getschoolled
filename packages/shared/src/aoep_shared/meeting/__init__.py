"""Part 3 - present a generated lesson live in a video meeting.

The AI teacher joins a Google Meet / Zoom / Teams meeting and presents the
harvested+narrated course slide by slide. Real providers create the meeting via
their API (when credentials are configured); a MockMeetingProvider runs fully
offline so the whole flow is testable without accounts. The presentation
"driving" logic (advance slide -> speak narration -> next) lives in the base
provider and is shared by every backend; production media transport (streaming
audio/video into the meeting) is the per-provider extension point.
"""

from .base import (
    Meeting,
    MeetingProvider,
    PresentationEvent,
    PresentationPlan,
    PresentationResult,
    PresentationStep,
)
from .factory import build_meeting_provider, present_with_provider
from .presenter import (
    DEFAULT_WPM,
    MeetingPresenter,
    build_presentation_plan,
    estimate_seconds,
)
from .providers import (
    GoogleMeetProvider,
    MockMeetingProvider,
    TeamsProvider,
    ZoomProvider,
)

__all__ = [
    "Meeting",
    "MeetingProvider",
    "PresentationStep",
    "PresentationPlan",
    "PresentationEvent",
    "PresentationResult",
    "build_presentation_plan",
    "estimate_seconds",
    "MeetingPresenter",
    "DEFAULT_WPM",
    "MockMeetingProvider",
    "GoogleMeetProvider",
    "ZoomProvider",
    "TeamsProvider",
    "build_meeting_provider",
    "present_with_provider",
]
