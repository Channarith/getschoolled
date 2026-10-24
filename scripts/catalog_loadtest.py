#!/usr/bin/env python3
"""Load test the Postgres catalog with synthetic multi-lesson courses and report real numbers.

  docker run -d --name catalog-pg -e POSTGRES_PASSWORD=pw -e POSTGRES_DB=catalog -p 55432:5432 \\
      --shm-size=1g postgres:16 -c shared_buffers=1GB -c max_wal_size=8GB -c synchronous_commit=off
  python3 scripts/catalog_loadtest.py --dsn postgresql://postgres:pw@localhost:55432/catalog \\
      --courses 1000000 --modules 8 --out runs/catalog-loadtest.json

What it does: migrates the schema, loads N courses (each with M lessons, provenance rows) through
PgCatalogStore.bulk_insert (COPY), rebuilds the indexes, then measures p50/p95/p99 latency for get,
browse (keyset), deep paging, filters, text search, counts, rails, facets, a 16-thread mixed run,
and steady-state insert speed with every index in place. Prints table and index sizes.

SYNTHETIC DATA: titles, categories and languages are random but shaped like the real catalog
(27 languages with a heavy head, popularity with a heavy tail, ~1.5-2.5 KB of JSON per course).
Run it on the hardware you intend to use: numbers from a laptop VM are a lower bound for a small VPS
only in the sense of CPU/disk differences, not a guarantee.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
sys.path.insert(0, str(ROOT / "services" / "curriculum" / "src"))

from aoep_shared.catalog_db import migrate  # noqa: E402
from curriculum.catalog import Course, Module  # noqa: E402
from curriculum.catalog_pg import PgCatalogStore  # noqa: E402

TOPICS = (
    "algebra geometry calculus statistics biology chemistry physics astronomy geology ecology anatomy genetics "
    "history geography economics civics philosophy ethics logic rhetoric grammar poetry fiction drama music "
    "painting sculpture photography cooking baking nutrition fitness yoga first-aid driving cycling sailing "
    "gardening beekeeping woodworking plumbing electronics robotics python javascript databases networking "
    "security cryptography accounting marketing negotiation leadership entrepreneurship finance investing "
    "taxes insurance law contracts privacy parenting teaching writing editing translation linguistics khmer "
    "vietnamese thai spanish mandarin swahili bengali hindi arabic"
).split()
ADJ = "Introduction Fundamentals Essentials Advanced Practical Complete Modern Applied Beginner Concepts".split()
CATEGORIES = [f"cat-{i:02d}" for i in range(40)]
LANGS = ("en es vi th zh km sw id el cs fr de ja pt it tr pl hi ar bn ur uk ru he fa ko nl").split()
LEVELS = ["beginner", "intermediate", "advanced"]


def make_course(i: int, rnd: random.Random, modules: int) -> Course:
    topic = TOPICS[rnd.randrange(len(TOPICS))]
    topic2 = TOPICS[rnd.randrange(len(TOPICS))]
    lang = LANGS[min(int(rnd.paretovariate(1.1)) - 1, len(LANGS) - 1)]
    cat = CATEGORIES[rnd.randrange(len(CATEGORIES))]
    sha = f"{i:064x}"
    body = (f"{ADJ[rnd.randrange(len(ADJ))]} {topic} for {topic2} learners. " * 6)[:300]
    return Course(
        course_id=f"lt{i:07x}",
        title=f"{ADJ[i % len(ADJ)]} {topic.title()} and {topic2.title()} ({i})",
        subject=topic,
        category=cat,
        language=lang,
        description=body,
        preview=body[:160],
        level=LEVELS[rnd.randrange(3)],
        media_format="text",
        duration_min=rnd.randrange(30, 400),
        popularity=int(rnd.paretovariate(1.2) * 10),
        hands_on=rnd.random() < 0.08,
        access_tier="free" if rnd.random() < 0.7 else "pro",
        maturity_rating="kids" if rnd.random() < 0.05 else "all",
        tags=["harvest", "license:product_safe", "tier:0", topic, f"sha:{sha[:16]}", f"source:site{i % 500}.example"],
        source="harvest",
        source_fingerprint=sha,
        modules=[
            Module(title=f"Lesson {j + 1}: {topic} part {j + 1}", deck_id=f"obj:{(i * modules + j):064x}", order=j,
                   module_id=f"m{j + 1}")
            for j in range(modules)
        ],
    )


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))]


def timed(fn, n: int) -> dict:
    ms: list[float] = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        ms.append((time.perf_counter() - t) * 1000)
    return {"n": n, "p50_ms": round(pct(ms, 50), 2), "p95_ms": round(pct(ms, 95), 2),
            "p99_ms": round(pct(ms, 99), 2), "mean_ms": round(statistics.mean(ms), 2)}


def sizes(store: PgCatalogStore) -> dict:
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_size_pretty(pg_database_size(current_database())), pg_database_size(current_database())")
        pretty, raw = cur.fetchone()
        cur.execute(
            "SELECT relname, pg_total_relation_size(oid) FROM pg_class WHERE relname IN "
            "('catalog_courses','catalog_modules','catalog_sources','catalog_translations') ORDER BY 2 DESC"
        )
        tables = {r[0]: int(r[1]) for r in cur.fetchall()}
        cur.execute(
            "SELECT c.relname, pg_relation_size(c.oid) FROM pg_class c JOIN pg_index i ON i.indexrelid = c.oid "
            "JOIN pg_class t ON t.oid = i.indrelid WHERE t.relname = 'catalog_courses' ORDER BY 2 DESC"
        )
        indexes = {r[0]: int(r[1]) for r in cur.fetchall()}
    return {"database": pretty, "database_bytes": int(raw), "tables_incl_indexes_bytes": tables,
            "catalog_courses_indexes_bytes": indexes}


INDEX_DDL_SQL = None


def index_statements(store: PgCatalogStore) -> list[tuple[str, str]]:
    """(name, CREATE statement) for every secondary index on catalog_courses, read from pg itself."""
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'catalog_courses' "
            "AND indexname NOT IN ('catalog_courses_pkey', 'ux_catalog_courses_content_hash')"
        )
        return [(r[0], r[1]) for r in cur.fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", default=os.environ.get("CATALOG_DATABASE_URL", ""))
    ap.add_argument("--courses", type=int, default=100_000)
    ap.add_argument("--modules", type=int, default=8)
    ap.add_argument("--batch", type=int, default=2000)
    ap.add_argument("--reset", action="store_true", help="TRUNCATE the catalog tables first")
    ap.add_argument("--skip-load", action="store_true", help="measure queries on what is already there")
    ap.add_argument("--keep-indexes", action="store_true", help="load with all indexes in place (slower)")
    ap.add_argument("--queries", type=int, default=200)
    ap.add_argument("--mixed-seconds", type=int, default=20)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if not args.dsn:
        print("pass --dsn", file=sys.stderr)
        return 2

    conn = migrate.connect(args.dsn)
    rep = migrate.migrate(conn)
    conn.close()
    if not rep.ok:
        print(rep.problems, file=sys.stderr)
        return 1
    store = PgCatalogStore(args.dsn, max_size=max(8, args.threads), cache_ttl=0, hot_cap=2000)
    result: dict = {"courses_requested": args.courses, "modules_per_course": args.modules}

    if args.reset and not args.skip_load:
        with store.pool.connection() as c, c.cursor() as cur:
            cur.execute("TRUNCATE catalog_courses, catalog_programs, catalog_facets CASCADE")

    if not args.skip_load:
        rnd = random.Random(42)
        idx = [] if args.keep_indexes else index_statements(store)
        t_drop = time.perf_counter()
        with store.pool.connection() as c, c.cursor() as cur:
            for name, _ in idx:
                cur.execute(f'DROP INDEX IF EXISTS "{name}"')
        gen_s = ins_s = 0.0
        done = 0
        t0 = time.perf_counter()
        while done < args.courses:
            n = min(args.batch, args.courses - done)
            tg = time.perf_counter()
            courses = [make_course(done + k, rnd, args.modules) for k in range(n)]
            sources = {c.course_id: [{"deck_sha256": m.deck_id[4:], "source_url": f"https://site{(done) % 500}.example/p/{k}",
                                      "license": "cc-by-4.0", "license_tier": "product_safe",
                                      "attribution": {"author": "Example"}, "fetched_at": "2026-10-24"}
                                     for k, m in enumerate(c.modules)] for c in courses}
            gen_s += time.perf_counter() - tg
            ti = time.perf_counter()
            store.bulk_insert(courses, sources)
            ins_s += time.perf_counter() - ti
            done += n
            if done % (args.batch * 25) == 0 or done == args.courses:
                el = time.perf_counter() - t0
                print(f"  loaded {done:,}/{args.courses:,} courses  {done / el:,.0f}/s  elapsed {el:,.0f}s", flush=True)
        load_s = time.perf_counter() - t0
        t_idx = time.perf_counter()
        with store.pool.connection() as c, c.cursor() as cur:
            cur.execute("SET maintenance_work_mem = '1GB'")
            for name, ddl in idx:
                ts = time.perf_counter()
                cur.execute(ddl)
                print(f"  rebuilt index {name} in {time.perf_counter() - ts:,.1f}s", flush=True)
            cur.execute("SELECT catalog_refresh_facets()")
            cur.execute("ANALYZE")
        result["load"] = {
            "courses": done, "modules": done * args.modules, "indexes_deferred": not args.keep_indexes,
            "generate_seconds": round(gen_s, 1), "copy_seconds": round(ins_s, 1),
            "total_load_seconds": round(load_s, 1), "courses_per_second_copy_only": round(done / max(ins_s, 1e-9)),
            "courses_per_second_end_to_end": round(done / load_s), "index_rebuild_seconds": round(time.perf_counter() - t_idx, 1),
        }
    result["sizes"] = sizes(store)
    with store.pool.connection() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM catalog_courses")
        total = int(cur.fetchone()[0])
        cur.execute("SELECT course_id FROM catalog_courses TABLESAMPLE SYSTEM (0.05) LIMIT 5000")
        ids = [r[0] for r in cur.fetchall()] or ["lt0000000"]
    result["rows"] = total
    rnd2 = random.Random(7)
    q = args.queries

    def cursor_after(pages: int):
        cur_c = None
        for _ in range(pages):
            items, cur_c = store.page_courses(limit=50, cursor=cur_c)
            if not cur_c:
                break
        return cur_c

    deep = cursor_after(200)  # a cursor ~10,000 rows deep
    bench = {
        "get_by_id": timed(lambda: store.get_course(rnd2.choice(ids)), q * 5),
        "browse_first_page_50": timed(lambda: store.page_courses(limit=50), q),
        "browse_deep_keyset_10k": timed(lambda: store.page_courses(limit=50, cursor=deep), q),
        "browse_offset_5000": timed(lambda: store.page_courses(limit=50, offset=5000), q),
        "filter_category": timed(lambda: store.page_courses(limit=50, category=rnd2.choice(CATEGORIES)), q),
        "filter_language_km": timed(lambda: store.page_courses(limit=50, language="km"), q),
        "filter_language_en": timed(lambda: store.page_courses(limit=50, language="en"), q),
        "filter_tag": timed(lambda: store.page_courses(limit=50, tag=rnd2.choice(TOPICS)), q),
        "filter_category_language_level": timed(
            lambda: store.page_courses(limit=50, category=rnd2.choice(CATEGORIES), language="en", level="beginner"), q),
        "search_one_word": timed(lambda: store.page_courses(limit=20, q=rnd2.choice(TOPICS)), q),
        "search_two_words": timed(lambda: store.page_courses(limit=20, q=f"{rnd2.choice(TOPICS)} {rnd2.choice(TOPICS)}"), q),
        "search_prefix_like": timed(lambda: store.page_courses(limit=20, q=rnd2.choice(TOPICS)[:5]), q),
        "count_filtered_capped": timed(lambda: store.count_courses(category=rnd2.choice(CATEGORIES)), q),
        "count_all_capped": timed(lambda: store.count_courses(), q),
        "home_rails": timed(lambda: store.home_rails(), max(20, q // 5)),
        "facet_counts": timed(lambda: store.facet_counts(), q),
    }
    result["latency"] = bench

    stop = time.time() + args.mixed_seconds
    lat: list[float] = []
    errors = [0]
    lock = threading.Lock()

    def worker(seed: int) -> None:
        r = random.Random(seed)
        while time.time() < stop:
            t = time.perf_counter()
            try:
                roll = r.random()
                if roll < 0.5:
                    store.get_course(r.choice(ids))
                elif roll < 0.75:
                    store.page_courses(limit=50, category=r.choice(CATEGORIES))
                elif roll < 0.9:
                    store.page_courses(limit=20, q=r.choice(TOPICS))
                else:
                    store.page_courses(limit=50)
            except Exception:
                with lock:
                    errors[0] += 1
                continue
            with lock:
                lat.append((time.perf_counter() - t) * 1000)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(args.threads)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0
    result["mixed_read_load"] = {
        "threads": args.threads, "seconds": round(wall, 1), "requests": len(lat), "errors": errors[0],
        "requests_per_second": round(len(lat) / wall), "p50_ms": round(pct(lat, 50), 2),
        "p95_ms": round(pct(lat, 95), 2), "p99_ms": round(pct(lat, 99), 2),
    }

    # steady-state writes with every index in place
    rnd3 = random.Random(99)
    base = total + 10_000_000
    t = time.perf_counter()
    inserted = skipped = 0
    for b in range(5):
        batch = [make_course(base + b * 2000 + k, rnd3, args.modules) for k in range(2000)]
        i2, s2 = store.bulk_insert(batch)
        inserted += i2
        skipped += s2
    bulk_s = time.perf_counter() - t
    single = []
    for k in range(300):
        c = make_course(base + 50_000 + k, rnd3, args.modules)
        ts = time.perf_counter()
        store.create_course(c)
        single.append((time.perf_counter() - ts) * 1000)
    ids_for_bump = ids[:200]
    bump = timed(lambda: store.bump_popularity(rnd3.choice(ids_for_bump)), 300)
    result["writes_with_all_indexes"] = {
        "bulk_courses_per_second": round(inserted / bulk_s), "bulk_inserted": inserted,
        "single_create_p50_ms": round(pct(single, 50), 2), "single_create_p95_ms": round(pct(single, 95), 2),
        "bump_popularity": bump,
    }
    # idempotency check at scale
    again = [make_course(base + k, random.Random(99), args.modules) for k in range(10)]
    result["rerun_same_courses_inserts"] = store.bulk_insert(again)[0]
    store.close()
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
