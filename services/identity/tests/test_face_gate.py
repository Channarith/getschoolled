"""Face template replace, 1:1 match, and single-use verify tokens."""

from __future__ import annotations

import time
import uuid

from fastapi.testclient import TestClient

from aoep_shared.face_gate import decide_face_scan, issue_face_token, read_face_token
from identity.main import app

client = TestClient(app)

SAME = [1.0] + [0.0] * 127
OTHER = [0.0] * 127 + [1.0]


def _auth() -> dict:
    email = f"face-{uuid.uuid4().hex[:8]}@example.com"
    token = client.post(
        "/auth/signup", json={"email": email, "password": "S3cretpass"},
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _student(headers: dict) -> str:
    return client.get("/students", headers=headers).json()["students"][0]["id"]


def test_other_face_does_not_verify():
    headers = _auth()
    student_id = _student(headers)
    enrolled = client.post(
        f"/students/{student_id}/face-enrollment",
        json={"embedding": SAME},
        headers=headers,
    )
    assert enrolled.status_code == 200, enrolled.text
    rejected = client.post(
        f"/students/{student_id}/face-verify",
        json={"embedding": OTHER, "purpose": "start"},
        headers=headers,
    )
    assert rejected.status_code == 403
    matched = client.post(
        f"/students/{student_id}/face-verify",
        json={"embedding": SAME, "purpose": "start"},
        headers=headers,
    )
    assert matched.status_code == 200, matched.text
    assert matched.json()["token"]


def test_replace_invalidates_outstanding_tokens_and_hides_template():
    headers = _auth()
    student_id = _student(headers)
    client.post(
        f"/students/{student_id}/face-enrollment",
        json={"embedding": SAME},
        headers=headers,
    )
    first = client.post(
        f"/students/{student_id}/face-verify",
        json={"embedding": SAME, "purpose": "start"},
        headers=headers,
    ).json()["token"]
    replaced = client.post(
        f"/students/{student_id}/face-enrollment",
        json={"embedding": OTHER},
        headers=headers,
    )
    assert replaced.status_code == 200, replaced.text
    stale = client.post(
        "/internal/face-gate/consume",
        json={
            "token": first,
            "account_id": client.get("/auth/me", headers=headers).json()["id"],
            "student_id": student_id,
            "purpose": "start",
        },
    )
    assert stale.status_code == 403
    assert "changed" in stale.json()["detail"]
    fresh = client.post(
        f"/students/{student_id}/face-verify",
        json={"embedding": OTHER, "purpose": "checkpoint"},
        headers=headers,
    )
    assert fresh.status_code == 200, fresh.text
    profile = client.get(f"/students/{student_id}", headers=headers).json()
    assert profile["face_enrolled"] is True
    assert "face_embedding" not in profile
    assert "face_consumed_jtis" not in profile


def test_token_is_single_use_and_purpose_bound():
    headers = _auth()
    account_id = client.get("/auth/me", headers=headers).json()["id"]
    student_id = _student(headers)
    client.post(
        f"/students/{student_id}/face-enrollment",
        json={"embedding": SAME},
        headers=headers,
    )
    token = client.post(
        f"/students/{student_id}/face-verify",
        json={"embedding": SAME, "purpose": "start"},
        headers=headers,
    ).json()["token"]
    body = {
        "token": token,
        "account_id": account_id,
        "student_id": student_id,
        "purpose": "checkpoint",
    }
    wrong_purpose = client.post("/internal/face-gate/consume", json=body)
    assert wrong_purpose.status_code == 403
    body["purpose"] = "start"
    first = client.post("/internal/face-gate/consume", json=body)
    assert first.status_code == 200, first.text
    replay = client.post("/internal/face-gate/consume", json=body)
    assert replay.status_code == 403
    assert "already used" in replay.json()["detail"]


def test_expired_token_is_rejected():
    token = issue_face_token(
        account_id="acct",
        student_id="stu",
        purpose="resume",
        generation=1,
        ttl_s=30,
    )
    try:
        read_face_token(
            token,
            account_id="acct",
            student_id="stu",
            purpose="resume",
            now=time.time() + 120,
        )
        raise AssertionError("expired token was accepted")
    except ValueError as exc:
        assert "invalid" in str(exc)


def test_scan_waits_until_the_minute_then_times_out():
    assert decide_face_scan(matched=False, elapsed_s=0) == "wait"
    assert decide_face_scan(matched=False, elapsed_s=59.9) == "wait"
    assert decide_face_scan(matched=True, elapsed_s=59.9) == "match"
    assert decide_face_scan(matched=False, elapsed_s=60) == "timeout"
    assert decide_face_scan(matched=True, elapsed_s=90) == "match"
