"""Content interchange / export (Netflix-compatible catalog feeds)."""

from fastapi.testclient import TestClient

from curriculum.catalog import CatalogStore
from curriculum.main import app

client = TestClient(app)


def _seed():
    app.state.catalog = CatalogStore()
    client.post("/courses", json={
        "title": "Intro to Biology", "subject": "biology", "language": "en",
        "tags": ["cells", "dna"], "level": "beginner", "duration_min": 45,
        "maturity_rating": "all", "subtitle_languages": ["en", "es"],
        "hls_url": "https://cdn.example/bio/master.m3u8", "thumbnail": "https://cdn.example/bio.jpg",
        "preview": "Cells and DNA.",
    })


def test_json_feed_shape():
    _seed()
    feed = client.get("/catalog/export", params={"format": "json"}).json()
    assert feed["provider"] == "AOEP" and feed["titleCount"] >= 1
    t = next(x for x in feed["titles"] if x["title"] == "Intro to Biology")
    assert t["audioLanguages"] == ["en"]
    assert t["subtitleLanguages"] == ["en", "es"]
    assert t["maturityRating"] == "all"
    assert t["runtimeSeconds"] == 45 * 60
    assert t["media"]["hls"].endswith(".m3u8")
    assert "cells" in t["genres"]


def test_mrss_feed_is_valid_xml_with_media():
    _seed()
    res = client.get("/catalog/export", params={"format": "mrss"})
    assert res.headers["content-type"].startswith("application/rss+xml")
    body = res.text
    assert body.startswith("<?xml")
    assert "xmlns:media=" in body
    assert "<media:content" in body and ".m3u8" in body
    assert "<media:thumbnail" in body
    # Parses as well-formed XML.
    import xml.etree.ElementTree as ET
    ET.fromstring(body)
