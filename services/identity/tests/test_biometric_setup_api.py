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


def test_setup_assistant_persists_only_the_changed_account(monkeypatch):
    from identity.store import AccountStore

    store = AccountStore()
    account = store.create("scoped-setup@example.com", "S3cretpass")
    student = store.ensure_default_student(account.id)
    persisted: list[tuple[str, ...]] = []
    monkeypatch.setattr(store, "_persist", lambda *account_ids: persisted.append(account_ids))

    store.update_biometric_setup(account.id, student.id, {"current_step": "biometrics"})

    assert persisted == [(account.id,)]


def test_student_added_on_another_replica_reloads_instead_of_404(monkeypatch):
    headers, _ = _account()
    accounts = identity_main.app.state.accounts
    account_id = client.get("/auth/me", headers=headers).json()["id"]
    hidden = accounts.add_student(account_id, "Other replica", age_band="adult")
    accounts.get_by_id(account_id).students.pop(hidden.id)
    reloads: list[str] = []

    def reload(aid):
        reloads.append(aid)
        accounts.get_by_id(aid).students[hidden.id] = hidden
        return True

    monkeypatch.setattr(accounts, "reload_account", reload)
    resp = client.get(f"/students/{hidden.id}/setup-assistant", headers=headers)
    assert resp.status_code == 200
    assert reloads == [account_id]
    monkeypatch.setattr(accounts, "reload_account", lambda aid: False)
    assert client.get("/students/missing/setup-assistant", headers=headers).status_code == 404


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
    neutral = [1.0, 0.0, 0.0]
    face = client.post(
        f"/students/{student_id}/biometric-face",
        headers=headers,
        json={
            "embeddings": [
                neutral,
                [0.98, 0.15, 0.0],
                [0.98, -0.15, 0.0],
                [0.98, 0.0, 0.15],
                [0.98, 0.0, -0.15],
            ],
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


def test_face_enrollment_stores_nothing_until_poses_match(monkeypatch):
    headers, student = _account()
    student_id = student["id"]
    client.put(
        f"/students/{student_id}/biometric-consent",
        headers=headers,
        json={"granted": True},
    )
    calls: list[str] = []

    def fake_json(path, payload):
        calls.append(path)
        return {"student_id": student_id, "enrollments": len(calls)}

    monkeypatch.setattr(identity_main, "_perception_json", fake_json)
    short = client.post(
        f"/students/{student_id}/biometric-face",
        headers=headers,
        json={"embeddings": [[1.0, 0.0, 0.0]], "pose_sequence": ["left", "right", "up", "down"]},
    )
    assert short.status_code == 422
    assert calls == []
    other_person = client.post(
        f"/students/{student_id}/biometric-face",
        headers=headers,
        json={
            "embeddings": [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.98, -0.15, 0.0],
                [0.98, 0.0, 0.15],
                [0.98, 0.0, -0.15],
            ],
            "pose_sequence": ["left", "right", "up", "down"],
        },
    )
    assert other_person.status_code == 422
    assert calls == []
    ready = client.post(
        f"/students/{student_id}/biometric-face",
        headers=headers,
        json={
            "embeddings": [
                [1.0, 0.0, 0.0],
                [0.98, 0.15, 0.0],
                [0.98, -0.15, 0.0],
                [0.98, 0.0, 0.15],
                [0.98, 0.0, -0.15],
            ],
            "pose_sequence": ["down", "up", "right", "left"],
        },
    )
    assert ready.status_code == 200
    assert calls == [f"/enroll-embedding/{student_id}"] * 5
    assert ready.json()["enrollments"] == 5


def test_pose_challenge_accepts_a_turned_head(monkeypatch):
    """A same-person look near cosine 0.19 used to 422 at the 0.22 gate."""
    import math

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
    turned = math.sqrt(1 - 0.19 ** 2)
    neutral = [1.0, 0.0, 0.0]
    same_person = [0.19, turned, 0.0]
    stranger = [0.05, math.sqrt(1 - 0.05 ** 2), 0.0]
    ok = client.post(
        f"/students/{student_id}/biometric-face",
        headers=headers,
        json={
            "embeddings": [neutral, same_person, same_person, same_person, [0.2, math.sqrt(1 - 0.04), 0.0]],
            "pose_sequence": ["left", "right", "up", "down"],
        },
    )
    assert ok.status_code == 200
    stranger_post = client.post(
        f"/students/{student_id}/biometric-face",
        headers=headers,
        json={
            "embeddings": [neutral, stranger, same_person, same_person, same_person],
            "pose_sequence": ["left", "right", "up", "down"],
        },
    )
    assert stranger_post.status_code == 422
    assert stranger_post.json()["detail"].startswith("pose challenge face does not match portrait")


def test_face_preview_needs_consent_and_stores_nothing(monkeypatch):
    headers, student = _account()
    student_id = student["id"]
    image = base64.b64encode(b"\xff\xd8\xff" + b"\0" * 1500).decode()
    assert client.post(
        f"/students/{student_id}/face-preview", headers=headers, json={"image_b64": image},
    ).status_code == 409
    client.put(
        f"/students/{student_id}/biometric-consent", headers=headers, json={"granted": True},
    )
    calls: list[str] = []
    face = {
        "bbox": [10, 20, 100, 120],
        "landmarks": [[40, 60], [80, 60], [60, 85], [45, 110], [75, 110]],
        "frame_size": [200, 260],
        "score": 0.93,
    }

    def fake_image(path, payload):
        calls.append(path)
        return {"faces": [face]}

    monkeypatch.setattr(identity_main, "_perception_image", fake_image)
    before = client.get(f"/students/{student_id}/setup-assistant", headers=headers).json()
    preview = client.post(
        f"/students/{student_id}/face-preview", headers=headers, json={"image_b64": image},
    )
    assert preview.status_code == 200
    assert preview.json()["faces"] == [face]
    assert calls == ["/detect-landmarks"]
    after = client.get(f"/students/{student_id}/setup-assistant", headers=headers).json()
    assert after == before
    assert client.post(
        f"/students/{student_id}/face-preview", headers=headers, json={"image_b64": "@@"},
    ).status_code == 422


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
