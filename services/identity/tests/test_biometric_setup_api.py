import base64
import uuid

from fastapi.testclient import TestClient

import identity.main as identity_main


client = TestClient(identity_main.app)


def _account():
    email = f"setup-{uuid.uuid4().hex[:8]}@example.com"
    token = client.post(
        "/auth/signup",
        json={"email": email, "password": "S3cretpass"},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    student = client.get("/students", headers=headers).json()["students"][0]
    return headers, student


def test_setup_resumes_and_general_courses_remain_optional():
    headers, student = _account()
    student_id = student["id"]
    update = client.patch(
        f"/students/{student_id}/setup-assistant",
        headers=headers,
        json={"current_step": "preferences"},
    )
    assert update.status_code == 200
    assert client.get(
        f"/students/{student_id}/setup-assistant", headers=headers
    ).json()["current_step"] == "preferences"
    assurance = client.get(
        f"/students/{student_id}/identity-assurance?required=false",
        headers=headers,
    ).json()
    assert assurance == {"allowed": True, "required": False, "missing": [], "reason": ""}


def test_minor_requires_guardian_biometric_consent():
    headers, _ = _account()
    student = client.post(
        "/students",
        headers=headers,
        json={"display_name": "Minor", "age_band": "child"},
    ).json()
    denied = client.put(
        f"/students/{student['id']}/biometric-consent",
        headers=headers,
        json={"granted": True},
    )
    assert denied.status_code == 422
    accepted = client.put(
        f"/students/{student['id']}/biometric-consent",
        headers=headers,
        json={"granted": True, "guardian_granted": True},
    )
    assert accepted.status_code == 200


def test_face_and_document_store_only_verification_metadata(monkeypatch):
    headers, student = _account()
    student_id = student["id"]
    client.put(
        f"/students/{student_id}/biometric-consent",
        headers=headers,
        json={"granted": True},
    )
    monkeypatch.setattr(
        identity_main,
        "_perception_json",
        lambda path, payload: {"student_id": student_id, "enrollments": 1},
    )
    monkeypatch.setattr(
        identity_main,
        "_perception_image",
        lambda path, payload: {"student_id": student_id, "verified": True, "enrollments": 1},
    )
    face = client.post(
        f"/students/{student_id}/biometric-face",
        headers=headers,
        json={
            "embeddings": [[0.1, 0.2, 0.3]],
            "pose_sequence": ["left", "right", "up", "down"],
        },
    )
    assert face.status_code == 200
    image = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 1200).decode()
    document = client.post(
        f"/students/{student_id}/government-id",
        headers=headers,
        json={"document_type": "driver_license", "front_image_b64": image},
    )
    assert document.status_code == 200
    setup = client.get(
        f"/students/{student_id}/setup-assistant", headers=headers
    ).json()
    assert setup["portrait"]["status"] == "verified"
    assert setup["pose"]["status"] == "verified"
    assert setup["government_id"]["status"] == "verified"
    serialized = str(setup)
    assert image not in serialized


def test_biometric_delete_revokes_consent_and_templates(monkeypatch):
    headers, student = _account()
    student_id = student["id"]
    client.put(
        f"/students/{student_id}/biometric-consent",
        headers=headers,
        json={"granted": True},
    )
    deleted: list[str] = []
    monkeypatch.setattr(identity_main, "_perception_delete", deleted.append)
    response = client.delete(f"/students/{student_id}/biometrics", headers=headers)
    assert response.status_code == 200
    assert deleted == [student_id]
    setup = client.get(
        f"/students/{student_id}/setup-assistant", headers=headers
    ).json()
    assert setup["consent"]["granted"] is False
    assert setup["portrait"]["status"] == "revoked"
    assert setup["voice"]["template_ref"] == ""
    assert setup["government_id"]["provider_reference"] == ""


def test_setup_assistant_learner_age_sets_band_and_ratings_build_profile():
    headers, student = _account()
    learner = client.post(
        "/onboarding/learner",
        headers=headers,
        json={"learner_name": "Maya", "age": 11},
    )
    assert learner.status_code == 200
    assert learner.json()["student"]["id"] == student["id"]
    assert learner.json()["age_band"] == "child"
    assert client.post(
        "/onboarding/learner", headers=headers, json={"learner_name": "Maya", "age": 2},
    ).status_code == 422

    ratings = {
        "video": 6, "live_teacher": 4, "presentation": 5,
        "reading": 3, "tutoring": 7, "gaming": 10,
    }
    saved = client.post(
        f"/students/{student['id']}/learning-profile",
        headers=headers,
        json={"answers": {"modality_ratings": ratings}},
    )
    assert saved.status_code == 200
    body = saved.json()["student"]
    assert body["modality_ratings"] == ratings
    assert body["primary_style"] == "hands_on"
    assert body["group_preference"] == "solo"

    bad = client.post(
        f"/students/{student['id']}/learning-profile",
        headers=headers,
        json={"answers": {"modality_ratings": {**ratings, "gaming": 11}}},
    )
    assert bad.status_code == 422
