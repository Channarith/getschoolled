"""Audio-only drive-mode course endpoints."""

from curriculum.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_categories():
    cats = client.get("/audio/categories").json()["categories"]
    names = {c["category"] for c in cats}
    assert {"Languages", "History", "Personal Finance"} <= names


def test_list_paginates_and_total_is_hundreds():
    body = client.get("/audio/courses", params={"limit": 20}).json()
    assert body["total"] >= 200
    assert len(body["courses"]) == 20
    assert all(c["format"] == "audio" and c["visual_required"] is False
               and c["drive_safe"] is True for c in body["courses"])


def test_filter_by_category_and_search():
    langs = client.get("/audio/courses", params={"category": "Languages", "limit": 100}).json()
    assert langs["total"] > 10
    assert all(c["category"] == "Languages" for c in langs["courses"])
    found = client.get("/audio/courses", params={"q": "budgeting"}).json()
    assert found["total"] >= 1


def test_get_course_has_narration_segments():
    body = client.get("/audio/courses/lang-es-phrases").json()
    assert body["format"] == "audio" and body["visual_required"] is False
    assert len(body["segments"]) >= 3
    assert body["segments"][0]["heading"] == "Introduction"


def test_unknown_audio_course_404():
    assert client.get("/audio/courses/nope").status_code == 404
