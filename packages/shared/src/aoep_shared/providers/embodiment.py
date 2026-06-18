"""Embodiment providers (Phase 14).

- ScreenAvatarProvider: the default - drives the web avatar (TTS speech + display
  cues), today's "body".
- MockRobotProvider: records say/gesture calls for offline tests.
- RobotProvider: hardware humanoid (speakers + actuators + cameras); raises until
  the on-device build wires it (Phase 15).

The orchestrator maps teaching actions (narrate slide, answer, re-engage) onto
this interface, so the same brain runs on a screen or a robot.
"""

from __future__ import annotations

from typing import List, Optional

from ..config import AppConfig
from .base import EmbodimentAction, EmbodimentProvider, ProviderInfo


class ScreenAvatarProvider(EmbodimentProvider):
    impl = "screen-avatar"

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config

    def info(self) -> ProviderInfo:
        return ProviderInfo(capability=self.capability, mode="local", impl=self.impl,
                            endpoint="screen://avatar")

    def say(self, text: str, *, language: str = "en") -> EmbodimentAction:
        return EmbodimentAction("speech", {"text": text, "language": language, "tts": True})

    def gesture(self, name: str) -> EmbodimentAction:
        return EmbodimentAction("display", {"animation": name})


class MockRobotProvider(EmbodimentProvider):
    impl = "mock-robot"

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config
        self.actions: List[EmbodimentAction] = []

    def info(self) -> ProviderInfo:
        return ProviderInfo(capability=self.capability, mode="local", impl=self.impl,
                            endpoint="mock://robot")

    def say(self, text: str, *, language: str = "en") -> EmbodimentAction:
        a = EmbodimentAction("speech", {"text": text, "language": language, "actuator": "speaker"})
        self.actions.append(a)
        return a

    def gesture(self, name: str) -> EmbodimentAction:
        a = EmbodimentAction("gesture", {"motion": name, "actuator": "servo"})
        self.actions.append(a)
        return a

    def perceive(self) -> dict:
        return {"frames": [], "audio": None}


class RobotProvider(EmbodimentProvider):
    impl = "robot"

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config

    def info(self) -> ProviderInfo:
        return ProviderInfo(capability=self.capability, mode="local", impl=self.impl,
                            endpoint=getattr(self._config, "robot_endpoint", None))

    def say(self, text: str, *, language: str = "en") -> EmbodimentAction:
        raise NotImplementedError("hardware robot embodiment not wired (see Phase 15 runbook)")

    def gesture(self, name: str) -> EmbodimentAction:
        raise NotImplementedError("hardware robot embodiment not wired (see Phase 15 runbook)")


def narrate(provider: EmbodimentProvider, text: str, *, gesture: Optional[str] = None,
            language: str = "en") -> List[EmbodimentAction]:
    """Map a teaching beat (speak + optional gesture) onto the embodiment."""
    actions = [provider.say(text, language=language)]
    if gesture:
        actions.append(provider.gesture(gesture))
    return actions
