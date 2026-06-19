"""Ad-break endpoint (tier-gated VMAP/VAST)."""

import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient

from curriculum.catalog import CatalogStore
from curriculum.main import app

client = TestClient(app)


def _seed_course():
    app.state.catalog = CatalogStore()
    res = client.post("/courses", json={
        "title": "Long Lecture", "subject": "history", "duration_min": 45,
    })
    return res.json()["course_id"]


def test_free_tier_gets_ads():
    cid = _seed_course()
    data = client.get(f"/courses/{cid}/ad-breaks", params={"tier": "free"}).json()
    assert data["ad_free"] is False
    assert data["breaks"][0]["position"] == "preroll"
    assert any(b["position"] == "midroll" for b in data["breaks"])


def test_pro_tier_is_ad_free():
    cid = _seed_course()
    data = client.get(f"/courses/{cid}/ad-breaks", params={"tier": "pro"}).json()
    assert data["ad_free"] is True
    assert data["breaks"] == []


def test_vmap_format_returns_xml():
    cid = _seed_course()
    res = client.get(f"/courses/{cid}/ad-breaks", params={"tier": "free", "format": "vmap"})
    assert res.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(res.text)
    assert root.tag.endswith("VMAP")


def test_unknown_course_404():
    _seed_course()
    assert client.get("/courses/nope/ad-breaks").status_code == 404
