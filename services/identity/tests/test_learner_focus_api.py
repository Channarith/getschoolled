"""Focus events and report cards persist on the student record."""

import uuid

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _auth():
    email = f"focus-{uuid.uuid4().hex[:8]}@example.com"
    tok = client.post("/auth/signup", json={"email": email, "password": "S3cretpass"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def _student(headers):
    created = client.post(
        "/students",
        headers=headers,
        json={"display_name": "Nora", "age_band": "child"},
    ).json()
    return created["id"]


def test_focus_events_round_trip_and_report_card():
    headers = _auth()
    student_id = _student(headers)
    posted = client.post(
        f"/students/{student_id}/focus-events",
        headers=headers,
        json={
            "kind": "camera_on",
            "surface": "children_lab",
            "context": "children",
            "evidence": {"signal": "face_mesh"},
        },
    )
    assert posted.status_code == 200
    client.post(
        f"/students/{student_id}/learning-preferences",
        headers=headers,
        json={"class_length": "short", "modality": "video", "materials": "games"},
    )
    client.post(
        f"/students/{student_id}/focus-periods",
        headers=headers,
        json={"kind": "eat_and_learn", "note": "snack during story time", "active": True},
    )
    profile = client.get(f"/students/{student_id}/focus-profile", headers=headers).json()
    assert profile["focus_profile"]["preferences"]["class_length"] == "short"
    assert profile["focus_profile"]["events"][0]["kind"] == "camera_on"
    card = client.get(
        f"/students/{student_id}/report-card",
        headers=headers,
        params={"context": "children"},
    ).json()
    assert card["learner_name"] == "Nora"
    assert card["categories"][0]["category"] == "Attendance & Punctuality"
    assert card["identity_check"]["status"] == "unverified"


def test_identity_verification_stays_honest():
    headers = _auth()
    student_id = _student(headers)
    rejected = client.post(
        f"/students/{student_id}/identity-verification",
        headers=headers,
        json={"status": "verified", "document_type": "license", "document_number": "D123"},
    )
    assert rejected.status_code == 422 or rejected.status_code == 400
    pending = client.post(
        f"/students/{student_id}/identity-verification",
        headers=headers,
        json={"status": "pending", "document_type": "license", "reference": "chk-9"},
    )
    assert pending.status_code == 200
    assert pending.json()["identity_check"]["status"] == "pending"
    bare = client.post(
        f"/students/{student_id}/identity-verification",
        headers=headers,
        json={"status": "verified", "document_type": "license"},
    )
    assert bare.status_code == 400
