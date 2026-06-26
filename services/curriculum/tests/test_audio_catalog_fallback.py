"""Home/browse fall back to the audio library when CatalogStore is empty."""

from curriculum.catalog import CatalogStore
from curriculum.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _empty_catalog():
    app.state.catalog = CatalogStore()


def test_home_feed_uses_audio_when_catalog_empty():
    _empty_catalog()
    rails = client.get("/home").json()["rails"]
    assert len(rails) >= 3
    keys = {r["key"] for r in rails}
    assert "new" in keys
    assert "audio" in keys
    assert any(k.startswith("cat:") for k in keys)
    total_courses = sum(len(r["courses"]) for r in rails)
    assert total_courses >= 12
    audio_rail = next(r for r in rails if r["key"] == "audio")
    sample = audio_rail["courses"][0]
    assert sample["media_format"] == "audio"
    assert sample["course_id"].startswith(("audio-", "lang-"))


def test_search_and_facets_use_audio_when_catalog_empty():
    _empty_catalog()
    courses = client.get("/courses/search").json()
    assert len(courses) >= 50
    assert any(c["media_format"] == "audio" for c in courses)
    facets = client.get("/courses/facets").json()
    assert "History" in facets["categories"] or len(facets["categories"]) >= 5
    assert "audio" in facets["media_formats"]


def test_get_course_resolves_audio_id_when_catalog_empty():
    _empty_catalog()
    listed = client.get("/courses/search", params={"q": "egypt"}).json()
    assert listed
    course_id = listed[0]["course_id"]
    got = client.get(f"/courses/{course_id}").json()
    assert got["course_id"] == course_id
    assert got["title"] == listed[0]["title"]


def test_seeded_catalog_takes_precedence():
    _empty_catalog()
    empty_home = client.get("/home").json()["rails"]
    assert empty_home
    client.post("/courses", json={"title": "Only Custom Course", "category": "Science"})
    seeded = client.get("/home").json()["rails"]
    titles = {c["title"] for r in seeded for c in r["courses"]}
    assert "Only Custom Course" in titles
    assert all(c["title"] != "Only Custom Course" for r in empty_home for c in r["courses"])
