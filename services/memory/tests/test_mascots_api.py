"""Memory service mascot endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from memory.main import app

client = TestClient(app)
ADMIN = {"X-Admin-Secret": "dev-admin-secret"}


def test_mascots_catalog():
    r = client.get("/mascots/catalog")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 27
    assert len(body["mascots"]) == 27
    assert body["mascots"][0]["path"].startswith("/mascots/")


def test_mascots_resolve_follows_locale():
    r = client.get("/mascots/resolve", params={"locale": "vi"})
    assert r.status_code == 200
    body = r.json()
    assert body["locale"] == "vi"
    assert body["path"] == "/mascots/vi.svg"
    assert body["enabled"] is True


def test_mascots_resolve_preview_locale_flag():
    client.put(
        "/admin/flags/ux.locale_mascots_preview_locale",
        json={"enabled": True, "value": "km"},
        headers=ADMIN,
    )
    r = client.get("/mascots/resolve", params={"locale": "en"})
    assert r.status_code == 200
    assert r.json()["locale"] == "km"
    client.put(
        "/admin/flags/ux.locale_mascots_preview_locale",
        json={"enabled": True, "value": "auto"},
        headers=ADMIN,
    )


def test_mascots_resolve_disabled_flag():
    client.put(
        "/admin/flags/ux.locale_mascots",
        json={"enabled": True, "value": False},
        headers=ADMIN,
    )
    r = client.get("/mascots/resolve", params={"locale": "ja"})
    assert r.status_code == 200
    assert r.json()["path"] == "/bayon-mark.webp"
    assert r.json()["enabled"] is False
    client.put(
        "/admin/flags/ux.locale_mascots",
        json={"enabled": True, "value": True},
        headers=ADMIN,
    )
