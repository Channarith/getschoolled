"""Scalable harvest corpus — SQLite + FTS5 for RAG-ready search.

Stores fetched sources, text chunks, generated courses, themes, and media refs.
Designed to grow to millions of chunks; FTS5 for fast lexical retrieval (swap to
pgvector later behind the same ``search()`` shape).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .queue import url_key

_SCHEMA_VERSION = 1
_CHUNK_SIZE = 900
_TOKEN = re.compile(r"[a-z0-9]+")


def default_corpus_path() -> Path:
    env = os.environ.get("AOEP_HARVEST_CORPUS_DB")
    if env:
        return Path(env)
    return Path(os.path.expanduser("~")) / ".cache" / "aoep" / "harvest_corpus.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp._fts_probe USING fts5(x)")
        conn.execute("DROP TABLE temp._fts_probe")
        return True
    except sqlite3.Error:
        return False


def chunk_text(text: str, *, max_chars: int = _CHUNK_SIZE) -> List[str]:
    """Split prose into RAG-sized chunks on sentence boundaries."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    parts = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []
    buf = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(buf) + len(p) + 1 <= max_chars:
            buf = f"{buf} {p}".strip() if buf else p
        else:
            if buf:
                chunks.append(buf)
            buf = p if len(p) <= max_chars else p[:max_chars]
    if buf:
        chunks.append(buf)
    return chunks


@dataclass
class CorpusHit:
    chunk_id: str
    source_url: str
    title: str
    subject: str
    heading: str
    body: str
    score: float
    course_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class HarvestCorpusStore:
    """Persistent harvest corpus with FTS-backed ``search()``."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else default_corpus_path()
        self._lock = threading.RLock()
        self._fts = False
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS corpus_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS sources (
                        url_key TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        license TEXT,
                        subject TEXT,
                        title TEXT,
                        source_type TEXT,
                        content_hash TEXT,
                        status TEXT DEFAULT 'fetched',
                        fetched_at TEXT,
                        meta_json TEXT DEFAULT '{}'
                    );
                    CREATE TABLE IF NOT EXISTS chunks (
                        chunk_id TEXT PRIMARY KEY,
                        url_key TEXT NOT NULL,
                        course_id TEXT,
                        heading TEXT,
                        body TEXT NOT NULL,
                        subject TEXT,
                        chunk_index INTEGER DEFAULT 0,
                        meta_json TEXT DEFAULT '{}',
                        FOREIGN KEY (url_key) REFERENCES sources(url_key)
                    );
                    CREATE TABLE IF NOT EXISTS courses (
                        course_id TEXT PRIMARY KEY,
                        url_key TEXT,
                        title TEXT NOT NULL,
                        subject TEXT,
                        composition_score INTEGER DEFAULT 0,
                        json_path TEXT,
                        pptx_path TEXT,
                        theme_json TEXT DEFAULT '{}',
                        media_json TEXT DEFAULT '{}',
                        tags_json TEXT DEFAULT '{}',
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS harvest_queue (
                        url_key TEXT PRIMARY KEY,
                        spec_json TEXT NOT NULL,
                        state TEXT DEFAULT 'pending',
                        priority INTEGER DEFAULT 0,
                        enqueued_at TEXT NOT NULL,
                        finished_at TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_chunks_url ON chunks(url_key);
                    CREATE INDEX IF NOT EXISTS idx_chunks_course ON chunks(course_id);
                    CREATE INDEX IF NOT EXISTS idx_courses_subject ON courses(subject);
                    """
                )
                self._fts = _fts5_available(conn)
                if self._fts:
                    conn.execute(
                        """
                        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                            chunk_id UNINDEXED,
                            title,
                            heading,
                            body,
                            subject,
                            tokenize='porter'
                        )
                        """
                    )
                row = conn.execute(
                    "SELECT value FROM corpus_meta WHERE key='schema_version'"
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO corpus_meta(key,value) VALUES('schema_version',?)",
                        (str(_SCHEMA_VERSION),),
                    )
                conn.commit()
            finally:
                conn.close()

    def upsert_source(
        self,
        *,
        url: str,
        license: Optional[str] = None,
        subject: Optional[str] = None,
        title: Optional[str] = None,
        source_type: str = "html",
        content_hash: str = "",
        status: str = "fetched",
        meta: Optional[Dict] = None,
    ) -> str:
        key = url_key(url)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO sources(url_key,url,license,subject,title,source_type,
                        content_hash,status,fetched_at,meta_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(url_key) DO UPDATE SET
                        license=excluded.license,
                        subject=COALESCE(excluded.subject, sources.subject),
                        title=COALESCE(excluded.title, sources.title),
                        content_hash=excluded.content_hash,
                        status=excluded.status,
                        fetched_at=excluded.fetched_at,
                        meta_json=excluded.meta_json
                    """,
                    (
                        key, url, license, subject, title, source_type,
                        content_hash, status, _now(), json.dumps(meta or {}),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return key

    def index_document(
        self,
        *,
        url: str,
        title: str,
        text: str,
        subject: str = "general",
        heading: str = "",
        course_id: Optional[str] = None,
        meta: Optional[Dict] = None,
    ) -> int:
        """Chunk and index text for RAG. Returns chunk count."""
        key = url_key(url)
        chunks = chunk_text(text)
        if not chunks:
            return 0
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM chunks WHERE url_key=? AND course_id IS ?",
                             (key, course_id))
                for i, body in enumerate(chunks):
                    cid = uuid.uuid4().hex[:16]
                    conn.execute(
                        """
                        INSERT INTO chunks(chunk_id,url_key,course_id,heading,body,
                            subject,chunk_index,meta_json)
                        VALUES(?,?,?,?,?,?,?,?)
                        """,
                        (cid, key, course_id, heading or title, body, subject, i,
                         json.dumps(meta or {})),
                    )
                    if self._fts:
                        conn.execute(
                            "INSERT INTO chunks_fts(chunk_id,title,heading,body,subject)"
                            " VALUES(?,?,?,?,?)",
                            (cid, title, heading or title, body, subject),
                        )
                conn.commit()
            finally:
                conn.close()
        return len(chunks)

    def save_course(
        self,
        *,
        course_id: str,
        url: str,
        title: str,
        subject: str,
        composition_score: int = 0,
        json_path: str = "",
        pptx_path: str = "",
        theme: Optional[Dict] = None,
        media: Optional[Dict] = None,
        tags: Optional[Dict] = None,
        full_text: str = "",
    ) -> None:
        key = url_key(url)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO courses(course_id,url_key,title,subject,composition_score,
                        json_path,pptx_path,theme_json,media_json,tags_json,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(course_id) DO UPDATE SET
                        title=excluded.title,
                        subject=excluded.subject,
                        composition_score=excluded.composition_score,
                        json_path=excluded.json_path,
                        pptx_path=excluded.pptx_path,
                        theme_json=excluded.theme_json,
                        media_json=excluded.media_json,
                        tags_json=excluded.tags_json
                    """,
                    (
                        course_id, key, title, subject, composition_score,
                        json_path, pptx_path,
                        json.dumps(theme or {}),
                        json.dumps(media or {}),
                        json.dumps(tags or {}),
                        _now(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        if full_text:
            self.index_document(
                url=url, title=title, text=full_text, subject=subject,
                course_id=course_id, meta={"kind": "course"},
            )

    def search(self, query: str, *, top_k: int = 8, subject: Optional[str] = None) -> List[CorpusHit]:
        """RAG retrieval over indexed chunks."""
        q = (query or "").strip()
        if not q:
            return []
        with self._lock:
            conn = self._connect()
            try:
                if self._fts:
                    sql = (
                        "SELECT c.chunk_id, c.url_key, c.heading, c.body, c.subject, "
                        "c.course_id, c.meta_json, s.url, s.title, "
                        "bm25(chunks_fts) AS rank "
                        "FROM chunks_fts f "
                        "JOIN chunks c ON c.chunk_id=f.chunk_id "
                        "JOIN sources s ON s.url_key=c.url_key "
                        "WHERE chunks_fts MATCH ? "
                    )
                    params: List[Any] = [q]
                    if subject:
                        sql += " AND c.subject=? "
                        params.append(subject)
                    sql += " ORDER BY rank LIMIT ?"
                    params.append(top_k)
                    try:
                        rows = conn.execute(sql, params).fetchall()
                    except sqlite3.Error:
                        rows = []
                else:
                    rows = []
                if not rows:
                    like = f"%{q}%"
                    sql = (
                        "SELECT c.chunk_id, c.url_key, c.heading, c.body, c.subject, "
                        "c.course_id, c.meta_json, s.url, s.title "
                        "FROM chunks c JOIN sources s ON s.url_key=c.url_key "
                        "WHERE c.body LIKE ? "
                    )
                    params = [like]
                    if subject:
                        sql += " AND c.subject=? "
                        params.append(subject)
                    sql += " LIMIT ?"
                    params.append(top_k)
                    rows = conn.execute(sql, params).fetchall()
                hits: List[CorpusHit] = []
                for r in rows:
                    rank = float(r["rank"]) if "rank" in r.keys() else 1.0
                    score = 1.0 / (1.0 + abs(rank)) if self._fts else 0.5
                    hits.append(CorpusHit(
                        chunk_id=r["chunk_id"],
                        source_url=r["url"],
                        title=r["title"] or "",
                        subject=r["subject"] or "",
                        heading=r["heading"] or "",
                        body=r["body"],
                        score=score,
                        course_id=r["course_id"],
                        meta=json.loads(r["meta_json"] or "{}"),
                    ))
                return hits
            finally:
                conn.close()

    def reset_queue_state(self, from_state: str, *, new_state: str = "pending") -> int:
        """Re-queue failed/skipped harvest URLs (e.g. after a network fix)."""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "UPDATE harvest_queue SET state=? WHERE state=?",
                    (new_state, from_state),
                )
                conn.commit()
                return int(cur.rowcount or 0)
            finally:
                conn.close()

    def stats(self) -> Dict[str, int]:
        with self._lock:
            conn = self._connect()
            try:
                return {
                    "sources": conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
                    "chunks": conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
                    "courses": conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
                    "queue_pending": conn.execute(
                        "SELECT COUNT(*) FROM harvest_queue WHERE state='pending'"
                    ).fetchone()[0],
                }
            finally:
                conn.close()
