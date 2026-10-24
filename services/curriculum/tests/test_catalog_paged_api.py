"""The curriculum API on top of the shared Postgres catalog (only when a database is available)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from curriculum.catalog import CatalogStore, Course, Module
from curriculum.main import app


@pytest.fixture()
def paged_client(pg_dsn):
    from curriculum.catalog_pg import PgCatalogStore

    store = PgCatalogStore(pg_dsn, cache_ttl=0, hot_cap=50)
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE catalog_courses, catalog_programs, catalog_facets CASCADE")
    previous = app.state.catalog
    app.state.catalog = store
    try:
        yield TestClient(app), store
    finally:
        app.state.catalog = previous
        store.close()


def _seed(store, n=30):
    store.bulk_insert([
        Course(course_id=f"p{i:03d}", title=f"Paged course {i}", subject="math", category="Maths",
               popularity=i, tags=["license:product_safe", "tier:0"],
               modules=[Module(title="L1", deck_id=f"obj:{i:064x}")])
        for i in range(n)
    ])


def test_courses_list_pages_with_cursor_and_headers(paged_client):
    client, store = paged_client
    _seed(store, 30)
    first = client.get("/courses?limit=10")
    assert first.status_code == 200 and len(first.json()) == 10
    assert first.headers["X-Total-Count"] == "30" and first.headers["X-Limit"] == "10"
    cursor = first.headers["X-Next-Cursor"]
    seen = [c["course_id"] for c in first.json()]
    while cursor:
        page = client.get(f"/courses?limit=10&cursor={cursor}")
        seen += [c["course_id"] for c in page.json()]
        cursor = page.headers.get("X-Next-Cursor")
    assert len(seen) == 30 and len(set(seen)) == 30
    assert client.get("/courses?cursor=garbage").status_code == 422


def test_post_courses_is_idempotent_through_the_api(paged_client):
    client, store = paged_client
    body = {"title": "Same course", "subject": "math", "modules": [{"title": "L1", "deck_id": "d1"}]}
    a = client.post("/courses", json=body).json()
    b = client.post("/courses", json=body).json()  # a client retry
    assert a["course_id"] == b["course_id"]
    assert store.count_courses()[0] == 1


def test_course_detail_has_etag_and_revalidates(paged_client):
    client, store = paged_client
    _seed(store, 3)
    r = client.get("/courses/p001")
    etag = r.headers["ETag"]
    assert r.status_code == 200 and "max-age" in r.headers["Cache-Control"]
    again = client.get("/courses/p001", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.headers["ETag"] == etag
    store.patch_course("p001", trailer_url="https://x.example/t.mp4")
    changed = client.get("/courses/p001", headers={"If-None-Match": etag})
    assert changed.status_code == 200 and changed.headers["ETag"] != etag


def test_search_merges_learnable_items_then_catalog_and_pages_consistently(paged_client):
    client, store = paged_client
    _seed(store, 25)
    everything = []
    offset = 0
    while True:
        page = client.get(f"/courses/search?limit=20&offset={offset}")
        assert page.status_code == 200
        rows = page.json()
        everything += [c["course_id"] for c in rows]
        offset += 20
        if len(rows) < 20:
            break
        assert offset < 10_000
    mine = [c for c in everything if c.startswith("p0")]
    assert len(mine) == len(set(mine)) == 25  # every catalog course reachable exactly once across both segments
    total = int(client.get("/courses/search?limit=1").headers["X-Total-Count"])
    assert total == len(everything)


def test_search_filters_reach_the_database(paged_client):
    client, store = paged_client
    _seed(store, 12)
    r = client.get("/courses/search?source=&category=Maths&language=en&limit=50")
    ids = {c["course_id"] for c in r.json()}
    assert {f"p{i:03d}" for i in range(12)} <= ids


def test_deck_bodies_resolve_from_object_storage(paged_client, tmp_path, monkeypatch):
    import gzip

    from aoep_shared.harvest.objectstore import LocalObjectStore, canonical_bytes, content_sha256, course_key

    client, _ = paged_client
    store = LocalObjectStore(tmp_path)
    body = {"title": "Cells", "language": "en", "slides": [{"title": "S1", "body": "b", "narration": "n"}]}
    sha = content_sha256(canonical_bytes(body))
    store.put(course_key(sha), gzip.compress(canonical_bytes(body), mtime=0))
    monkeypatch.setenv("OBJECT_STORE_DIR", str(tmp_path))
    app.state.body_loader = None
    got = client.get(f"/decks/obj:{sha}")
    assert got.status_code == 200 and got.json()["slides"][0]["narration"] == "n"
    assert client.get(f"/decks/obj:{'0' * 64}").status_code == 404
    pres = client.get(f"/decks/obj:{sha}/presentation").json()
    assert pres["slides"][0]["index"] == 0
    app.state.body_loader = None


def test_unset_database_url_keeps_the_in_memory_store(monkeypatch):
    from curriculum.catalog import make_catalog_store

    monkeypatch.delenv("CATALOG_DATABASE_URL", raising=False)
    assert type(make_catalog_store()) is CatalogStore


def test_unreachable_database_falls_back_unless_required(monkeypatch):
    from curriculum.catalog import make_catalog_store

    monkeypatch.setenv("CATALOG_DATABASE_URL", "postgresql://nobody:x@127.0.0.1:9/none?connect_timeout=1")
    assert type(make_catalog_store()) is CatalogStore  # logged loudly, service still starts
    monkeypatch.setenv("CATALOG_DB_REQUIRED", "1")
    with pytest.raises(Exception):
        make_catalog_store()
