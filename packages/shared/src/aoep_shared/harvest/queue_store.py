"""SQLite-backed durable harvest queue (survives restarts, scales to large URL sets)."""

from __future__ import annotations

import json
from typing import Iterable, List, Optional

from .corpus_store import HarvestCorpusStore
from .queue import HarvestQueue, url_key
from .sources import SourceSpec


class PersistentHarvestQueue(HarvestQueue):
    """In-memory deque + SQLite persistence for 24/7 background crawls."""

    def __init__(self, store: Optional[HarvestCorpusStore] = None) -> None:
        super().__init__()
        self._store = store or HarvestCorpusStore()

    def _conn(self):
        return self._store._connect()

    def enqueue(self, spec: SourceSpec) -> bool:
        key = url_key(spec.url)
        if key in self._seen:
            return False
        with self._store._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT state FROM harvest_queue WHERE url_key=?", (key,)
                ).fetchone()
                if row and row["state"] == "done":
                    self._seen.add(key)
                    return False
                from datetime import datetime, timezone
                conn.execute(
                    """
                    INSERT INTO harvest_queue(url_key,spec_json,state,priority,enqueued_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(url_key) DO UPDATE SET
                        spec_json=excluded.spec_json,
                        state='pending',
                        priority=excluded.priority,
                        enqueued_at=excluded.enqueued_at
                    WHERE harvest_queue.state != 'done'
                    """,
                    (key, json.dumps(_spec_to_dict(spec)), "pending",
                     int(spec.meta.get("priority", 0)),
                     datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
            finally:
                conn.close()
        return super().enqueue(spec)

    def enqueue_many(self, specs: Iterable[SourceSpec]) -> int:
        return sum(1 for s in specs if self.enqueue(s))

    def mark_done(self, spec: SourceSpec, *, status: str = "done") -> None:
        key = url_key(spec.url)
        with self._store._lock:
            conn = self._conn()
            try:
                from datetime import datetime, timezone
                conn.execute(
                    "UPDATE harvest_queue SET state=?, finished_at=? WHERE url_key=?",
                    (status, datetime.now(timezone.utc).isoformat(), key),
                )
                conn.commit()
            finally:
                conn.close()

    def load_pending(self, *, limit: int = 500) -> int:
        """Hydrate the in-memory deque from SQLite pending rows."""
        self._q.clear()
        self._seen.clear()
        loaded = 0
        with self._store._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT spec_json FROM harvest_queue WHERE state='pending' "
                    "ORDER BY priority DESC, enqueued_at LIMIT ?",
                    (limit,),
                ).fetchall()
            finally:
                conn.close()
        for row in rows:
            spec = _dict_to_spec(json.loads(row["spec_json"]))
            if super().enqueue(spec):
                loaded += 1
        return loaded


def _spec_to_dict(spec: SourceSpec) -> dict:
    return {
        "url": spec.url,
        "license": spec.license,
        "source_type": spec.source_type,
        "subject": spec.subject,
        "title": spec.title,
        "meta": spec.meta,
    }


def _dict_to_spec(d: dict) -> SourceSpec:
    return SourceSpec(
        url=d["url"],
        license=d.get("license"),
        source_type=d.get("source_type", "html"),
        subject=d.get("subject"),
        title=d.get("title"),
        meta=d.get("meta") or {},
    )
