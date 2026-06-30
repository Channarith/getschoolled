"""Persistent embedded knowledge store (SQLite).

The authored corpus in ``knowledge_base.py`` is the canonical source of truth and
is always available in-process. This module additionally persists it to a
file-based SQLite database (the standard-library, zero-config embedded engine) so
the knowledge base is queryable and durable across restarts.

Design goals — "always available":
- Self-healing: the DB is (re)built deterministically from the corpus whenever it
  is missing or its stored signature no longer matches the corpus.
- Resilient: if the filesystem is read-only or SQLite cannot be opened, the store
  transparently falls back to an in-memory backend backed by the corpus, so reads
  never fail.
- Portable: the DB path is configurable via ``AOEP_KNOWLEDGE_DB`` and defaults to
  ``~/.cache/aoep/knowledge.db`` (matching the project's cache convention).

Full-text search uses SQLite FTS5 when the local build supports it, and falls
back to LIKE-based matching otherwise.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .knowledge_base import (
    ReferenceFact,
    corpus_signature,
    fact_to_dict,
    iter_facts_with_meta,
)

_SCHEMA_VERSION = 1


def default_db_path() -> Path:
    env = os.environ.get("AOEP_KNOWLEDGE_DB")
    if env:
        return Path(env)
    return Path(os.path.expanduser("~")) / ".cache" / "aoep" / "knowledge.db"


def _domains_blob(domains: Tuple[str, ...]) -> str:
    # Wrap in commas so 'road' matches via LIKE '%,road,%' without prefix bleed.
    return "," + ",".join(domains) + "," if domains else ","


def _fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp._fts_probe USING fts5(x)")
        conn.execute("DROP TABLE temp._fts_probe")
        return True
    except sqlite3.Error:
        return False


class KnowledgeStore:
    """SQLite-backed, self-healing knowledge store with in-memory fallback."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else default_db_path()
        self.backend = "sqlite"
        self.persistent = True
        self._fts = False
        self._lock = threading.RLock()
        self._memory_facts: Optional[List[Tuple[ReferenceFact, Tuple[str, ...], Tuple[str, ...]]]] = None
        self._ensure()

    # ----- lifecycle ----------------------------------------------------- #
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = self._connect()
        except (OSError, sqlite3.Error):
            self._fallback_to_memory()
            return
        try:
            with self._lock:
                if not self._is_current(conn):
                    self._build(conn)
            self.backend = "sqlite"
            self.persistent = True
        except sqlite3.Error:
            self._fallback_to_memory()
        finally:
            try:
                conn.close()
            except sqlite3.Error:
                pass

    def _fallback_to_memory(self) -> None:
        self.backend = "memory"
        self.persistent = False
        self._memory_facts = list(iter_facts_with_meta())

    def _is_current(self, conn: sqlite3.Connection) -> bool:
        try:
            row = conn.execute(
                "SELECT value FROM kb_meta WHERE key = 'signature'"
            ).fetchone()
        except sqlite3.Error:
            return False
        if row is None:
            return False
        want = f"{_SCHEMA_VERSION}|{corpus_signature()}"
        return row["value"] == want

    def _build(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            DROP TABLE IF EXISTS facts;
            DROP TABLE IF EXISTS kb_meta;
            CREATE TABLE kb_meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE facts (
                id INTEGER PRIMARY KEY,
                fact TEXT NOT NULL,
                source TEXT NOT NULL,
                reference TEXT NOT NULL,
                category TEXT NOT NULL,
                url TEXT NOT NULL DEFAULT '',
                domains TEXT NOT NULL DEFAULT ',',
                keywords TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX idx_facts_source ON facts(source);
            CREATE INDEX idx_facts_category ON facts(category);
            """
        )
        rows = []
        for i, (fact, domains, keywords) in enumerate(iter_facts_with_meta(), start=1):
            rows.append((
                i, fact.fact, fact.source, fact.reference, fact.category, fact.url,
                _domains_blob(domains), " ".join(keywords),
            ))
        conn.executemany(
            "INSERT INTO facts (id, fact, source, reference, category, url, domains, keywords)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

        self._fts = _fts5_available(conn)
        if self._fts:
            conn.executescript(
                """
                DROP TABLE IF EXISTS facts_fts;
                CREATE VIRTUAL TABLE facts_fts USING fts5(
                    fact, source, reference, keywords,
                    content='facts', content_rowid='id'
                );
                INSERT INTO facts_fts (rowid, fact, source, reference, keywords)
                    SELECT id, fact, source, reference, keywords FROM facts;
                """
            )
        conn.execute(
            "INSERT INTO kb_meta (key, value) VALUES ('signature', ?)",
            (f"{_SCHEMA_VERSION}|{corpus_signature()}",),
        )
        conn.execute(
            "INSERT INTO kb_meta (key, value) VALUES ('fts', ?)",
            ("1" if self._fts else "0",),
        )
        conn.commit()

    def _detect_fts(self, conn: sqlite3.Connection) -> bool:
        try:
            row = conn.execute("SELECT value FROM kb_meta WHERE key='fts'").fetchone()
            return bool(row) and row["value"] == "1"
        except sqlite3.Error:
            return False

    def rebuild(self) -> None:
        """Force a rebuild from the corpus (e.g. after a corpus update)."""
        if self.backend != "sqlite":
            self._memory_facts = list(iter_facts_with_meta())
            return
        conn = self._connect()
        try:
            with self._lock:
                self._build(conn)
        finally:
            conn.close()

    # ----- queries ------------------------------------------------------- #
    def _memory_filtered(
        self, q, domain, category, source
    ) -> List[ReferenceFact]:
        ql = (q or "").lower()
        out: List[ReferenceFact] = []
        for fact, domains, keywords in (self._memory_facts or []):
            if domain and domain not in domains:
                continue
            if category and fact.category != category:
                continue
            if source and source.lower() not in fact.source.lower():
                continue
            if ql and ql not in fact.fact.lower() and ql not in fact.source.lower() \
                    and ql not in fact.reference.lower() and ql not in " ".join(keywords).lower():
                continue
            out.append(fact)
        return out

    def search(
        self,
        *,
        q: Optional[str] = None,
        domain: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = 50,
    ) -> List[dict]:
        if self.backend == "memory":
            res = self._memory_filtered(q, domain, category, source)
            if offset:
                res = res[offset:]
            if limit is not None:
                res = res[:limit]
            return [fact_to_dict(f) for f in res]

        conn = self._connect()
        try:
            use_fts = bool(q) and self._detect_fts(conn)
            params: List[object] = []
            if use_fts:
                sql = (
                    "SELECT f.fact, f.source, f.reference, f.category, f.url "
                    "FROM facts_fts JOIN facts f ON f.id = facts_fts.rowid "
                    "WHERE facts_fts MATCH ? "
                )
                params.append(_fts_query(q))
            else:
                sql = "SELECT fact, source, reference, category, url FROM facts WHERE 1=1 "
                if q:
                    sql += "AND (fact LIKE ? OR source LIKE ? OR reference LIKE ? OR keywords LIKE ?) "
                    like = f"%{q}%"
                    params += [like, like, like, like]
            if domain:
                sql += "AND " + ("f.domains" if use_fts else "domains") + " LIKE ? "
                params.append(f"%,{domain},%")
            if category:
                sql += "AND " + ("f.category" if use_fts else "category") + " = ? "
                params.append(category)
            if source:
                sql += "AND " + ("f.source" if use_fts else "source") + " LIKE ? "
                params.append(f"%{source}%")
            sql += "ORDER BY " + ("f.id" if use_fts else "id") + " "
            if limit is not None:
                sql += "LIMIT ? OFFSET ? "
                params += [limit, offset]
            elif offset:
                sql += "LIMIT -1 OFFSET ? "
                params.append(offset)
            try:
                rows = conn.execute(sql, params).fetchall()
            except sqlite3.Error:
                # FTS query syntax issue — fall back to LIKE.
                return self._search_like(conn, q, domain, category, source, offset, limit)
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _search_like(self, conn, q, domain, category, source, offset, limit):
        sql = "SELECT fact, source, reference, category, url FROM facts WHERE 1=1 "
        params: List[object] = []
        if q:
            sql += "AND (fact LIKE ? OR source LIKE ? OR reference LIKE ? OR keywords LIKE ?) "
            like = f"%{q}%"
            params += [like, like, like, like]
        if domain:
            sql += "AND domains LIKE ? "
            params.append(f"%,{domain},%")
        if category:
            sql += "AND category = ? "
            params.append(category)
        if source:
            sql += "AND source LIKE ? "
            params.append(f"%{source}%")
        sql += "ORDER BY id "
        if limit is not None:
            sql += "LIMIT ? OFFSET ? "
            params += [limit, offset]
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def count(
        self,
        *,
        q: Optional[str] = None,
        domain: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
    ) -> int:
        return len(self.search(q=q, domain=domain, category=category, source=source,
                               offset=0, limit=None))

    def sources(self) -> List[Dict[str, object]]:
        if self.backend == "memory":
            counts: Dict[str, int] = {}
            for fact, _, _ in (self._memory_facts or []):
                counts[fact.source] = counts.get(fact.source, 0) + 1
            return [{"source": s, "count": n}
                    for s, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT source, COUNT(*) AS count FROM facts "
                "GROUP BY source ORDER BY count DESC, source ASC"
            ).fetchall()
            return [{"source": r["source"], "count": r["count"]} for r in rows]
        finally:
            conn.close()

    def total(self) -> int:
        if self.backend == "memory":
            return len(self._memory_facts or [])
        conn = self._connect()
        try:
            return int(conn.execute("SELECT COUNT(*) AS c FROM facts").fetchone()["c"])
        finally:
            conn.close()

    def status(self) -> dict:
        return {
            "backend": self.backend,
            "persistent": self.persistent,
            "db_path": str(self.path) if self.backend == "sqlite" else "",
            "fts5": self._detect_fts(self._connect()) if self.backend == "sqlite" else False,
            "count": self.total(),
            "signature": corpus_signature(),
        }


def _fts_query(q: str) -> str:
    """Turn free text into a safe FTS5 prefix query (AND of terms)."""
    terms = [t for t in "".join(c if c.isalnum() else " " for c in q).split() if t]
    if not terms:
        return '""'
    return " ".join(f"{t}*" for t in terms)


# --------------------------------------------------------------------------- #
# Process-wide singleton
# --------------------------------------------------------------------------- #
_STORE: Optional[KnowledgeStore] = None
_STORE_LOCK = threading.Lock()


def get_store() -> KnowledgeStore:
    global _STORE
    if _STORE is None:
        with _STORE_LOCK:
            if _STORE is None:
                _STORE = KnowledgeStore()
    return _STORE


def reset_store() -> None:
    """Drop the singleton (tests / after corpus change)."""
    global _STORE
    with _STORE_LOCK:
        _STORE = None
