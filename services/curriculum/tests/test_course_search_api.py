"""Faceted catalog search + metadata (Netflix-style browse)."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def _course(**kw):
    body = {"title": "T", "subject": "general"}
    body.update(kw)
    return client.post("/courses", json=body).json()


def test_metadata_defaults_category_and_audio():
    c = _course(title="Knife Skills", subject="culinary", language="en")
    assert c["category"] == "culinary"        # defaults to subject
    assert c["audio_language"] == "en"        # defaults to language
    assert c["media_format"] == "video"
    assert c["hands_on"] is False


def test_search_by_name_category_language_audio():
    _course(title="Intro Biology", subject="biology", language="en",
            tags=["cells", "dna"], media_format="video")
    _course(title="Biologia Intro", subject="biology", language="es",
            audio_language="es", tags=["celulas"])
    _course(title="French Cooking", subject="culinary", language="fr",
            hands_on=True, tags=["knife"], media_format="interactive")

    by_name = client.get("/courses/search", params={"q": "biology"}).json()
    assert any("Biology" in c["title"] for c in by_name)

    by_lang = client.get("/courses/search", params={"category": "biology", "language": "es"}).json()
    assert by_lang and all(c["language"] == "es" for c in by_lang)

    by_audio = client.get("/courses/search", params={"audio": "es"}).json()
    assert all(c["audio_language"] == "es" for c in by_audio)


def test_search_hands_on_and_format_and_tag():
    _course(title="Welding Lab", subject="vocational", hands_on=True,
            media_format="interactive", tags=["welding", "safety"])
    hands = client.get("/courses/search", params={"hands_on": "true"}).json()
    assert hands and all(c["hands_on"] is True for c in hands)

    fmt = client.get("/courses/search", params={"media_format": "interactive"}).json()
    assert all(c["media_format"] == "interactive" for c in fmt)

    tagged = client.get("/courses/search", params={"tag": "welding"}).json()
    assert tagged and all("welding" in c["tags"] for c in tagged)


def test_facets_endpoint():
    _course(title="Audio Spanish", subject="language", language="es",
            media_format="audio", level="intermediate", tags=["spanish"])
    facets = client.get("/courses/facets").json()
    assert "audio" in facets["media_formats"] or "video" in facets["media_formats"]
    assert "languages" in facets and "categories" in facets and "tags" in facets


def test_search_route_not_shadowed_by_course_id():
    # /courses/search must resolve to search, not GET /courses/{course_id}.
    r = client.get("/courses/search")
    assert r.status_code == 200 and isinstance(r.json(), list)
