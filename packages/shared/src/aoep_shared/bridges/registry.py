"""Bridge platform capability registry + credential readiness.

The registry is the single source of truth for what each external meeting
platform can bridge, which runtime its real bot is written in, and which
credentials it needs. It has no third-party dependencies, so it is fully
usable (and testable) without any platform SDK installed.
"""

from __future__ import annotations

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
