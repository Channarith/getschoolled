"""Shared backends for group-class scheduling across orchestrator replicas."""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Protocol

from .group_class_serde import group_class_from_json, group_class_to_json
from .group_classes import GroupClass

logger = logging.getLogger(__name__)

DEFAULT_GROUP_CLASS_TTL_SECONDS = 2_592_000  # 30 days — schedule survives restarts


class GroupClassBackend(Protocol):
    name: str

    def get(self, class_id: str) -> Optional[GroupClass]:
        ...

    def save(self, gc: GroupClass) -> None:
        ...

    def delete(self, class_id: str) -> None:
        ...

    def list_ids(self) -> List[str]:
        ...


class InMemoryGroupClassBackend:
    name = "memory"

    def __init__(self) -> None:
        self._classes: dict[str, GroupClass] = {}

    def get(self, class_id: str) -> Optional[GroupClass]:
        return self._classes.get(class_id)

    def save(self, gc: GroupClass) -> None:
        self._classes[gc.id] = gc

    def delete(self, class_id: str) -> None:
        self._classes.pop(class_id, None)

    def list_ids(self) -> List[str]:
        return list(self._classes.keys())


class RedisGroupClassBackend:
    name = "redis"

    def __init__(
        self,
        redis_client,
        *,
        prefix: str = "aoep:gc:",
        index_key: str = "aoep:gc:index",
        ttl_seconds: int = DEFAULT_GROUP_CLASS_TTL_SECONDS,
    ) -> None:
        self._r = redis_client
        self._prefix = prefix
        self._index = index_key
        self._ttl = ttl_seconds
        self._fallback = InMemoryGroupClassBackend()

    def _key(self, class_id: str) -> str:
        return f"{self._prefix}{class_id}"

    def get(self, class_id: str) -> Optional[GroupClass]:
        try:
            raw = self._r.get(self._key(class_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis group-class get failed (%s); using in-memory", exc)
            return self._fallback.get(class_id)
        if raw is None:
            return None
        try:
            return group_class_from_json(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("group class %s failed to deserialize (%s)", class_id, exc)
            return None

    def save(self, gc: GroupClass) -> None:
        try:
            self._r.set(self._key(gc.id), group_class_to_json(gc), ex=self._ttl)
            self._r.sadd(self._index, gc.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis group-class save failed (%s); using in-memory", exc)
            self._fallback.save(gc)

    def delete(self, class_id: str) -> None:
        try:
            self._r.delete(self._key(class_id))
            self._r.srem(self._index, class_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis group-class delete failed (%s)", exc)
            self._fallback.delete(class_id)

    def list_ids(self) -> List[str]:
        try:
            ids = self._r.smembers(self._index)
            return sorted(ids) if ids else []
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis group-class index failed (%s); using in-memory", exc)
            return self._fallback.list_ids()


def build_group_class_backend() -> GroupClassBackend:
    backend = (os.environ.get("GROUP_CLASS_BACKEND") or "").lower()
    if backend == "memory":
        return InMemoryGroupClassBackend()
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis  # type: ignore[import-not-found]

            client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            ttl = int(
                os.environ.get(
                    "GROUP_CLASS_TTL_SECONDS", DEFAULT_GROUP_CLASS_TTL_SECONDS
                )
            )
            return RedisGroupClassBackend(client, ttl_seconds=ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "redis unavailable for group classes (%s); using in-memory", exc
            )
    return InMemoryGroupClassBackend()
