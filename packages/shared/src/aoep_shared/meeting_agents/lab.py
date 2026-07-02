"""Offline lab: harvest → teach → bridge → multi-agent meeting simulation."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from aoep_shared.bridges import BridgePlatform, get_bridge, parse_meeting_ref
from aoep_shared.bridges.session import LiveKitEndpoint
from aoep_shared.dialect import normalize_dialect
from aoep_shared.teaching import run_end_to_end

from .agents import (
    ChatTutorAgent,
    InterruptHostAgent,
    ModeratorAgent,
    PerceptionAgent,
    SharedSessionState,
    TeacherAgent,
)
from .simulation import SimulatedMeetingTransport, VideoFrameEvent


# Sample meeting URLs for each platform (parsed offline; no network).
_SAMPLE_MEETINGS = {
    "zoom": "https://us05web.zoom.us/j/87654321012?pwd=AbC123",
    "teams": (
        "https://teams.microsoft.com/l/meetup-join/19%3ameeting_NWE4%40thread.v2/0"
        "?context=%7b%22Tid%22%3a%22tenant-abc%22%7d"
    ),
    "meet": "https://meet.google.com/abc-defg-hij",
}

_DEFAULT_CHAT_SCRIPT = [
    ("Alex", "wait what does balancing equations mean?"),
    ("Jordan", "this is a piece of cake lol"),
    ("Sam", "can you slow down?"),
]

_DEFAULT_VIDEO_SCRIPT = [
    VideoFrameEvent("student-1", attention=0.9),
    VideoFrameEvent("student-2", attention=0.35, looking_away=True),
    VideoFrameEvent("student-3", attention=0.7, hand_raised=True),
]


@dataclass
class MeetingAgentsLabResult:
    platform: str
    dialect: str
    provider_used: str
    bridge_state: str
    agent_events: List[dict]
    chat_sent: List[str]
    checks: List[tuple[str, bool]] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "dialect": self.dialect,
            "provider_used": self.provider_used,
            "bridge_state": self.bridge_state,
            "agent_events": self.agent_events,
            "chat_sent": self.chat_sent,
            "checks": [{"label": a, "ok": b} for a, b in self.checks],
            "artifacts": self.artifacts,
        }


def _check(results: List[tuple[str, bool]], label: str, ok: bool) -> None:
    results.append((label, bool(ok)))


def run_meeting_agents_lab(
    *,
    platform: str = "zoom",
    dialect: str = "us_ca",
    language: str = "en",
    subject: str = "chemistry",
    sample_text: Optional[str] = None,
    out_dir: Optional[str | Path] = None,
    chat_script: Optional[List[tuple[str, str]]] = None,
    ticks: int = 8,
) -> MeetingAgentsLabResult:
    """Run the full offline experiment and return a structured report."""
    platform = platform.lower()
    if platform not in _SAMPLE_MEETINGS:
        raise ValueError(f"platform must be one of {list(_SAMPLE_MEETINGS)}")
    dialect_id = normalize_dialect(dialect, language=language)
    checks: List[tuple[str, bool]] = []
    cleanup = out_dir is None
    if out_dir is None:
        out_dir = Path(tempfile.mkdtemp(prefix="aoep_meeting_lab_"))
    else:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

    text = sample_text or (
        "Introduction\nWelcome to group chemistry.\n\n"
        "Balancing\nBalance equations by matching atoms on both sides.\n\n"
        "Example\nH2 + O2 -> H2O needs coefficients.\n\n"
        "Summary\nPractice makes balancing second nature.\n"
    )

    # Part 1 + 2 + 3 (harvest, teach, present plan)
    e2e = run_end_to_end(
        text=text, subject=subject, out_dir=out_dir / "pipeline",
        teach_engine="fallback", meeting_provider=platform, present=True,
        dialect=dialect_id, language=language,
    )
    _check(checks, "Part1: course slides", len(e2e.course.slides) >= 3)
    _check(checks, "Part2: lesson script", len(e2e.lesson.steps) >= 3)
    _check(checks, "Part3: meeting join URL", bool(e2e.join_url))

    # Apply dialect to first segment narration for the lab
    segment = e2e.lesson.segments[0] if e2e.lesson.segments else e2e.lesson.steps[0]
    from aoep_shared.dialect import humanize_narration

    lesson_bit = humanize_narration(segment.narration, dialect_id, language=language)

    # Bridge connect (simulated transport)
    plat = BridgePlatform(platform)
    parse_meeting_ref(plat, _SAMPLE_MEETINGS[platform])  # validate the meeting ref
    room = LiveKitEndpoint(room="lab-room", url="wss://offline.local", token="lab-token")
    state = SharedSessionState(
        slides_total=len(e2e.lesson.segments) or 1,
        dialect=dialect_id,
        language=language,
        subject=subject,
        lesson_snippet=lesson_bit,
    )
    chat_tutor = ChatTutorAgent()
    teacher = TeacherAgent()
    perception = PerceptionAgent()
    interrupt = InterruptHostAgent()
    moderator = ModeratorAgent()

    bridge_holder: dict = {"session": None}

    def _handle_chat(msg) -> None:
        reply = chat_tutor.on_chat(state, msg)
        sess = bridge_holder.get("session")
        if reply and sess is not None:
            sess.post_to_chat(reply)

    transport = SimulatedMeetingTransport(
        on_inbound_chat=_handle_chat,
        on_video_frame=lambda f: perception.on_video(state, f),
    )

    bridge = get_bridge(plat)
    bridge_session = bridge.connect(
        _SAMPLE_MEETINGS[platform],
        livekit_room=room.room,
        room_url=room.url,
        room_token=room.token,
        transport=transport,
        tutor_router=lambda text: transport.inject_chat(text, author="meeting"),
    )
    bridge_holder["session"] = bridge_session

    _check(checks, "Bridge: transport opened", transport.opened)
    _check(checks, "Bridge: disclosure announced", any(c.op == "announce" for c in transport.calls))

    # Inject meeting chat + video (simulates chatbot reading the meeting)
    transport.drain_chat_script(chat_script or _DEFAULT_CHAT_SCRIPT)
    for frame in _DEFAULT_VIDEO_SCRIPT:
        transport.inject_video(frame)

    # Multi-agent tick loop
    for tick in range(ticks):
        if interrupt.tick(state, chat_tutor):
            if bridge_session:
                bridge_session.post_to_chat(state.events[-1].detail)
        elif teacher.tick(state):
            pass  # narrate to room (logged in events)
        mod = moderator.tick(state)
        if mod and bridge_session:
            bridge_session.post_to_chat(mod)
        if tick % 3 == 2 and state.slide_index < state.slides_total - 1:
            state.slide_index += 1
            if e2e.lesson.segments:
                seg = e2e.lesson.segments[min(state.slide_index, len(e2e.lesson.segments) - 1)]
                state.lesson_snippet = humanize_narration(seg.narration, dialect_id, language=language)

    if bridge_session:
        bridge_session.stop()

    _check(checks, "Agents: teacher narrated", any(e.agent == "teacher" for e in state.events))
    _check(checks, "Agents: chat tutor replied", any(e.agent == "chat_tutor" for e in state.events))
    _check(checks, "Agents: perception observed", any(e.agent == "perception" for e in state.events))
    _check(checks, "Agents: interrupt or moderator acted",
           any(e.agent in ("interrupt_host", "moderator") for e in state.events))
    _check(checks, "Bridge: chat outbound", len(transport.chat_sent) >= 1)
    intro_narration = e2e.lesson.steps[0].narration if e2e.lesson.steps else ""
    _ca_markers = ("stoked", "holler", "so like", "okay cool", "real talk", "basically")
    _check(checks, "Dialect: colloquial intro",
           dialect_id != "us_ca"
           or any(m in intro_narration.lower() for m in _ca_markers))

    report_path = out_dir / "meeting_agents_lab.json"
    result = MeetingAgentsLabResult(
        platform=platform,
        dialect=dialect_id,
        provider_used=e2e.provider_used,
        bridge_state=bridge_session.state.value if bridge_session else "unknown",
        agent_events=[{"agent": e.agent, "kind": e.kind, "detail": e.detail, "meta": e.meta}
                      for e in state.events],
        chat_sent=list(transport.chat_sent),
        checks=checks,
        artifacts=dict(e2e.artifacts),
    )
    report_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    result.artifacts["lab_report"] = str(report_path)

    if cleanup:
        pass  # caller may inspect temp dir via artifacts

    return result
