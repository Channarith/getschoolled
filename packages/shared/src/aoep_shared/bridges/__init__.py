"""Phases 7-9 - platform media bridges (Zoom, Teams, Meet).

Each external platform is bridged into the LiveKit room the teaching brain
(apps/agent-runtime) already runs in, so the brain is written once and a thin
bridge only moves media. The platform-agnostic orchestration (join -> bridge ->
leave lifecycle, track wiring, chat->Tutor routing, recording/retention
disclosures) is implemented and tested here; the vendor-specific media plumbing
lives behind the :class:`MediaTransport` boundary.

The native SDKs / the Teams .NET sidecar are not present in this environment, so
``get_bridge(...).connect(...)`` raises :class:`BridgeUnavailable` (fail-closed)
unless a transport is injected. Inject a real transport in production or a
:class:`FakeTransport` in tests to run the full bridge end-to-end.
"""

from __future__ import annotations

from .meeting import MeetingRef, parse_meeting_ref, zoom_sdk_signature
from .platforms import (
    HttpSidecarTransport,
    MediaBridge,
    MeetMediaBridge,
    TeamsMediaBridge,
    ZoomMediaBridge,
    get_bridge,
)
from .registry import (
    REGISTRY,
    BridgeCapabilities,
    BridgePlatform,
    BridgeUnavailable,
    capabilities,
    is_ready,
    missing_credentials,
)
from .session import (
    BridgedTrack,
    BridgeSession,
    BridgeState,
    Direction,
    DisclosureNotice,
    FakeTransport,
    LiveKitEndpoint,
    MediaTransport,
    TrackKind,
    default_disclosure,
)

__all__ = [
    # registry
    "BridgePlatform",
    "BridgeCapabilities",
    "BridgeUnavailable",
    "REGISTRY",
    "capabilities",
    "missing_credentials",
    "is_ready",
    # meeting
    "MeetingRef",
    "parse_meeting_ref",
    "zoom_sdk_signature",
    # session engine
    "MediaTransport",
    "FakeTransport",
    "BridgeSession",
    "BridgeState",
    "LiveKitEndpoint",
    "DisclosureNotice",
    "BridgedTrack",
    "TrackKind",
    "Direction",
    "default_disclosure",
    # bridges
    "MediaBridge",
    "ZoomMediaBridge",
    "TeamsMediaBridge",
    "MeetMediaBridge",
    "HttpSidecarTransport",
    "get_bridge",
]
