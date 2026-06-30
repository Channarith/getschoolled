"""Persistent embedded knowledge store (SQLite) tests."""

from pathlib import Path

from aoep_shared.training_agents.knowledge_store import KnowledgeStore


def test_store_builds_persistent_sqlite_file(tmp_path):
    db = tmp_path / "kb.db"
    store = KnowledgeStore(db)
    assert store.backend == "sqlite"
    assert store.persistent is True
    assert db.is_file()
    assert store.total() >= 60


def test_store_survives_reopen(tmp_path):
    db = tmp_path / "kb.db"
    first = KnowledgeStore(db)
    n = first.total()
    # Reopen a fresh store object against the same file — data persists.
    second = KnowledgeStore(db)
    assert second.total() == n
    assert second.backend == "sqlite"


def test_store_search_and_filter(tmp_path):
    store = KnowledgeStore(tmp_path / "kb.db")
    marine = store.search(domain="marine", limit=100)
    assert marine
    assert all(r["fact"] and r["source"] and r["reference"] for r in marine)

    cpr = store.search(q="compressions", limit=10)
    assert any("100" in r["fact"] for r in cpr)

    regs = store.search(category="regulation", limit=100)
    assert all(r["category"] == "regulation" for r in regs)


def test_store_sources_and_status(tmp_path):
    store = KnowledgeStore(tmp_path / "kb.db")
    sources = store.sources()
    names = {s["source"] for s in sources}
    assert any("NHTSA" in n for n in names)
    assert any("FAA" in n for n in names)

    status = store.status()
    assert status["backend"] == "sqlite"
    assert status["persistent"] is True
    assert status["count"] >= 60
    assert status["db_path"].endswith("kb.db")


def test_store_rebuilds_when_stale(tmp_path):
    db = tmp_path / "kb.db"
    store = KnowledgeStore(db)
    # Corrupt the stored signature so the next open detects staleness.
    import sqlite3

    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE kb_meta SET value='0|stale' WHERE key='signature'")
    conn.commit()
    conn.close()

    reopened = KnowledgeStore(db)
    assert reopened.total() >= 60
    assert reopened.status()["signature"] != "0|stale"


def test_store_falls_back_to_memory_on_unwritable_path():
    # A path under a non-existent, unwritable root forces the memory fallback.
    store = KnowledgeStore(Path("/proc/nonexistent_dir/kb.db"))
    assert store.backend == "memory"
    assert store.persistent is False
    assert store.total() >= 60
    assert store.search(domain="aviation", limit=5)
