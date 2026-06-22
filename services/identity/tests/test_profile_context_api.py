"""Authenticated profile context sharing for future integrations."""

import uuid

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _signup():
    email = f"context-{uuid.uuid4().hex[:8]}@example.com"
    token = client.post(
        "/auth/signup",
        json={"email": email, "password": "S3cretpass", "display_name": "Casey"},
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_profile_context_remembers_class_context_between_classes():
    h = _signup()
    student = client.post(
        "/students",
        headers=h,
        json={
            "display_name": "Learner A",
            "age_band": "teen",
            "interests": ["robotics"],
        },
    ).json()
    sid = student["id"]

    assert client.get(f"/students/{sid}/profile-context").status_code in (401, 422)

    client.post(
        f"/students/{sid}/class-context",
        headers=h,
        json={
            "course_id": "math-101",
            "class_id": "class-1",
            "title": "Fractions intro",
            "summary": "Understands halves; needs practice comparing thirds.",
            "skills": ["fractions", "fractions", "comparison"],
        },
    )
    client.post(
        f"/students/{sid}/class-context",
        headers=h,
        json={
            "course_id": "math-102",
            "class_id": "class-2",
            "title": "Decimal bridge",
            "summary": "Connected tenths to fractions with visual cues.",
            "skills": ["decimals"],
        },
    )
    client.post(
        f"/students/{sid}/mastery",
        headers=h,
        json={"skill": "fractions", "value": 0.7},
    )
    client.post(
        f"/students/{sid}/complete",
        headers=h,
        json={"course_id": "math-101", "skills": ["fractions"]},
    )

    context = client.get(f"/students/{sid}/profile-context", headers=h).json()
    assert context["schema_version"] == "aoep.profile_context.v1"
    assert context["student"]["display_name"] == "Learner A"
    assert context["student"]["interests"] == ["robotics"]
    assert context["mastery"]["fractions"] >= 0.8
    assert "math-101" in context["completed_course_ids"]
    assert [c["class_id"] for c in context["class_contexts"]] == ["class-1", "class-2"]
    assert context["class_contexts"][0]["skills"] == ["comparison", "fractions"]


def test_profile_share_token_is_scoped_and_authenticated():
    h = _signup()
    student = client.post(
        "/students", headers=h, json={"display_name": "Learner B"}
    ).json()
    sid = student["id"]
    client.post(
        f"/students/{sid}/class-context",
        headers=h,
        json={
            "course_id": "science-1",
            "summary": "Likes astronomy.",
            "skills": ["space"],
        },
    )

    grant = client.post(
        f"/students/{sid}/profile-share-grants",
        headers=h,
        json={
            "integration": "robot-tutor",
            "scopes": ["profile", "class_context"],
            "ttl_s": 600,
        },
    ).json()
    shared = client.get(
        "/profile-shares/context",
        headers={"Authorization": f"Bearer {grant['token']}"},
    ).json()

    assert shared["student"]["id"] == sid
    assert shared["class_contexts"][0]["course_id"] == "science-1"
    assert "mastery" not in shared
    bad = client.get("/profile-shares/context", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
