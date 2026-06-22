"""HTTP cache + ETag middleware + standard registry."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aoep_shared.http_cache import (
    CacheRegistry, CacheRule, install, standard_registry,
)


def _app(registry: CacheRegistry) -> FastAPI:
    app = FastAPI()

    @app.get("/audio/courses")
    def audio_courses() -> dict:
        return {"items": [1, 2, 3]}

    @app.post("/audio/courses")
    def post_audio_courses() -> dict:
        return {"created": True}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    install(app, registry, etag=True)
    return app


def test_cache_control_header_added_for_registered_get():
    client = TestClient(_app(standard_registry()))
    r = client.get("/audio/courses")
    assert r.status_code == 200
    cc = r.headers["cache-control"]
    assert "max-age=" in cc and "s-maxage=" in cc
    assert "Vary" in r.headers


def test_unregistered_path_has_no_cache_control():
    client = TestClient(_app(standard_registry()))
    r = client.get("/health")
    assert r.status_code == 200
    assert "cache-control" not in (h.lower() for h in r.headers.keys()) \
        or "max-age" not in r.headers.get("cache-control", "")


def test_post_is_not_cached():
    client = TestClient(_app(standard_registry()))
    r = client.post("/audio/courses")
    assert r.status_code == 200
    assert "max-age" not in r.headers.get("cache-control", "")


def test_etag_and_304_revalidation():
    client = TestClient(_app(standard_registry()))
    r1 = client.get("/audio/courses")
    etag = r1.headers["etag"]
    assert etag.startswith('"')
    r2 = client.get("/audio/courses", headers={"If-None-Match": etag})
    assert r2.status_code == 304
    assert r2.headers["etag"] == etag


def test_longest_prefix_wins():
    reg = CacheRegistry()
    reg.register("/a", CacheRule(max_age=10))
    reg.register("/a/b", CacheRule(max_age=999))
    rule = reg.match("/a/b/c")
    assert rule is not None and rule.max_age == 999


def test_disabled_etag_returns_no_etag():
    reg = standard_registry()
    app = FastAPI()

    @app.get("/audio/courses")
    def audio_courses() -> dict:
        return {"items": []}

    install(app, reg, etag=False)
    client = TestClient(app)
    r = client.get("/audio/courses")
    assert "etag" not in {h.lower() for h in r.headers.keys()}
