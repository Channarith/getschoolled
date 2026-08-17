"""Regression tests for the 2026-08-17 audit (webcam service).

- HIGH-4  GroupPresenceTracker was created but never fed, so every group
          presence summary reported zero participants and quorum never met.
- HIGH-6  _sessions had no reaper and participant_id was unvalidated, letting
          a client allocate one MOG2 background model per request until OOM.
"""

import time

from fastapi.testclient import TestClient

from webcam.main import _sessions, app

client = TestClient(app)

# A 1x1 white JPEG that SilhouetteDetector can decode.
_TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300030202030202030303"
    "0304030304050805050404050a070706080c0a0c0c0b0a0b0b0d0e12100d0e110e0b"
    "0b1016101113141515150c0f171816141812141514ffdb0043010304040504050905"
    "0509140d0b0d14141414141414141414141414141414141414141414141414141414"
    "141414141414141414141414141414141414141414141414ffc00011080001000103"
    "012200021101031101ffc40014000100000000000000000000000000000000000000"
    "08ffc4001410010000000000000000000000000000000000000000ffc40014010100"
    "00000000000000000000000000000000000008ffc400141101000000000000000000"
    "00000000000000000000ffda000c03010002110311003f00b2c001ffd9"
)


def _create(class_type="group", student_ids=None):
    r = client.post("/sessions", json={
        "class_type": class_type,
        "student_ids": student_ids or [],
        "lesson_context": "",
    })
    assert r.status_code == 200
    return r.json()["session_id"]


def _frame(sid, participant, face_present="true"):
    return client.post(
        f"/sessions/{sid}/frame",
        files={"file": ("f.jpg", _TINY_JPEG, "image/jpeg")},
        data={"participant_id": participant, "face_present": face_present,
              "attention": "0.8"},
    )


def test_group_presence_summary_is_fed():
    sid = _create("group", ["alice", "bob"])
    _frame(sid, "alice")
    _frame(sid, "bob")
    summary = client.get(f"/sessions/{sid}/presence").json()["group_summary"]
    assert summary["total_participants"] == 2
    assert summary["present_count"] == 2
    assert summary["quorum_met"] is True


def test_participant_not_on_roster_rejected():
    sid = _create("group", ["alice"])
    r = _frame(sid, "mallory")
    assert r.status_code == 403
    # No detector/tracker may have been allocated for the intruder.
    s = _sessions[sid]
    assert "mallory" not in s.detectors and "mallory" not in s.trackers


def test_idle_sessions_are_reaped():
    sid = _create("solo", [])
    _sessions[sid].last_activity = time.monotonic() - 100_000
    _create("solo", [])  # any new session triggers the reaper
    assert sid not in _sessions
    assert client.get(f"/sessions/{sid}").status_code == 404
