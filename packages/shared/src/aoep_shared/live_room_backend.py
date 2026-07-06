"""Shared backends for Salareen live rooms across orchestrator replicas.

On Vultr VKE the orchestrator runs 3+ pods behind ingress. Live-room chat,
Q&A queues, and moderation must survive load balancing — the same pattern as
``orchestrator.sessions`` for teaching sessions.

Selection (env only, no code forks):
  1. ``LIVE_ROOM_BACKEND=memory``  -> per-process dict (tests / forcing).
  2. ``REDIS_URL`` + reachable     -> Redis JSON blobs shared by every replica.
  3. otherwise                     -> in-memory.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Protocol

from .live_room import LiveRoom
from .live_room_serde import live_room_from_json, live_room_to_json

logger = logging.getLogger(__name__)

DEFAULT_LIVE_ROOM_TTL_SECONDS = 86_400


class LiveRoomBackend(Protocol):
    name: str

    def get(self, room_id: str) -> Optional[LiveRoom]:
        ...

    def save(self, room: LiveRoom) -> None:
        ...

    def delete(self, room_id: str) -> None:
        ...


class InMemoryLiveRoomBackend:
    name = "memory"

    def __init__(self) -> None:
        self._rooms: dict[str, LiveRoom] = {}

    def get(self, room_id: str) -> Optional[LiveRoom]:
        return self._rooms.get(room_id)

    def save(self, room: LiveRoom) -> None:
        self._rooms[room.room_id] = room

    def delete(self, room_id: str) -> None:
        self._rooms.pop(room_id, None)


class RedisLiveRoomBackend:
    name = "redis"

    def __init__(
        self,
        redis_client,
        *,
        prefix: str = "aoep:live:",
        ttl_seconds: int = DEFAULT_LIVE_ROOM_TTL_SECONDS,
    ) -> None:
        self._r = redis_client
        self._prefix = prefix
        self._ttl = ttl_seconds
        self._fallback = InMemoryLiveRoomBackend()

    def _key(self, room_id: str) -> str:
        return f"{self._prefix}{room_id}"

    def get(self, room_id: str) -> Optional[LiveRoom]:
        try:
            raw = self._r.get(self._key(room_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis live-room get failed (%s); using in-memory", exc)
            return self._fallback.get(room_id)
        if raw is None:
            return None
        try:
            return live_room_from_json(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("live room %s failed to deserialize (%s)", room_id, exc)
            return None

    def save(self, room: LiveRoom) -> None:
        try:
            self._r.set(self._key(room.room_id), live_room_to_json(room), ex=self._ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis live-room save failed (%s); using in-memory", exc)
            self._fallback.save(room)

    def delete(self, room_id: str) -> None:
        try:
            self._r.delete(self._key(room_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis live-room delete failed (%s)", exc)
            self._fallback.delete(room_id)


def build_live_room_backend() -> LiveRoomBackend:
    backend = (os.environ.get("LIVE_ROOM_BACKEND") or "").lower()
    if backend == "memory":
        return InMemoryLiveRoomBackend()
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis  # type: ignore[import-not-found]

            client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
            client.ping()
            ttl = int(
                os.environ.get("LIVE_ROOM_TTL_SECONDS", DEFAULT_LIVE_ROOM_TTL_SECONDS)
            )
            return RedisLiveRoomBackend(client, ttl_seconds=ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis unavailable for live rooms (%s); using in-memory", exc)
    return InMemoryLiveRoomBackend()
