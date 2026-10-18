"""Server-side auto-retry for Redis-backed identity mutations.

Problem
-------
The identity service keeps every account in memory and persists to Redis after
each mutation via ``persist_hook`` -> ``_save_dirty_accounts``. Writes use
compare-and-swap (CAS) on a per-account revision counter so two replicas
cannot silently stomp each other. When a learner's phone and the browser both
hit different pods in quick succession, the loser's CAS fails with
``PersistenceConflict`` and FastAPI returns ``409 account was updated on
another server; retry``. Mobile users see a lot of these during onboarding
because the setup assistant posts avatar + learning-profile + course-progress
back-to-back.

On conflict, ``_save_dirty_accounts`` already hydrates the local store from
Redis before raising, so the in-memory state is guaranteed to be fresh after
the exception. Replaying the same HTTP request against the fresh state re-
applies the mutation and persists it on top. Usually in one retry.

Fix
---
A Starlette middleware wraps every mutating HTTP request. The 409 handler for
``PersistenceConflict`` stamps a known header (``X-Persistence-Conflict: 1``)
on its JSON response. When the middleware sees that header, it re-dispatches
the same request up to ``attempts`` times with a short jittered backoff.
Starlette's ``Request`` caches the body on the first ``await request.body()``
call so re-dispatch sees identical input. If the budget is exhausted, the
original 409 response flows through to the client unchanged - no silent
swallowing.

Why response-sniffing, not exception-catching
---------------------------------------------
Starlette's ``ExceptionMiddleware`` sits *inside* user middleware in the ASGI
stack. By the time user middleware runs, custom exceptions like
``PersistenceConflict`` have already been converted into responses by the
registered handler. So the retry layer has to look at the response, not catch
the exception.

Why middleware, not a per-endpoint decorator
--------------------------------------------
A ``functools.wraps`` decorator breaks FastAPI's pydantic forward-ref
resolution because ``typing.get_type_hints`` evaluates annotations in the
wrapper function's module globals, where endpoint-local models like
``CourseProgressWrite`` are undefined. Middleware runs at the ASGI layer and
leaves every endpoint signature untouched.

Scope
-----
Only mutating methods (``POST``, ``PUT``, ``PATCH``, ``DELETE``) are retried;
safe methods have nothing to CAS against. Only responses marked with
``PERSISTENCE_CONFLICT_HEADER`` are retried, so a client-sent 409 (e.g. from a
genuine business-rule conflict) is passed through unchanged.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# The 409 handler for PersistenceConflict stamps this header on its response
# so the retry middleware can tell our CAS race apart from a client-authored
# 409. The value is intentionally short - it is a flag, not a payload.
PERSISTENCE_CONFLICT_HEADER = "X-Persistence-Conflict"
PERSISTENCE_CONFLICT_HEADER_VALUE = "1"

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Soft default - 3 attempts covers the common replica-race window (<100 ms).
# Clamped to [1, 10] so a misconfiguration cannot stall a request indefinitely.
_DEFAULT_ATTEMPTS = 3
_MIN_ATTEMPTS = 1
_MAX_ATTEMPTS = 10

# Backoff: base * (attempt + 1) + random jitter, capped at max_delay_s.
_DEFAULT_BASE_DELAY_S = 0.025
_DEFAULT_MAX_DELAY_S = 0.25


def tag_persistence_conflict(response: Response) -> Response:
    """Stamp the retry-marker header on a 409 response.

    Call this from the ``PersistenceConflict`` exception handler so the retry
    middleware knows to re-dispatch instead of returning the 409 to the client.
    """
    response.headers[PERSISTENCE_CONFLICT_HEADER] = PERSISTENCE_CONFLICT_HEADER_VALUE
    return response


class PersistenceRetryMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that transparently retries CAS-conflict 409s."""

    def __init__(
        self,
        app: ASGIApp,
        attempts: int = _DEFAULT_ATTEMPTS,
        base_delay_s: float = _DEFAULT_BASE_DELAY_S,
        max_delay_s: float = _DEFAULT_MAX_DELAY_S,
    ) -> None:
        super().__init__(app)
        self._attempts = max(_MIN_ATTEMPTS, min(_MAX_ATTEMPTS, int(attempts)))
        self._base = max(0.0, float(base_delay_s))
        self._cap = max(self._base, float(max_delay_s))

    def _delay_for(self, attempt: int) -> float:
        if self._base <= 0:
            return 0.0
        return min(self._cap, self._base * (attempt + 1) + random.uniform(0.0, self._base))

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.method.upper() not in _MUTATING_METHODS:
            return await call_next(request)
        # Prime the body cache so re-dispatch sees the same payload (idempotent;
        # Starlette's Request only reads the stream once and caches the result).
        await request.body()
        response: Response | None = None
        for attempt in range(self._attempts):
            response = await call_next(request)
            if response.headers.get(PERSISTENCE_CONFLICT_HEADER) != PERSISTENCE_CONFLICT_HEADER_VALUE:
                return response
            if attempt + 1 >= self._attempts:
                logger.warning(
                    "persistence conflict after %d attempts on %s %s",
                    self._attempts, request.method, request.url.path,
                )
                return response
            logger.debug(
                "persistence conflict on %s %s (attempt %d/%d), retrying",
                request.method, request.url.path, attempt + 1, self._attempts,
            )
            await asyncio.sleep(self._delay_for(attempt))
        # Defensive: loop above always returns or exhausts; keep the type checker happy.
        assert response is not None
        return response


def install_persistence_retry_middleware(
    app: Any,
    *,
    attempts: int = _DEFAULT_ATTEMPTS,
    base_delay_s: float = _DEFAULT_BASE_DELAY_S,
    max_delay_s: float = _DEFAULT_MAX_DELAY_S,
) -> None:
    """Register the retry middleware on the given FastAPI/Starlette ``app``."""
    app.add_middleware(
        PersistenceRetryMiddleware,
        attempts=attempts,
        base_delay_s=base_delay_s,
        max_delay_s=max_delay_s,
    )
