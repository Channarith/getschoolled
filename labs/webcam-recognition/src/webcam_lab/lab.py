"""End-to-end offline webcam recognition lab harness."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import List, Optional

from .frames import absent_learner, body_only_learner, face_only_learner, present_learner
from .presence import AbsencePolicy
from .session import ClassMode, ClassSession, RoomSize
from .teaching import TeachingMode
from .xai_voice import MockXaiVoiceAgent, XaiVoiceConfig


@dataclass
class WebcamLabResult:
    class_mode: str
    teaching_mode: str
    room_size: int
    ticks: List[dict] = field(default_factory=list)
    voice_events: List[dict] = field(default_factory=list)
    checks: List[tuple] = field(default_factory=list)
    presence_hold_seen: bool = False
    session: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "class_mode": self.class_mode,
            "teaching_mode": self.teaching_mode,
            "room_size": self.room_size,
            "ticks": self.ticks,
            "voice_events": self.voice_events,
            "checks": [{"label": a, "ok": b} for a, b in self.checks],
            "presence_hold_seen": self.presence_hold_seen,
            "session": self.session,
        }


def _check(results: List[tuple], label: str, ok: bool) -> None:
    results.append((label, bool(ok)))


def run_webcam_lab(
    *,
    class_mode: str = "solo",
    teaching_mode: str = "theodore_teach",
    room_size: int = 2,
    grace_seconds: float = 3.0,
) -> WebcamLabResult:
    """Simulate a short class: present → absent (hold) → return → teach/ask.

    Always offline. Uses MockXaiVoiceAgent for Theodore speech cues.
    """
    cmode = ClassMode.SOLO if class_mode == "solo" else ClassMode.GROUP
    tmode = (
        TeachingMode.SELF_TEACH
        if teaching_mode == "self_teach"
        else TeachingMode.THEODORE_TEACH
    )
    try:
        rsize = RoomSize(int(room_size))
    except ValueError:
        rsize = RoomSize.SOLO if cmode is ClassMode.SOLO else RoomSize.SMALL

    policy = AbsencePolicy(grace_seconds=grace_seconds)
    session = ClassSession.open(
        room_id=f"lab-{cmode.value}-{tmode.value}",
        class_mode=cmode,
        room_size=rsize,
        teaching_mode=tmode,
        learner_names=["Alex", "Jordan", "Sam", "Riley", "Casey", "Morgan", "Quinn", "Avery"],
        policy=policy,
    )
    session.slide_title = "Webcam presence & natural dialogue"

    voice = MockXaiVoiceAgent(
        XaiVoiceConfig(
            instructions=(
                "You are Theodore, Salareen's AI host. Be brief and natural."
            )
        )
    )
    voice.connect()

    result = WebcamLabResult(
        class_mode=cmode.value,
        teaching_mode=tmode.value,
        room_size=int(session.room_size),
    )
    seat = "seat-1"

    # 1) Learner present (face + silhouette)
    tick = session.tick(seat, present_learner(), dt=1.0)
    if tick["turn"].get("use_voice_agent"):
        voice.speak(tick["turn"]["line"])
    result.ticks.append(tick)

    # 2) Body-only still counts as present under default policy
    tick = session.tick(seat, body_only_learner(), dt=1.0)
    result.ticks.append(tick)

    # 3) Face-only still counts as present
    tick = session.tick(seat, face_only_learner(), dt=1.0)
    result.ticks.append(tick)

    # 4..N) Absent through grace → hold
    hold_tick = None
    for _ in range(int(grace_seconds) + 2):
        tick = session.tick(seat, absent_learner(), dt=1.0)
        result.ticks.append(tick)
        if tick["turn"].get("use_voice_agent"):
            voice.speak(tick["turn"]["line"])
        if tick["presence_hold"]:
            hold_tick = tick
            result.presence_hold_seen = True
            break

    # Return to class
    tick = session.tick(seat, present_learner(), dt=1.0)
    if tick["turn"].get("use_voice_agent"):
        voice.speak(tick["turn"]["line"])
    result.ticks.append(tick)

    # Learner asks a question
    tick = session.tick(
        seat,
        present_learner(),
        dt=1.0,
        learner_question="How does silhouette detection differ from face recognition?",
    )
    if tick["turn"].get("use_voice_agent"):
        voice.speak(tick["turn"]["line"])
    result.ticks.append(tick)

    result.voice_events = list(voice.session.events_received)
    result.session = session.to_dict()

    _check(result.checks, "opened_session", bool(session.seats))
    _check(result.checks, "solo_or_group_size", int(session.room_size) in (2, 4, 6, 9))
    _check(
        result.checks,
        "first_tick_present",
        bool(result.ticks[0]["seat"]["last_verdict"]["present"]),
    )
    _check(result.checks, "presence_hold_triggered", result.presence_hold_seen)
    _check(
        result.checks,
        "hold_turn_pauses",
        hold_tick is not None and hold_tick["turn"]["pause_class"] is True,
    )
    _check(
        result.checks,
        "returned_present",
        bool(result.ticks[-2]["seat"]["last_verdict"]["present"]),
    )
    ask_action = result.ticks[-1]["turn"]["action"]
    _check(
        result.checks,
        "question_handled",
        ask_action in ("answer", "assist_answer"),
    )
    _check(result.checks, "voice_agent_mocked", len(result.voice_events) >= 1)
    if tmode is TeachingMode.SELF_TEACH:
        _check(
            result.checks,
            "self_teach_assist_on_ask",
            ask_action == "assist_answer",
        )
    else:
        _check(
            result.checks,
            "theodore_answers",
            ask_action == "answer",
        )

    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the private webcam recognition lab")
    parser.add_argument("--mode", choices=["theodore_teach", "self_teach"], default="theodore_teach")
    parser.add_argument("--class-mode", choices=["solo", "group"], default="solo")
    parser.add_argument("--size", type=int, choices=[2, 4, 6, 9], default=2)
    parser.add_argument("--grace", type=float, default=3.0)
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    args = parser.parse_args(argv)

    result = run_webcam_lab(
        class_mode=args.class_mode,
        teaching_mode=args.mode,
        room_size=args.size,
        grace_seconds=args.grace,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        failed = [label for label, ok in result.checks if not ok]
        print(
            f"webcam-lab {result.class_mode}/{result.teaching_mode} "
            f"size={result.room_size} hold={result.presence_hold_seen}"
        )
        for label, ok in result.checks:
            print(f"  [{'OK' if ok else 'FAIL'}] {label}")
        if failed:
            print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
            return 1
        print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
