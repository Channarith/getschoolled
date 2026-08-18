"""Regression tests for the 2026-08-17 audit (vision_agent absence prompts).

- The per-frame guard fired the Grok absence prompt on EVERY absent frame of
  the first episode and never again from episode two — now once per episode
  via the tracker's on_absent transition.
- The prompt always said "away for 0 seconds" because last_frame_at is
  refreshed by the same request that schedules the prompt — the duration now
  comes from the tracker's absence start (monotonic clock).
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from vision_agent.main import _sessions, app

client = TestClient(app)


class _FakeAgent:
    def __init__(self):
        self.prompts: list[float] = []

    def generate_absence_prompt(self, elapsed, *, lesson_title=""):
        self.prompts.append(elapsed)

        class _R:
            text = "come back"
            model = "fake"

        return _R()


def _make_session() -> str:
    r = client.post("/sessions", json={"class_type": "solo", "student_ids": [], "lesson_title": "Bio"})
    assert r.status_code == 201
    return r.json()["session_id"]


def test_absence_prompt_fires_once_per_episode_with_real_duration():
    sid = _make_session()
    session = _sessions[sid]
    agent = _FakeAgent()
    session._voice_agent = agent

    # Drive the tracker to ABSENT with undecodable frames (silhouette 0, face 0).
    # absence threshold default is small in tests via config; force it directly.
    tracker = session.get_tracker(app.state.config)
    tracker._absence_threshold = 0.05

    import asyncio

    async def drive():
        # Simulate frames: present, then absent long enough to trip the
        # threshold. The on_absent callback schedules the prompt task on THIS
        # running loop (as happens inside the async frame handler).
        tracker.update(face_count=1, silhouette_confidence=0.0, warming_up=False)
        await asyncio.sleep(0.08)
        for _ in range(4):
            tracker.update(face_count=0, silhouette_confidence=0.0, warming_up=False)
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)  # let the fire-and-forget prompt task run

    asyncio.run(drive())

    assert len(agent.prompts) == 1, f"expected 1 prompt, got {len(agent.prompts)}"
    assert agent.prompts[0] >= 0.05, f"prompt said {agent.prompts[0]}s — the 0-seconds bug"
    _sessions.pop(sid, None)
