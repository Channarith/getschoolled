"""Curriculum clip endpoint stores a playable reference on the course."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def test_youtube_clip_is_stored_as_trailer_metadata():
    created = client.post("/courses", json={"title": "Fractions", "subject": "math"}).json()
    built = client.post(
        f"/courses/{created['course_id']}/clips",
        json={
            "topic": "Fractions",
            "language": "en",
            "duration_sec": 30,
            "source_url": "https://www.youtube.com/watch?v=abcdefghijk",
        },
    ).json()
    assert built["clips"][0]["source"] == "youtube"
    assert built["clips"][0]["play"]["video_id"] == "abcdefghijk"
    assert built["clips"][0]["play"]["path"] == ""
    course = client.get(f"/courses/{created['course_id']}").json()
    assert course["media_format"] == "video"
    assert course["trailer_url"].startswith("https://www.youtube.com/embed/abcdefghijk?")
    assert ".mp4" not in course["trailer_url"]


def test_missing_clip_source_stores_generated_title_card():
    created = client.post("/courses", json={"title": "Moss", "subject": "biology"}).json()
    built = client.post(
        f"/courses/{created['course_id']}/clips",
        json={"topic": "Moss life cycle", "language": "en", "duration_sec": 20},
    ).json()
    clip = built["clips"][0]
    assert clip["source"] == "generated"
    assert clip["title"] == "Moss life cycle"
    assert clip["duration"] == 20
    assert "<svg" in clip["play"]["svg"]
    course = client.get(f"/courses/{created['course_id']}").json()
    assert course["trailer_url"].startswith("data:image/svg+xml")


def test_clip_list_shape():
    built = client.post(
        "/clips",
        json={"topic": "Tides", "duration_sec": 40, "language": "en"},
    ).json()
    assert built["media_format"] == "video"
    for clip in built["clips"]:
        assert clip["source"] in {"youtube", "online", "generated"}
        assert clip["title"]
        assert isinstance(clip["duration"], int)
        assert clip["how"]
