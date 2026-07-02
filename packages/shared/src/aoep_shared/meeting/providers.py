"""Meeting backends: an offline Mock plus real Google Meet / Zoom / Teams.

Real providers call their API only when credentials are present in the
environment; otherwise they raise ``NotImplementedError`` so callers can fall
back to the Mock (the same local/cloud-by-env pattern used elsewhere in the
platform). They create/schedule the meeting; synced slide+audio playback runs
locally (share the slide window into Zoom/Meet/Teams).
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import List, Optional

from .base import Meeting, MeetingProvider, PresentationPlan, PresentationResult, PresentationStep
from .presentation_sync import SyncedSlideShow, open_meeting_url


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


class LocalPlayMeetingProvider(MockMeetingProvider):
    """Local AI presenter: synced slide deck + natural TTS.

    Opens a fullscreen slide window in the browser, advances slides in lockstep
    with neural narration (edge-tts) or enhanced macOS voices.
    """

    name = "local"
    supports_media_transport = True

    def __init__(
        self,
        *,
        speak: bool = True,
        voice: str = "",
        wpm: int = 150,
        language: str = "en",
        tts_engine: str = "auto",
        sync_slides: bool = True,
        open_slides: bool = True,
        slide_dir: Optional[str | Path] = None,
        course_title: str = "",
        course_slides: Optional[List[dict]] = None,
        plan: Optional[PresentationPlan] = None,
        open_meeting: bool = False,
        slide_source: Optional[str | Path] = None,
        tts_rate: str = "+0%",
        theme: Optional[dict] = None,
        course_dir: Optional[str | Path] = None,
        repo_root: Optional[str | Path] = None,
        voice_sample: Optional[str | Path] = None,
        elevenlabs_voice_id: str = "",
    ) -> None:
        super().__init__()
        self.speak = speak
        self.voice = voice
        self.wpm = wpm
        self.language = language
        self.tts_engine = tts_engine
        self.sync_slides = sync_slides
        self.open_slides = open_slides
        self.slide_dir = Path(slide_dir) if slide_dir else None
        self.course_title = course_title
        self.course_slides = course_slides or []
        self.plan = plan
        self.open_meeting = open_meeting
        self.slide_source = Path(slide_source) if slide_source else None
        self.tts_rate = tts_rate or "+0%"
        self.theme = theme
        self.course_dir = Path(course_dir) if course_dir else None
        self.repo_root = Path(repo_root) if repo_root else None
        self.voice_sample = Path(voice_sample) if voice_sample else None
        self.elevenlabs_voice_id = elevenlabs_voice_id or ""
        self._slideshow: Optional[SyncedSlideShow] = None
        self.slide_url = ""

    def _ensure_slideshow(self, meeting: Meeting) -> None:
        if not self.sync_slides or not self.plan or self._slideshow:
            return
        root = self.slide_dir or Path.cwd() / "output" / "harvest" / "slide_show"
        self._slideshow = SyncedSlideShow(root)
        self._slideshow.build(
            self.plan,
            title=self.course_title or meeting.topic,
            course_slides=self.course_slides,
            slide_source=self.slide_source,
            theme=self.theme,
            course_dir=self.course_dir,
            repo_root=self.repo_root,
        )
        self.slide_url = self._slideshow.start(open_browser=self.open_slides)
        if self.open_meeting:
            open_meeting_url(meeting.join_url)

    def present(self, meeting: Meeting, plan: PresentationPlan, **kwargs) -> PresentationResult:
        if self.plan is None:
            self.plan = plan
        self._ensure_slideshow(meeting)
        try:
            return super().present(meeting, plan, **kwargs)
        finally:
            if self._slideshow:
                self._slideshow.stop()
                self._slideshow = None

    def create_meeting(self, topic: str, *, start_iso: str = "",
                       duration_min: int = 30) -> Meeting:
        mid = hashlib.sha256(f"local|{topic}|{start_iso}".encode()).hexdigest()[:10]
        return Meeting(
            provider=self.name,
            meeting_id=mid,
            topic=topic,
            join_url=f"local://classroom/{mid}",
            host_url=f"local://classroom/{mid}?role=host",
            start_iso=start_iso,
            duration_min=duration_min,
            offline=True,
        )

    def _deliver_step(self, meeting: Meeting, step: PresentationStep) -> None:
        super()._deliver_step(meeting, step)
        self._ensure_slideshow(meeting)
        if self._slideshow:
            self._slideshow.show_step(step)
            print(f"\n[Slide {step.order + 1}] {step.heading}", flush=True)
            if self.slide_url:
                print(f"  Deck: {self.slide_url}", flush=True)
            return
        tag = f" [{step.action}]" if step.action != "speak" else ""
        print(f"\n{'=' * 64}", flush=True)
        print(f" SLIDE {step.order + 1}{tag}: {step.heading}", flush=True)
        print(f"{'=' * 64}", flush=True)
        if step.on_screen_points:
            for pt in step.on_screen_points[:6]:
                print(f"  • {pt}", flush=True)

    def _on_speak(self, meeting: Meeting, step: PresentationStep, spoken: str) -> None:
        if not spoken:
            return
        if self._slideshow:
            self._slideshow.show_step(step, caption=spoken)
        print(f"\nPresenter: {spoken[:120]}{'…' if len(spoken) > 120 else ''}\n", flush=True)
        if not self.speak:
            return
        from .natural_tts import speak_natural_blocking, tts_engine_status

        ok = speak_natural_blocking(
            spoken,
            language=self.language,
            voice=self.voice,
            tts_engine=self.tts_engine,
            pace_multiplier=step.pace_multiplier,
            cache_dir=(self.slide_dir or Path("output/harvest/slide_show")) / "audio",
            tts_rate=self.tts_rate,
            voice_sample=self.voice_sample,
            repo_root=self.repo_root,
            elevenlabs_voice_id=self.elevenlabs_voice_id,
        )
        if not ok:
            st = tts_engine_status()
            print(
                f"(TTS unavailable — pip install edge-tts for neural voice; "
                f"edge={st['edge_tts']} say={st['say']})\n",
                flush=True,
            )


class SyncedHybridMeetingProvider(MeetingProvider):
    """Real meeting URL + synced local slide deck and narration.

    Creates the Zoom/Meet/Teams session, opens the join link, runs the same
    synced slide+audio presenter locally. Share the slide browser window (and
    system audio) into the call.
    """

    name = "synced_hybrid"
    supports_media_transport = True

    def __init__(self, inner: MeetingProvider, **local_kw) -> None:
        self.inner = inner
        self.local_kw = local_kw
        self.name = inner.name

    def create_meeting(self, topic: str, *, start_iso: str = "",
                       duration_min: int = 30) -> Meeting:
        return self.inner.create_meeting(topic, start_iso=start_iso, duration_min=duration_min)

    def present(self, meeting: Meeting, plan: PresentationPlan, **kwargs) -> PresentationResult:
        local = LocalPlayMeetingProvider(
            open_meeting=bool(self.local_kw.pop("open_meeting", True)),
            **self.local_kw,
        )
        return local.present(meeting, plan, **kwargs)


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
