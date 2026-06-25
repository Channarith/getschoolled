"""Meeting backends: an offline Mock plus real Google Meet / Zoom / Teams.

Real providers call their API only when credentials are present in the
environment; otherwise they raise ``NotImplementedError`` so callers can fall
back to the Mock (the same local/cloud-by-env pattern used elsewhere in the
platform). They create/schedule the meeting; streaming the AI's audio+slides
into the live meeting is a media-bot transport handled by ``_deliver_step`` in a
production deployment (documented; not exercised offline).
"""

from __future__ import annotations

import hashlib
import os
import uuid
from typing import Optional

from .base import Meeting, MeetingProvider, PresentationStep


# --------------------------------------------------------------------------- #
# Mock (offline, deterministic) - used in tests/CI and key-less demos
# --------------------------------------------------------------------------- #
class MockMeetingProvider(MeetingProvider):
    name = "mock"
    supports_media_transport = True   # simulated transport (records a log)

    def __init__(self) -> None:
        self.delivered: list[int] = []

    def create_meeting(self, topic: str, *, start_iso: str = "",
                       duration_min: int = 30) -> Meeting:
        mid = hashlib.sha256(f"{topic}|{start_iso}".encode()).hexdigest()[:10]
        return Meeting(
            provider=self.name,
            meeting_id=mid,
            topic=topic,
            join_url=f"https://meet.local/mock/{mid}",
            host_url=f"https://meet.local/mock/{mid}?role=host",
            start_iso=start_iso,
            duration_min=duration_min,
            offline=True,
        )

    def _deliver_step(self, meeting: Meeting, step: PresentationStep) -> None:
        # Simulated transport: just record which slides were "streamed".
        self.delivered.append(step.order)


# --------------------------------------------------------------------------- #
# Real providers
# --------------------------------------------------------------------------- #
class GoogleMeetProvider(MeetingProvider):
    """Create a Google Meet via a Calendar event with conferenceData.

    Needs an OAuth access token with Calendar scope in ``GOOGLE_ACCESS_TOKEN``
    (or ``GOOGLE_MEET_ACCESS_TOKEN``). Calendar id defaults to ``primary``.
    """

    name = "google_meet"

    def __init__(self, access_token: Optional[str] = None,
                 calendar_id: Optional[str] = None) -> None:
        self.access_token = access_token or os.environ.get(
            "GOOGLE_MEET_ACCESS_TOKEN") or os.environ.get("GOOGLE_ACCESS_TOKEN")
        self.calendar_id = calendar_id or os.environ.get("GOOGLE_CALENDAR_ID", "primary")

    def create_meeting(self, topic: str, *, start_iso: str = "",
                       duration_min: int = 30) -> Meeting:
        if not self.access_token:
            raise NotImplementedError(
                "GoogleMeetProvider needs GOOGLE_ACCESS_TOKEN (Calendar scope)")
        import datetime as _dt

        import requests  # lazy

        start = start_iso or _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        try:
            start_dt = _dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            start_dt = _dt.datetime.utcnow()
        end_dt = start_dt + _dt.timedelta(minutes=duration_min)
        body = {
            "summary": topic,
            "start": {"dateTime": start_dt.isoformat()},
            "end": {"dateTime": end_dt.isoformat()},
            "conferenceData": {"createRequest": {
                "requestId": uuid.uuid4().hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"}}},
        }
        url = (f"https://www.googleapis.com/calendar/v3/calendars/"
               f"{self.calendar_id}/events?conferenceDataVersion=1")
        resp = requests.post(url, json=body, timeout=20,
                             headers={"Authorization": f"Bearer {self.access_token}"})
        if resp.status_code >= 300:
            raise RuntimeError(f"Google Calendar error {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        join = data.get("hangoutLink") or _entry_point(data)
        return Meeting(provider=self.name, meeting_id=data.get("id", ""), topic=topic,
                       join_url=join, host_url=data.get("htmlLink", ""),
                       start_iso=start, duration_min=duration_min, raw=data)


class ZoomProvider(MeetingProvider):
    """Create a Zoom meeting via server-to-server OAuth.

    Needs ``ZOOM_ACCOUNT_ID``, ``ZOOM_CLIENT_ID``, ``ZOOM_CLIENT_SECRET``.
    """

    name = "zoom"

    def __init__(self) -> None:
        self.account_id = os.environ.get("ZOOM_ACCOUNT_ID")
        self.client_id = os.environ.get("ZOOM_CLIENT_ID")
        self.client_secret = os.environ.get("ZOOM_CLIENT_SECRET")

    def _token(self) -> str:
        import requests  # lazy

        resp = requests.post(
            "https://zoom.us/oauth/token", timeout=20,
            params={"grant_type": "account_credentials", "account_id": self.account_id},
            auth=(self.client_id, self.client_secret))
        if resp.status_code >= 300:
            raise RuntimeError(f"Zoom OAuth error {resp.status_code}: {resp.text[:200]}")
        return resp.json()["access_token"]

    def create_meeting(self, topic: str, *, start_iso: str = "",
                       duration_min: int = 30) -> Meeting:
        if not (self.account_id and self.client_id and self.client_secret):
            raise NotImplementedError(
                "ZoomProvider needs ZOOM_ACCOUNT_ID/ZOOM_CLIENT_ID/ZOOM_CLIENT_SECRET")
        import requests  # lazy

        body = {"topic": topic, "type": 2 if start_iso else 1,
                "duration": duration_min, "start_time": start_iso or None}
        resp = requests.post(
            "https://api.zoom.us/v2/users/me/meetings", json=body, timeout=20,
            headers={"Authorization": f"Bearer {self._token()}"})
        if resp.status_code >= 300:
            raise RuntimeError(f"Zoom create error {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return Meeting(provider=self.name, meeting_id=str(data.get("id", "")), topic=topic,
                       join_url=data.get("join_url", ""), host_url=data.get("start_url", ""),
                       start_iso=start_iso, duration_min=duration_min, raw=data)


class TeamsProvider(MeetingProvider):
    """Create a Microsoft Teams meeting via Graph ``onlineMeetings``.

    Needs a Graph access token in ``TEAMS_ACCESS_TOKEN`` (or ``GRAPH_ACCESS_TOKEN``)
    with ``OnlineMeetings.ReadWrite`` scope.
    """

    name = "teams"

    def __init__(self, access_token: Optional[str] = None) -> None:
        self.access_token = access_token or os.environ.get(
            "TEAMS_ACCESS_TOKEN") or os.environ.get("GRAPH_ACCESS_TOKEN")

    def create_meeting(self, topic: str, *, start_iso: str = "",
                       duration_min: int = 30) -> Meeting:
        if not self.access_token:
            raise NotImplementedError("TeamsProvider needs TEAMS_ACCESS_TOKEN (Graph)")
        import datetime as _dt

        import requests  # lazy

        start = start_iso or _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        try:
            start_dt = _dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            start_dt = _dt.datetime.utcnow()
        end_dt = start_dt + _dt.timedelta(minutes=duration_min)
        body = {"subject": topic, "startDateTime": start_dt.isoformat(),
                "endDateTime": end_dt.isoformat()}
        resp = requests.post(
            "https://graph.microsoft.com/v1.0/me/onlineMeetings", json=body, timeout=20,
            headers={"Authorization": f"Bearer {self.access_token}"})
        if resp.status_code >= 300:
            raise RuntimeError(f"Graph error {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return Meeting(provider=self.name, meeting_id=data.get("id", ""), topic=topic,
                       join_url=data.get("joinWebUrl", ""), start_iso=start,
                       duration_min=duration_min, raw=data)


def _entry_point(event: dict) -> str:
    for ep in event.get("conferenceData", {}).get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            return ep.get("uri", "")
    return ""
