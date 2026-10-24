"""Shared Postgres fixtures for the catalog tests.

CATALOG_TEST_DSN points at a throwaway database; otherwise a disposable postgres:16 container is
started with docker (skipped, not failed, when neither exists or psycopg is not installed).
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time

import pytest


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def pg_dsn():
    pytest.importorskip("psycopg")
    pytest.importorskip("psycopg_pool")
    from aoep_shared.catalog_db import migrate

    dsn = os.environ.get("CATALOG_TEST_DSN")
    container = None
    if not dsn:
        if not shutil.which("docker"):
            pytest.skip("set CATALOG_TEST_DSN or install docker to run the Postgres catalog tests")
        port = _free_port()
        container = f"catalog-pg-test-{os.getpid()}"
        started = subprocess.run(
            ["docker", "run", "-d", "--rm", "--name", container, "-e", "POSTGRES_PASSWORD=pw",
             "-e", "POSTGRES_DB=catalog", "-p", f"127.0.0.1:{port}:5432", "postgres:16"],
            capture_output=True, text=True,
        )
        if started.returncode != 0:
            pytest.skip(f"could not start postgres in docker: {started.stderr.strip()[:200]}")
        dsn = f"postgresql://postgres:pw@127.0.0.1:{port}/catalog"
    import psycopg

    deadline = time.time() + 90
    while True:
        try:
            psycopg.connect(dsn, connect_timeout=2).close()
            break
        except Exception:
            if time.time() > deadline:
                if container:
                    subprocess.run(["docker", "rm", "-f", container], capture_output=True)
                pytest.skip("postgres did not become ready")
            time.sleep(1)
    conn = migrate.connect(dsn)
    report = migrate.migrate(conn)
    conn.close()
    assert report.ok, report.problems
    yield dsn
    if container:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)


@pytest.fixture()
def pg_store(pg_dsn):
    from curriculum.catalog_pg import PgCatalogStore

    store = PgCatalogStore(pg_dsn, max_size=4, cache_ttl=0, hot_cap=50)
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE catalog_courses, catalog_programs, catalog_facets CASCADE")
    yield store
    store.close()
