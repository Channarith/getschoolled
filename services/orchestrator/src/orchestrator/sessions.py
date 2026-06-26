"""Shared session store for the live-class teaching loop.

The orchestrator runs N replicas (see ``infra/k8s/services.yaml``: ``replicas: 3``
plus an HPA up to 30). Live-class session state must therefore live somewhere
every replica can read; otherwise a follow-up
``/api/sessions/{id}/advance|ask`` that load-balances onto a different pod than
the one that created the session 404s with "unknown session". Cookie-based
ingress affinity mitigates this but breaks on pod restarts, rollouts, scale
events, or any client that drops the affinity cookie - so the durable fix is to
keep sessions out of per-pod memory.

Two backends, same interface (mirrors :mod:`aoep_shared.ratelimit`):

* :class:`InMemorySessionStore` - a per-process dict. Correct for local dev, a
  single replica, and tests. Zero dependencies.
* :class:`RedisSessionStore` - JSON-serialized sessions in Redis, shared across
  every replica. Activates when ``REDIS_URL`` is set and ``redis`` is
  importable. Falls back to the in-memory store if Redis is unreachable, so a
  Redis blip degrades to single-pod behaviour instead of a hard failure.

Selection is by env only (no code forks), matching the platform convention:
  1. ``SESSION_BACKEND=memory``          -> always in-memory (tests / forcing).
  2. ``REDIS_URL`` set + ``redis`` lib   -> Redis, shared across replicas.
  3. otherwise                           -> in-memory.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Protocol, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Session models must carry a ``session_id`` so the store can key by it.
M = TypeVar("M", bound=BaseModel)

# Sessions expire after this long without a write so abandoned live classes
# can't grow Redis memory forever. A class realistically runs for at most a few
# hours; a day of slack covers pauses and reconnects. Override with
# ``SESSION_TTL_SECONDS``.
DEFAULT_SESSION_TTL_SECONDS = 86_400


class SessionStore(Protocol):
    """Persist + fetch live-class session state, keyed by ``session_id``."""

    name: str

    def get(self, session_id: str) -> Optional[BaseModel]:
        ...

    def save(self, session: BaseModel) -> None:
        ...

    def delete(self, session_id: str) -> None:
        ...


# --------------------------------------------------------------------------- #
# In-memory backend
# --------------------------------------------------------------------------- #
class InMemorySessionStore:
    """Per-process session dict. Single-replica / dev / test correct.

    Holds the model object directly (no serialization), so this is exactly the
    behaviour the orchestrator had before the store abstraction existed.
    """

    name = "memory"

    def __init__(self) -> None:
        self._data: dict[str, BaseModel] = {}

    def get(self, session_id: str) -> Optional[BaseModel]:
        return self._data.get(session_id)

    def save(self, session: BaseModel) -> None:
        self._data[session.session_id] = session  # type: ignore[attr-defined]

    def delete(self, session_id: str) -> None:
        self._data.pop(session_id, None)


# --------------------------------------------------------------------------- #
# Redis backend (optional)
# --------------------------------------------------------------------------- #
class RedisSessionStore:
    """Redis-backed session store; shared across replicas.

    Sessions are stored as JSON (``model_dump_json`` / ``model_validate_json``)
    under ``{prefix}{session_id}`` with a TTL. If Redis is unreachable for any
    single operation we fall back to an in-memory store so a transient Redis
    outage degrades gracefully to single-pod behaviour rather than dropping the
    class entirely.
    """

    name = "redis"

    def __init__(
        self,
        redis_client,
        model_type: Type[M],
        *,
        prefix: str = "aoep:sess:",
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    ) -> None:
        self._r = redis_client
        self._model = model_type
        self._prefix = prefix
        self._ttl = ttl_seconds
        self._fallback = InMemorySessionStore()

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    def get(self, session_id: str) -> Optional[BaseModel]:
        try:
            raw = self._r.get(self._key(session_id))
        except Exception as e:  # noqa: BLE001
            logger.warning("redis session get failed (%s); using in-memory", e)
            return self._fallback.get(session_id)
        if raw is None:
            return None
        try:
            return self._model.model_validate_json(raw)
        except Exception as e:  # noqa: BLE001
            # Corrupt/incompatible payload -> treat as missing rather than 500.
            logger.warning("session %s failed to deserialize (%s)", session_id, e)
            return None

    def save(self, session: BaseModel) -> None:
        session_id = session.session_id  # type: ignore[attr-defined]
        try:
            self._r.set(
                self._key(session_id),
                session.model_dump_json(),
                ex=self._ttl,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("redis session save failed (%s); using in-memory", e)
            self._fallback.save(session)

    def delete(self, session_id: str) -> None:
        try:
            self._r.delete(self._key(session_id))
        except Exception as e:  # noqa: BLE001
            logger.warning("redis session delete failed (%s)", e)
            self._fallback.delete(session_id)


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def build_session_store(model_type: Type[M]) -> SessionStore:
    """Pick the best session backend for the current env.

    Priority:
      1. ``SESSION_BACKEND=memory`` -> always in-memory (tests / forcing).
      2. ``REDIS_URL`` set + ``redis`` installed + reachable -> Redis.
      3. otherwise -> in-memory.
    """
    backend = (os.environ.get("SESSION_BACKEND") or "").lower()
    if backend == "memory":
        return InMemorySessionStore()
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
            ttl = int(os.environ.get("SESSION_TTL_SECONDS", DEFAULT_SESSION_TTL_SECONDS))
            return RedisSessionStore(client, model_type, ttl_seconds=ttl)
        except Exception as e:  # noqa: BLE001
            logger.warning("redis unavailable for sessions (%s); using in-memory", e)
    return InMemorySessionStore()
