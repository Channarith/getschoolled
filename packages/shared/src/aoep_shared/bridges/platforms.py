"""Concrete platform bridges + transports.

Each :class:`MediaBridge` turns a pasted join URL into a running
:class:`BridgeSession`. The platform-agnostic orchestration lives in
``session.py``; here we only build the right vendor transport:

- Zoom (phase 7, python): wraps the Zoom Meeting/Video SDK native binding.
- Meet (phase 9, python): drives a headless Google Meet participant + Chat.
- Teams (phase 8, .NET): the media bot must run on the Graph Communications
  Calling SDK (.NET), so the Python bridge drives the .NET sidecar service over
  an HTTP control plane (see bridges/teams/).

The native SDKs / the .NET sidecar are not present in this environment, so
``_build_transport`` raises :class:`BridgeUnavailable` (fail-closed). Inject a
transport (a real one in production, a fake in tests) to run the full bridge.
"""

from __future__ import annotations

import abc
import json
import os
import urllib.request
from typing import Callable, Optional

from .meeting import MeetingRef, parse_meeting_ref
from .registry import (
    BridgeCapabilities,
    BridgePlatform,
    BridgeUnavailable,
    capabilities,
    missing_credentials,
)
from .session import (
    BridgeSession,
    Direction,
    DisclosureNotice,
    LiveKitEndpoint,
    MediaTransport,
    TrackKind,
)


class MediaBridge(abc.ABC):
    """Bridges an external meeting's media in/out of a LiveKit room."""

    def __init__(self, platform: BridgePlatform) -> None:
        self.platform = platform
        self.capabilities: BridgeCapabilities = capabilities(platform)

    @abc.abstractmethod
    def _build_transport(self, meeting: MeetingRef, room: LiveKitEndpoint) -> MediaTransport:
        """Construct the vendor transport, or raise :class:`BridgeUnavailable`."""

    def connect(
        self,
        meeting_ref: str,
        *,
        livekit_room: str,
        room_url: str = "",
        room_token: str = "",
        identity: str = "aoep-bridge",
        recording: bool = False,
        retention_days: Optional[int] = None,
        tutor_router: Optional[Callable[[str], None]] = None,
        transport: Optional[MediaTransport] = None,
    ) -> BridgeSession:
        """Join the meeting and bridge media into ``livekit_room``.

        Raises ``ValueError`` on an unparseable meeting reference and
        :class:`BridgeUnavailable` when credentials/SDK are missing (unless a
        ``transport`` is injected).
        """
        meeting = parse_meeting_ref(self.platform, meeting_ref)
        room = LiveKitEndpoint(room=livekit_room, url=room_url, token=room_token, identity=identity)
        if transport is None:
            missing = missing_credentials(self.platform)
            if missing:
                raise BridgeUnavailable(
                    f"{self.platform.value} bridge missing credentials: {', '.join(missing)}"
                )
            transport = self._build_transport(meeting, room)
        session = BridgeSession(
            capabilities=self.capabilities,
            meeting=meeting,
            room=room,
            transport=transport,
            recording=recording,
            retention_days=retention_days,
            tutor_router=tutor_router,
        )
        return session.start()


class ZoomMediaBridge(MediaBridge):
    def __init__(self) -> None:
        super().__init__(BridgePlatform.ZOOM)

    def _build_transport(self, meeting: MeetingRef, room: LiveKitEndpoint) -> MediaTransport:
        # A real deploy wires the Zoom Meeting SDK native binding here, using
        # zoom_sdk_signature(...) to authenticate. The binding is not installed
        # in this environment.
        raise BridgeUnavailable(
            "Zoom Meeting SDK (phase 7, python) not installed in this environment; "
            "install the Zoom Linux Meeting SDK binding to enable live bridging."
        )


class MeetMediaBridge(MediaBridge):
    def __init__(self) -> None:
        super().__init__(BridgePlatform.MEET)

    def _build_transport(self, meeting: MeetingRef, room: LiveKitEndpoint) -> MediaTransport:
        raise BridgeUnavailable(
            "Google Meet bridge (phase 9, python) needs a Workspace service "
            "account + the Meet automation runtime, which are not available here."
        )


class HttpSidecarTransport:
    """Drives the Teams .NET media bot over its HTTP control plane.

    The Teams bot must run on the Graph Communications Calling SDK (.NET), so the
    Python bridge cannot host the media itself. Instead it sends control commands
    (open / bridge_track / announce / chat / close) to the .NET sidecar, which
    owns the actual Teams<->LiveKit media. Uses stdlib HTTP only.
    """

    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> None:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                resp.read()
        except Exception as exc:  # noqa: BLE001 - surface as a typed bridge error
            raise BridgeUnavailable(f"Teams sidecar call {path} failed: {exc}") from exc

    def open(self, *, meeting: MeetingRef, room: LiveKitEndpoint) -> None:
        self._post("/call/join", {
            "threadId": meeting.meeting_id,
            "tenantId": meeting.tenant_id,
            "livekitUrl": room.url,
            "livekitRoom": room.room,
            "livekitToken": room.token,
        })

    def bridge_track(self, kind: TrackKind, direction: Direction) -> None:
        self._post("/call/bridge", {"kind": kind.value, "direction": direction.value})

    def announce(self, notice: DisclosureNotice) -> None:
        self._post("/call/announce", {"text": notice.text, "recording": notice.recording})

    def send_chat(self, text: str) -> None:
        self._post("/call/chat", {"text": text})

    def close(self) -> None:
        self._post("/call/leave", {})


class TeamsMediaBridge(MediaBridge):
    def __init__(self) -> None:
        super().__init__(BridgePlatform.TEAMS)

    def _build_transport(self, meeting: MeetingRef, room: LiveKitEndpoint) -> MediaTransport:
        sidecar = os.environ.get("TEAMS_BRIDGE_SIDECAR_URL", "").strip()
        if not sidecar:
            raise BridgeUnavailable(
                "Teams bridge (phase 8, .NET) needs the Graph Communications media "
                "sidecar; set TEAMS_BRIDGE_SIDECAR_URL to its control-plane URL "
                "(see bridges/teams/)."
            )
        return HttpSidecarTransport(sidecar)


_BRIDGES = {
    BridgePlatform.ZOOM: ZoomMediaBridge,
    BridgePlatform.TEAMS: TeamsMediaBridge,
    BridgePlatform.MEET: MeetMediaBridge,
}


def get_bridge(platform: BridgePlatform) -> MediaBridge:
    """Factory for the concrete platform bridge."""
    return _BRIDGES[platform]()
