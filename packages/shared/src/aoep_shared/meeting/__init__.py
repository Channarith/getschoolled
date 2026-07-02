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
from .presentation_matrix import (
    PRESENTATION_MODE_CAPACITY,
    PresentationProfile,
    decode_presentation_mode,
    encode_presentation_mode,
    list_presentation_modes,
    recommend_presentation_modes,
    resolve_mode_index,
)
from .smart_presenter import (
    build_smart_presentation_plan,
    corpus_rag_search,
    enrich_spoken_narration,
    summarize_narration,
)
from .providers import (
    GoogleMeetProvider,
    LocalPlayMeetingProvider,
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
    "build_smart_presentation_plan",
    "enrich_spoken_narration",
    "summarize_narration",
    "corpus_rag_search",
    "estimate_seconds",
    "MeetingPresenter",
    "DEFAULT_WPM",
    "MockMeetingProvider",
    "LocalPlayMeetingProvider",
    "GoogleMeetProvider",
    "ZoomProvider",
    "TeamsProvider",
    "build_meeting_provider",
    "present_with_provider",
    "PresentationProfile",
    "PRESENTATION_MODE_CAPACITY",
    "decode_presentation_mode",
    "encode_presentation_mode",
    "list_presentation_modes",
    "recommend_presentation_modes",
    "resolve_mode_index",
]
