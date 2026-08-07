from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_course_studio.main import app

client = TestClient(app)


def test_health_and_studio_page():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "theodore-course-studio"
    page = client.get("/studio")
    assert page.status_code == 200
    assert "Theodore Course Studio" in page.text
    assert "Run training scan" in page.text
    assert "Learner profile scoring" in page.text
    assert "Reject" in page.text
    assert "Pop quiz" in page.text
    assert "Summary quiz" in page.text
    assert "Play game" in page.text
