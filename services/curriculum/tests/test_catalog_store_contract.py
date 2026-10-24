"""One contract, two implementations: the in-memory store and the Postgres store must agree."""

from __future__ import annotations

import pytest

from curriculum.catalog import CatalogStore, Course, DeliveryMode, Module, Program, decode_cursor


@pytest.fixture(params=["memory", "postgres"])
def store(request):
    if request.param == "memory":
        return CatalogStore()
    return request.getfixturevalue("pg_store")


def _course(i: int, **kw) -> Course:
    base = dict(
        course_id=f"c{i:04d}", title=f"Course {i} algebra" if i % 2 == 0 else f"Course {i} biology",
        subject="math" if i % 2 == 0 else "science", language="en" if i % 3 else "es",
        popularity=i % 7, tags=["harvest", "tier:0", "license:product_safe"],
        modules=[Module(title=f"L{j}", deck_id=f"obj:{(i * 10 + j):064x}", order=j) for j in range(3)],
    )
    base.update(kw)
    return Course(**base)


def test_create_get_delete_roundtrip(store):
    c = store.create_course(_course(1))
    assert store.get_course(c.course_id).title == c.title
    assert store.delete_course(c.course_id) is True
    assert store.get_course(c.course_id) is None
    assert store.delete_course(c.course_id) is False


def test_same_content_is_not_created_twice(store):
    a = store.create_course(_course(1, course_id="first"), dedupe=True)
    b = store.create_course(_course(1, course_id="second"), dedupe=True)
    assert b.course_id == a.course_id == "first"
    assert store.count_courses()[0] == 1


def test_replacing_by_course_id_updates_in_place(store):
    store.create_course(_course(1, title="Old title"))
    store.create_course(_course(1, title="New title", modules=[Module(title="only", deck_id="d9")]))
    assert store.get_course("c0001").title == "New title"
    assert store.count_courses()[0] == 1


def test_keyset_paging_walks_every_course_once_in_stable_order(store):
    for i in range(1, 26):
        store.create_course(_course(i))
    seen, cursor, pages = [], None, 0
    while True:
        items, cursor = store.page_courses(limit=10, cursor=cursor)
        seen += [c.course_id for c in items]
        pages += 1
        if not cursor:
            break
        assert pages < 10
    assert len(seen) == 25 and len(set(seen)) == 25 and pages == 3
    order = [(store.get_course(c).popularity, c) for c in seen]
    assert order == sorted(order, reverse=True)  # popularity desc, then course_id desc


def test_paging_survives_writes_between_pages(store):
    for i in range(1, 16):
        store.create_course(_course(i))
    first, cursor = store.page_courses(limit=5)
    store.create_course(_course(99, popularity=0, course_id="c0000"))  # sorts last: cannot shift page 2
    rest = []
    while cursor:
        items, cursor = store.page_courses(limit=5, cursor=cursor)
        rest += items
    assert not ({c.course_id for c in first} & {c.course_id for c in rest})


def test_bad_cursor_is_a_value_error(store):
    with pytest.raises(ValueError):
        store.page_courses(limit=5, cursor="not-a-cursor")
    with pytest.raises(ValueError):
        decode_cursor("!!")


def test_limit_is_clamped(store):
    for i in range(1, 6):
        store.create_course(_course(i))
    assert len(store.page_courses(limit=0)[0]) == 1
    assert len(store.page_courses(limit=10_000)[0]) == 5


def test_filters(store):
    store.create_course(_course(1, category="Maths", level="advanced", hands_on=True, audiences=["Nurse"], language="en"))
    store.create_course(_course(2, category="Biology", language="es", access_tier="pro"))
    store.create_course(_course(3, category="maths", tags=["Special"], maturity_rating="kids", language="en"))
    ids = lambda **kw: sorted(c.course_id for c in store.page_courses(limit=50, **kw)[0])  # noqa: E731
    assert ids(category="MATHS") == ["c0001", "c0003"]
    assert ids(language="es") == ["c0002"]
    assert ids(level="advanced") == ["c0001"]
    assert ids(hands_on=True) == ["c0001"]
    assert ids(access_tier="pro") == ["c0002"]
    assert ids(tag="special") == ["c0003"]
    assert ids(maturity="kids") == ["c0003"]
    assert ids(audience="nurse") == ["c0001"]
    assert ids(category="maths", language="en") == ["c0001", "c0003"]
    assert ids(category="nothing") == []


def test_text_search_finds_title_and_description(store):
    store.create_course(_course(1, title="Intro to Photosynthesis", description="plants make sugar"))
    store.create_course(_course(2, title="Linear algebra"))
    assert [c.course_id for c in store.page_courses(limit=10, q="photosynthesis")[0]] == ["c0001"]
    assert [c.course_id for c in store.page_courses(limit=10, q="sugar")[0]] == ["c0001"]
    assert store.page_courses(limit=10, q="zzzz-nothing")[0] == []


def test_count_courses(store):
    for i in range(1, 8):
        store.create_course(_course(i))
    n, capped = store.count_courses()
    assert (n, capped) == (7, False)
    assert store.count_courses(language="es")[0] == len([i for i in range(1, 8) if i % 3 == 0])


def test_unpublished_courses_are_not_listed(store):
    store.create_course(_course(1))
    store.create_course(_course(2, lifecycle_state="draft"))
    store.create_course(_course(3, lifecycle_state="retired"))
    assert [c.course_id for c in store.page_courses(limit=10)[0]] == ["c0001"]


def test_bump_popularity_changes_order(store):
    for i in (1, 2, 3):
        store.create_course(_course(i, popularity=0))
    assert store.bump_popularity("c0001", 5).popularity == 5
    assert store.bump_popularity("nope") is None
    assert store.page_courses(limit=10)[0][0].course_id == "c0001"


def test_patch_course_only_touches_playable_media_fields(store):
    store.create_course(_course(1))
    patched = store.patch_course("c0001", trailer_url="https://x/t.mp4", title="HACK", media_format="video")
    assert patched.trailer_url == "https://x/t.mp4" and patched.title != "HACK"
    assert store.get_course("c0001").trailer_url == "https://x/t.mp4"
    assert store.patch_course("nope", trailer_url="x") is None


def test_programs_crud(store):
    p = store.create_program(Program(program_id="p1", title="Starter", course_ids=["c1"]))
    assert store.get_program("p1").title == "Starter"
    store.create_program(Program(program_id="p1", title="Renamed"))  # same id replaces
    assert [x.title for x in store.list_programs()] == ["Renamed"]
    assert store.delete_program("p1") is True and store.delete_program("p1") is False
    assert p.program_id == "p1"


def test_kids_and_rails(store):
    for i in range(1, 6):
        store.create_course(_course(i, maturity_rating="kids" if i == 1 else "all", category="Art",
                                    access_tier="free", hands_on=(i == 2)))
    assert [c.course_id for c in store.kids_safe()] == ["c0001"]
    rails = {r["key"]: r for r in store.home_rails(per_rail=2)}
    assert {"popular", "new", "free", "hands_on", "kids", "cat:Art"} <= set(rails)
    assert all(len(r["courses"]) <= 2 for r in rails.values())
    kids = {r["key"] for r in store.home_rails(kids_only=True)}
    assert "kids" not in kids and "popular" in kids


def test_delivery_mode_roundtrip(store):
    store.create_course(_course(1, delivery_mode=DeliveryMode.HYBRID))
    assert store.get_course("c0001").delivery_mode == DeliveryMode.HYBRID
    assert [c.course_id for c in store.page_courses(limit=5, delivery_mode="hybrid")[0]] == ["c0001"]


# ----------------------------------------------------------------- Postgres-only guarantees
def test_pg_quarantines_non_product_licenses(pg_store):
    pg_store.create_course(_course(1, tags=["license:research_only", "tier:0"]))
    pg_store.create_course(_course(2, tags=["license:unknown"]))
    pg_store.create_course(_course(3, tags=["license:share_alike"]))
    pg_store.create_course(_course(4, tags=["license:product_safe"]))
    assert [c.course_id for c in pg_store.page_courses(limit=10)[0]] == ["c0004"]
    assert pg_store.get_course("c0001") is None  # invisible by id too
    assert pg_store.get_course("c0001", include_hidden=True) is not None  # admin tooling can still see it


def test_pg_share_alike_needs_explicit_opt_in(pg_dsn):
    from curriculum.catalog_pg import PgCatalogStore

    store = PgCatalogStore(pg_dsn, cache_ttl=0, allow_share_alike=True)
    try:
        with store.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("TRUNCATE catalog_courses CASCADE")
        store.create_course(_course(3, tags=["license:share_alike"]))
        assert [c.course_id for c in store.page_courses(limit=10)[0]] == ["c0003"]
    finally:
        store.close()


def test_pg_bulk_insert_is_idempotent_and_never_overwrites(pg_store):
    courses = [_course(i) for i in range(1, 21)]
    assert pg_store.bulk_insert(courses) == (20, 0)
    assert pg_store.bulk_insert(courses) == (0, 20)
    changed = _course(1, title="Rewritten", description="x")
    assert pg_store.bulk_insert([changed]) == (0, 1)
    assert pg_store.get_course("c0001").title == "Course 1 biology"
    with pg_store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM catalog_modules")
        assert cur.fetchone()[0] == 60


def test_pg_bulk_insert_writes_provenance(pg_store):
    c = _course(1)
    sha = c.modules[0].deck_id[4:]
    pg_store.bulk_insert([c], {c.course_id: [{"deck_sha256": sha, "source_url": "https://x.example/a",
                                              "license": "cc-by-4.0", "license_tier": "product_safe",
                                              "attribution": {"author": "A"}, "fetched_at": "2026-10-24"}]})
    with pg_store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT license, license_tier, attribution FROM catalog_sources WHERE course_id = %s", (c.course_id,))
        assert cur.fetchone() == ("cc-by-4.0", "product_safe", {"author": "A"})
        cur.execute("SELECT deck_sha256 FROM catalog_modules WHERE course_id = %s ORDER BY ordering LIMIT 1", (c.course_id,))
        assert cur.fetchone()[0] == sha


def test_pg_two_stores_share_one_truth(pg_dsn, pg_store):
    """Two replicas never diverge: a write through one is visible through the other."""
    from curriculum.catalog_pg import PgCatalogStore

    other = PgCatalogStore(pg_dsn, cache_ttl=0)
    try:
        pg_store.create_course(_course(1))
        assert other.get_course("c0001") is not None
        other.delete_course("c0001")
        assert pg_store.get_course("c0001") is None
    finally:
        other.close()


def test_pg_read_cache_is_bounded_by_ttl_and_dropped_on_local_write(pg_dsn):
    from curriculum.catalog_pg import PgCatalogStore

    a = PgCatalogStore(pg_dsn, cache_ttl=60)
    b = PgCatalogStore(pg_dsn, cache_ttl=0)
    try:
        with a.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("TRUNCATE catalog_courses CASCADE")
        a.create_course(_course(1, title="v1"))
        assert a.get_course("c0001").title == "v1"          # now cached on a
        b.create_course(_course(1, title="v2"))              # another replica edits it
        assert a.get_course("c0001").title == "v1"           # stale until the TTL: documented window
        a.create_course(_course(1, title="v3"))              # a local write drops the local entry
        assert a.get_course("c0001").title == "v3"
    finally:
        a.close()
        b.close()


def test_pg_concurrent_identical_posts_create_one_course(pg_dsn, pg_store):
    import threading

    from curriculum.catalog_pg import PgCatalogStore

    stores = [PgCatalogStore(pg_dsn, cache_ttl=0, max_size=2) for _ in range(4)]
    results: list[str] = []

    def post(s, n):
        results.append(s.create_course(_course(1, course_id=f"racer{n}")).course_id)

    try:
        threads = [threading.Thread(target=post, args=(s, n)) for n, s in enumerate(stores)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert len(set(results)) == 1
        assert pg_store.count_courses()[0] == 1
    finally:
        for s in stores:
            s.close()


def test_pg_text_search_is_relevance_ranked_and_offset_capped(pg_store):
    pg_store.create_course(_course(1, title="Algebra", popularity=0))
    pg_store.create_course(_course(2, title="Cooking", description="algebra of flavors", popularity=99))
    got = [c.course_id for c in pg_store.page_courses(limit=5, q="algebra")[0]]
    assert got[0] == "c0001"  # title match outranks a description match even with fewer views
    assert pg_store.page_courses(limit=5, q="algebra", offset=10**9)[0] == []  # clamped, not an error
