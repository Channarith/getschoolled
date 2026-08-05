"""Theodore (AI) teaching vs user self-teaching modes for the webcam lab."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import List, Optional

from .presence import PresenceVerdict


class TeachingMode(str, Enum):
    """Who leads the spoken lesson."""

    THEODORE_TEACH = "theodore_teach"  # AI host teaches; learners attend
    SELF_TEACH = "self_teach"  # human hosts/teaches; Theodore assists on ask


@dataclass
class TeachingTurn:
    mode: TeachingMode
    speaker: str
    action: str
    line: str
    use_voice_agent: bool = True
    pause_class: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d


THEODORE_NAME = "Theodore (AI Host)"


def plan_teaching_turn(
    *,
    mode: TeachingMode,
    slide_title: str,
    presence: Optional[PresenceVerdict] = None,
    learner_question: str = "",
    human_host_name: str = "Host",
) -> TeachingTurn:
    """Decide the next teaching action from mode + presence + optional Q.

    Absence with hold_recommended pauses the class and has Theodore (or the
    self-teach assist path) speak a natural re-engagement line via the voice
    agent.
    """
    title = (slide_title or "the current topic").strip()
    question = (learner_question or "").strip()

    if presence is not None and presence.hold_recommended:
        return TeachingTurn(
            mode=mode,
            speaker=THEODORE_NAME,
            action="presence_hold",
            line=(
                "I'll pause for a moment — I can't see you in the camera. "
                "Come back into view when you're ready and we'll continue with "
                f"{title}."
            ),
            use_voice_agent=True,
            pause_class=True,
            reason=presence.reason or "user_absent",
        )

    if presence is not None and not presence.present and not presence.hold_recommended:
        # Still in grace — soft nudge, keep teaching.
        nudge = (
            "I notice you may have stepped away briefly. "
            f"I'll keep going with {title}."
        )
        if mode is TeachingMode.SELF_TEACH:
            return TeachingTurn(
                mode=mode,
                speaker=THEODORE_NAME,
                action="assist_nudge",
                line=nudge,
                use_voice_agent=True,
                pause_class=False,
                reason=presence.reason or "grace_absent",
            )
        return TeachingTurn(
            mode=mode,
            speaker=THEODORE_NAME,
            action="soft_nudge",
            line=nudge,
            use_voice_agent=True,
            pause_class=False,
            reason=presence.reason or "grace_absent",
        )

    if question:
        if mode is TeachingMode.SELF_TEACH:
            return TeachingTurn(
                mode=mode,
                speaker=THEODORE_NAME,
                action="assist_answer",
                line=(
                    f"Happy to help while {human_host_name} teaches. "
                    f"About your question on {title}: {question} — "
                    "here's a short clarification."
                ),
                use_voice_agent=True,
                pause_class=False,
                reason="learner_ask",
            )
        return TeachingTurn(
            mode=mode,
            speaker=THEODORE_NAME,
            action="answer",
            line=(
                f"Good question about {title}. "
                "Let me explain that clearly, then we'll check understanding."
            ),
            use_voice_agent=True,
            pause_class=False,
            reason="learner_ask",
        )

    if mode is TeachingMode.SELF_TEACH:
        return TeachingTurn(
            mode=mode,
            speaker=human_host_name,
            action="human_teach",
            line=f"Continuing the lesson on {title}.",
            use_voice_agent=False,
            pause_class=False,
            reason="self_teach",
        )

    return TeachingTurn(
        mode=mode,
        speaker=THEODORE_NAME,
        action="teach",
        line=(
            f"Let's look at {title} together. "
            "Watch the slide, stay in frame, and ask anytime."
        ),
        use_voice_agent=True,
        pause_class=False,
        reason="theodore_teach",
    )


def teaching_script(
    mode: TeachingMode,
    slides: List[str],
    *,
    presence_by_slide: Optional[List[Optional[PresenceVerdict]]] = None,
) -> List[TeachingTurn]:
    """Build a short multi-slide teaching script for the lab harness."""
    presence_by_slide = presence_by_slide or [None] * len(slides)
    turns: List[TeachingTurn] = []
    for i, title in enumerate(slides):
        presence = presence_by_slide[i] if i < len(presence_by_slide) else None
        turns.append(plan_teaching_turn(mode=mode, slide_title=title, presence=presence))
    return turns
