"""Unified learnable search API on the curriculum service."""

from curriculum.catalog import CatalogStore
from curriculum.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _empty_catalog():
    app.state.catalog = CatalogStore()


def test_learn_search_returns_mixed_sources():
    _empty_catalog()
    body = client.get("/learn/search", params={"q": "python", "limit": 30}).json()
    assert body["total"] >= 5
    sources = {i["source"] for i in body["items"]}
    assert "lesson" in sources or "audio" in sources


def test_courses_search_unified_when_catalog_empty():
    _empty_catalog()
    courses = client.get("/courses/search", params={"limit": 50}).json()
    assert len(courses) >= 50
    formats = {c.get("source") or c.get("media_format") for c in courses}
    assert formats


def test_home_feed_unified_rails():
    _empty_catalog()
    rails = client.get("/home").json()["rails"]
    keys = {r["key"] for r in rails}
    assert "live" in keys
    assert "audio" in keys
    assert sum(len(r["courses"]) for r in rails) >= 20


def test_learn_facets_and_item_lookup():
    _empty_catalog()
    facets = client.get("/learn/facets").json()
    assert "live_class" in facets["formats"]
    search = client.get("/learn/search", params={"source": "lesson", "limit": 1}).json()
    gid = search["items"][0]["id"]
    got = client.get(f"/learn/items/{gid}").json()
    assert got["id"] == gid


def test_get_course_resolves_lesson_id():
    _empty_catalog()
    lessons = client.get("/learn/search", params={"source": "lesson", "limit": 1}).json()
    lesson_id = lessons["items"][0]["source_id"]
    course = client.get(f"/courses/{lesson_id}").json()
    assert course["course_id"] == lesson_id
    assert course["deep_link"].startswith("/class")
