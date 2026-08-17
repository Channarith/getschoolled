"""Regression tests for the 2026-08-17 audit (vision_agent service).

- HIGH-5  Session records were never removed from _sessions (unbounded leak;
          the "retained for metrics" justification was unreachable code).
- LOW-12  The SSE "connected" frame was not valid JSON (Python single quotes).
"""

import json
import time

from fastapi.testclient import TestClient

from vision_agent.main import _sessions, app

client = TestClient(app)


def _create() -> str:
    r = client.post("/sessions", json={"class_type": "solo", "student_ids": [],
                                       "lesson_title": "Audit"})
    assert r.status_code == 201
    return r.json()["session_id"]


def test_end_session_releases_state():
    sid = _create()
    r = client.delete(f"/sessions/{sid}")
    assert r.status_code == 200
    assert sid not in _sessions, "ended session record was retained (leak)"


def test_idle_sessions_are_reaped():
    sid = _create()
    _sessions[sid].created_at = time.time() - 100_000
    _create()  # triggers the reaper
    assert sid not in _sessions


def test_sse_connected_frame_is_valid_json():
    import asyncio

    import vision_agent.main as va_main

    sid = _create()

    class _Req:
        async def is_disconnected(self):
            return True  # end the stream right after the connected frame

    async def first_frame() -> str:
        resp = await va_main.events_stream(sid, _Req())
        gen = resp.body_iterator
        return await gen.__anext__()

    first = asyncio.run(first_frame())
    assert first.startswith("data: ")
    payload = json.loads(first[len("data: "):])  # must not raise
    assert payload["kind"] == "connected"
    assert payload["session_id"] == sid
