"""Audio catalog endpoints with the new locale= query parameter."""

from curriculum.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_categories_default_to_english():
    body = client.get("/audio/categories").json()
    cats = {c["category_id"]: c["category"] for c in body["categories"]}
    assert cats["Languages"] == "Languages"
    assert cats["History"] == "History"
    assert body["locale"] == "en"


def test_categories_in_spanish():
    body = client.get("/audio/categories", params={"locale": "es"}).json()
    cats = {c["category_id"]: c["category"] for c in body["categories"]}
    assert cats["Languages"] == "Idiomas"
    assert cats["Personal Finance"] == "Finanzas personales"


def test_courses_in_japanese():
    body = client.get("/audio/courses",
                      params={"category": "Languages", "locale": "ja", "limit": 100}).json()
    assert body["locale"] == "ja"
    levels = {c["level"] for c in body["courses"]}
    assert levels == {"初級"}
    # Every language course title should embed the target language name
    # in Japanese (the language being TAUGHT, rendered for the ja UI).
    assert any("\u8a9e" in c["title"] or "\u8a9e" in c["subject"]
               for c in body["courses"])  # 語 = "language"


def test_course_detail_localized_segments():
    body = client.get("/audio/courses/audio-ancient-egypt",
                      params={"locale": "fr"}).json()
    assert body["locale"] == "fr"
    assert body["category"] == "Histoire"
    assert body["level"] == "débutant"
    assert body["segments"][0]["heading"] == "Introduction"
    assert "Bienvenue" in body["segments"][0]["text"]


def test_filter_by_localized_category():
    body = client.get("/audio/courses",
                      params={"category": "Histoire", "locale": "fr", "limit": 100}).json()
    assert body["total"] > 0
    assert all(c["category"] == "Histoire" for c in body["courses"])


def test_unknown_locale_falls_back_to_english():
    body = client.get("/audio/categories", params={"locale": "xx"}).json()
    cats = {c["category_id"]: c["category"] for c in body["categories"]}
    assert cats["Languages"] == "Languages"
