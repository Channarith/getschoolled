#!/usr/bin/env python3
"""Headless end-to-end demo of the webcam-recognition lab (no camera needed).

Simulates a solo Theodore class where the learner arrives, drifts (low
attention), steps away (user absence), and returns -- printing the presence
transitions and the words Theodore (the xAI voice agent) speaks at each step.
Runs fully offline via the deterministic agent fallback; set XAI_API_KEY to hear
the real Grok voice agent instead.

    python3 scripts/demo.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from webcam_recognition.config import load_lab_config  # noqa: E402
from webcam_recognition.session import ClassMode, SoloSession, TeachingMode  # noqa: E402
from webcam_recognition.silhouette import summarize_frame  # noqa: E402
from webcam_recognition.teaching import TeachingConductor  # noqa: E402
from webcam_recognition.voice_agent import XAIVoiceAgent  # noqa: E402


def _frame(present: bool, attention: float = 0.9):
    fp = summarize_frame([], face_count=1 if present else 0, attention=attention)
    fp.person_present = present
    return fp


def main() -> None:
    cfg = load_lab_config().with_overrides(absent_grace_s=2.0, present_grace_s=1.0)
    agent = XAIVoiceAgent(cfg)
    print(f"xAI agent configured: {agent.configured} (persona: {agent.persona})\n")

    session = SoloSession("demo", TeachingMode.THEODORE, cfg)
    conductor = TeachingConductor(
        agent, class_mode=ClassMode.SOLO,
        teaching_mode=TeachingMode.THEODORE, topic="fractions",
    )

    # (time, present?, attention, note)
    script = [
        (0.0, True, 0.9, "learner sits down"),
        (1.0, True, 0.2, "attention drifting"),
        (2.0, True, 0.15, "still distracted"),
        (5.0, False, 0.0, "steps away"),
        (7.5, False, 0.0, "still away"),
        (9.0, True, 0.8, "comes back"),
        (10.5, True, 0.85, "settled in"),
    ]
    for now, present, attn, note in script:
        print(f"[t={now:>4}s] {note} (present={present}, attention={attn})")
        ev = session.observe(_frame(present, attn), now)
        if ev is not None:
            action = conductor.on_presence_event(
                ev, learner_name="Sam",
                away_seconds=session.tracker.away_seconds_total,
            )
            if action.reply:
                print(f"    -> [{action.kind.value}] Theodore: {action.reply.text}")
        if session.tracker.is_present:
            nudge = conductor.on_attention(session.attention_ewma, learner_name="Sam")
            if nudge.reply:
                print(f"    -> [{nudge.kind.value}] Theodore: {nudge.reply.text}")

    print("\nFinal status:", session.status())


if __name__ == "__main__":
    main()
