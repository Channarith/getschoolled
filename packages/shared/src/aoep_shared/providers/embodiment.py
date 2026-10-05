"""Embodiment providers (Phase 14).

- ScreenAvatarProvider: the default - drives the web avatar (TTS speech + display
  cues), today's "body".
- MockRobotProvider: records say/gesture calls for offline tests.
- RobotProvider: hardware humanoid (speakers + actuators + cameras). When
  ``robot_endpoint`` is an http(s) URL it forwards say/gesture/perceive to that
  bridge; without an endpoint it still raises until a vendor SDK is wired.

The orchestrator maps teaching actions (narrate slide, answer, re-engage) onto
this interface, so the same brain runs on a screen or a robot.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
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

    def _endpoint(self) -> str:
        return (getattr(self._config, "robot_endpoint", None) or "").strip()

    def info(self) -> ProviderInfo:
        endpoint = self._endpoint() or ""
        impl = "robot-http" if endpoint.startswith(("http://", "https://")) else self.impl
        return ProviderInfo(capability=self.capability, mode="local", impl=impl,
                            endpoint=endpoint or None)

    def _require_http(self) -> str:
        endpoint = self._endpoint()
        if endpoint.startswith(("http://", "https://")):
            return endpoint.rstrip("/")
        raise NotImplementedError(
            "hardware robot embodiment not wired (set ROBOT_ENDPOINT to an http(s) "
            "bridge or see docs/edge-robot-runbook.txt)"
        )

    def _post(self, payload: dict) -> None:
        url = self._require_http()
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"robot bridge HTTP {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"robot bridge unreachable: {exc.reason}") from exc

    def say(self, text: str, *, language: str = "en") -> EmbodimentAction:
        self._post({"action": "say", "text": text, "language": language})
        return EmbodimentAction(
            "speech",
            {"text": text, "language": language, "actuator": "speaker", "transport": "http"},
        )

    def gesture(self, name: str) -> EmbodimentAction:
        self._post({"action": "gesture", "name": name})
        return EmbodimentAction(
            "gesture",
            {"motion": name, "actuator": "servo", "transport": "http"},
        )

    def perceive(self) -> dict:
        url = self._require_http()
        req = urllib.request.Request(f"{url}/perceive", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 — bridge optional for perceive
            return {"frames": [], "audio": None}


def narrate(provider: EmbodimentProvider, text: str, *, gesture: Optional[str] = None,
            language: str = "en") -> List[EmbodimentAction]:
    """Map a teaching beat (speak + optional gesture) onto the embodiment."""
    actions = [provider.say(text, language=language)]
    if gesture:
        actions.append(provider.gesture(gesture))
    return actions
