"""Phases 7-9 - platform media bridges (scaffold behind a stable interface).

Each external platform (Zoom, Teams, Meet) is bridged into the LiveKit room the
teaching brain already runs in, so the brain is written once. The real bots need
platform SDKs and credentials that aren't available in this environment, so the
concrete connect/bridge calls raise ``BridgeUnavailable``. This module provides
the stable interface, a capability registry, and credential-readiness checks so
the rest of the system can be wired (and tested) without the SDKs.
"""

from __future__ import annotations

import abc
import enum
import os
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional


class BridgePlatform(str, enum.Enum):
    ZOOM = "zoom"
    TEAMS = "teams"
    MEET = "meet"


class BridgeUnavailable(RuntimeError):
    """Raised when a bridge is invoked without its SDK/credentials configured."""


@dataclass(frozen=True)
class BridgeCapabilities:
    platform: BridgePlatform
    phase: int
    runtime: str               # "python" | "dotnet"
    audio: bool
    video: bool
    screen_share: bool
    chat: bool
    required_credentials: tuple = field(default_factory=tuple)


# Capability registry (from docs/plan.txt). Teams is .NET-centric (Graph
# Communications); Meet additionally bridges Chat text to the Tutor.
REGISTRY: Dict[BridgePlatform, BridgeCapabilities] = {
    BridgePlatform.ZOOM: BridgeCapabilities(
        platform=BridgePlatform.ZOOM,
        phase=7,
        runtime="python",
        audio=True,
        video=True,
        screen_share=True,
        chat=True,
        required_credentials=("ZOOM_SDK_KEY", "ZOOM_SDK_SECRET"),
    ),
    BridgePlatform.TEAMS: BridgeCapabilities(
        platform=BridgePlatform.TEAMS,
        phase=8,
        runtime="dotnet",
        audio=True,
        video=True,
        screen_share=True,
        chat=True,
        required_credentials=("TEAMS_APP_ID", "TEAMS_APP_SECRET", "TEAMS_TENANT_ID"),
    ),
    BridgePlatform.MEET: BridgeCapabilities(
        platform=BridgePlatform.MEET,
        phase=9,
        runtime="python",
        audio=True,
        video=True,
        screen_share=True,
        chat=True,
        required_credentials=("GOOGLE_SA_JSON", "GOOGLE_WORKSPACE_CUSTOMER"),
    ),
}


def capabilities(platform: BridgePlatform) -> BridgeCapabilities:
    return REGISTRY[platform]


def missing_credentials(
    platform: BridgePlatform, env: Optional[Mapping[str, str]] = None
) -> List[str]:
    """Return the required credential env vars that are unset/empty."""
    source = os.environ if env is None else env
    caps = REGISTRY[platform]
    return [c for c in caps.required_credentials if not source.get(c)]


def is_ready(platform: BridgePlatform, env: Optional[Mapping[str, str]] = None) -> bool:
    return not missing_credentials(platform, env)


class MediaBridge(abc.ABC):
    """Bridges an external meeting's media in/out of a LiveKit room."""

    def __init__(self, platform: BridgePlatform) -> None:
        self.platform = platform
        self.capabilities = REGISTRY[platform]

    @abc.abstractmethod
    def connect(self, meeting_ref: str, *, livekit_room: str) -> None:
        """Join the external meeting and bridge media into ``livekit_room``."""


class _StubBridge(MediaBridge):
    """Scaffold bridge: validates readiness, then reports the SDK is needed."""

    def connect(self, meeting_ref: str, *, livekit_room: str) -> None:
        missing = missing_credentials(self.platform)
        if missing:
            raise BridgeUnavailable(
                f"{self.platform.value} bridge missing credentials: "
                f"{', '.join(missing)}"
            )
        raise BridgeUnavailable(
            f"{self.platform.value} media SDK (phase {self.capabilities.phase}, "
            f"{self.capabilities.runtime}) not installed in this environment."
        )


def get_bridge(platform: BridgePlatform) -> MediaBridge:
    """Factory for a platform bridge (returns the scaffold implementation)."""
    return _StubBridge(platform)
