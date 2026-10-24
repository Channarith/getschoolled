"""Load lesson bodies (decks) from content-addressed object storage.

Catalog modules point at a deck with deck_id = "obj:<sha256>". The body is the gzip JSON the
harvester wrote (courses/<aa>/<sha256>.json.gz) in Vultr Object Storage (S3 compatible) or a local
directory. Bodies are immutable, so they are cached freely; every load is size-capped and
hash-verified so a corrupt or tampered object can never be served.
"""

from __future__ import annotations

import gzip
import os
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional

from aoep_shared.harvest.objectstore import (
    LocalObjectStore,
    ObjectStore,
    canonical_bytes,
    content_sha256,
    course_key,
)

from .compose import deck_sha_from_deck_id

MAX_BODY_BYTES = int(os.environ.get("CATALOG_MAX_BODY_BYTES", str(2 * 1024 * 1024)))


class BodyError(Exception):
    """The body is missing, too large, or failed its integrity check."""


def store_from_env() -> Optional[ObjectStore]:
    """None when no object store is configured (deck bodies then simply cannot be resolved)."""
    directory = os.environ.get("OBJECT_STORE_DIR")
    if directory:
        return LocalObjectStore(directory)
    if os.environ.get("OBJECT_STORE_ENDPOINT") and os.environ.get("OBJECT_STORE_BUCKET"):
        from aoep_shared.harvest.objectstore import open_store

        return open_store("s3")
    return None


class BodyLoader:
    def __init__(self, store: ObjectStore, *, cache_items: int = 256, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.store = store
        self.max_bytes = max_bytes
        self._cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._cache_items = cache_items
        self._lock = threading.Lock()

    def load(self, deck_id: str) -> Dict[str, Any]:
        """Return the deck body dict for 'obj:<sha256>'. Raises BodyError on any problem."""
        sha = deck_sha_from_deck_id(deck_id)
        if sha is None:
            raise BodyError("not an object-store deck id")
        with self._lock:
            hit = self._cache.get(sha)
            if hit is not None:
                self._cache.move_to_end(sha)
                return hit
        try:
            raw = self.store.get(course_key(sha))
        except Exception as exc:
            raise BodyError(f"body not found: {sha[:12]}") from exc
        if len(raw) > self.max_bytes:
            raise BodyError("body too large")
        try:
            data = gzip.decompress(raw)
            if len(data) > self.max_bytes * 8:
                raise BodyError("body too large when decompressed")
            import json

            body = json.loads(data.decode("utf-8"))
        except BodyError:
            raise
        except Exception as exc:
            raise BodyError("body unreadable") from exc
        if content_sha256(canonical_bytes(body)) != sha:
            raise BodyError("body failed its integrity check")
        with self._lock:
            self._cache[sha] = body
            while len(self._cache) > self._cache_items:
                self._cache.popitem(last=False)
        return body


def deck_dict_from_body(deck_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a harvested body like curriculum.decks.Deck(**dict): deck_id/title/language/slides."""
    slides = []
    for s in body.get("slides") or []:
        if not isinstance(s, dict):
            continue
        slides.append(
            {
                "title": str(s.get("title") or "")[:300],
                "body": str(s.get("body") or "")[:20000],
                "narration": str(s.get("narration") or s.get("notes") or "")[:20000],
                "media_url": s.get("media_url") if isinstance(s.get("media_url"), str) else None,
            }
        )
    return {
        "deck_id": deck_id,
        "title": str(body.get("title") or "Untitled")[:300],
        "language": str(body.get("language") or "en"),
        "slides": slides,
        "format": str(body.get("format") or "lecture"),
        "source": str(body.get("source") or body.get("source_url") or "")[:500],
    }
