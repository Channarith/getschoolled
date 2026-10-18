"""Tests for the PersistenceConflict retry middleware.

The middleware sits in front of mobile-hot identity endpoints so a transient
Redis CAS race no longer surfaces as a 409 to the learner. These tests pin
five guarantees:

1. A successful first call reaches the client without any retry overhead.
2. A transient CAS-race 409 (first N-1 attempts) is swallowed and the Nth
   attempt's successful response is handed back.
3. A persistent CAS-race 409 (every attempt tagged) still flows through to
   the client once the budget is exhausted.
4. Safe methods (``GET``) are never retried.
5. A 409 that is NOT tagged with the retry header - e.g. a genuine
   client-authored conflict - is passed through unchanged on the first try.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from identity.concurrency import (
    PERSISTENCE_CONFLICT_HEADER,
    PERSISTENCE_CONFLICT_HEADER_VALUE,
    install_persistence_retry_middleware,
    tag_persistence_conflict,
)
from identity.persistence import PersistenceConflict


def _build_app(side_effect) -> FastAPI:
    """Build a tiny FastAPI app whose POST runs ``side_effect`` each call.

    ``side_effect`` returns the response body on success or raises
    :class:`PersistenceConflict` to simulate a Redis CAS race (which is then
    tagged by the exception handler just like the real identity service does).
    """
    app = FastAPI()

    @app.exception_handler(PersistenceConflict)
    async def _conflict_handler(_request, exc):
        return tag_persistence_conflict(
            JSONResponse(status_code=409, content={"detail": "conflict"})
        )

    install_persistence_retry_middleware(app, base_delay_s=0.0, max_delay_s=0.0)

    @app.post("/mutate")
    def mutate() -> dict:
        return {"result": side_effect()}

    @app.get("/read")
    def read() -> dict:
        return {"result": side_effect()}

    @app.post("/plain-conflict")
    def plain_conflict() -> JSONResponse:
        side_effect()
        return JSONResponse(status_code=409, content={"detail": "business rule"})

    return app


def test_successful_mutation_runs_the_handler_once() -> None:
    calls: list[int] = []

    def do() -> str:
        calls.append(1)
        return "ok"

    client = TestClient(_build_app(do))
    response = client.post("/mutate")
    assert response.status_code == 200
    assert response.json() == {"result": "ok"}
    assert len(calls) == 1
    assert PERSISTENCE_CONFLICT_HEADER not in response.headers


def test_retries_transient_conflict_until_success() -> None:
    calls: list[int] = []

    def do() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise PersistenceConflict("acct-1")
        return "settled"

    client = TestClient(_build_app(do))
    response = client.post("/mutate")
    assert response.status_code == 200
    assert response.json() == {"result": "settled"}
    assert len(calls) == 3  # two conflicts, then success


def test_persistent_conflict_surfaces_as_tagged_409() -> None:
    calls: list[int] = []

    def do() -> str:
        calls.append(1)
        raise PersistenceConflict("acct-stuck")

    client = TestClient(_build_app(do))
    response = client.post("/mutate")
    assert response.status_code == 409
    # The tag survives all the way out so an operator can grep for truly stuck
    # accounts in access logs.
    assert response.headers.get(PERSISTENCE_CONFLICT_HEADER) == PERSISTENCE_CONFLICT_HEADER_VALUE
    assert len(calls) == 3  # default attempts budget


def test_safe_methods_are_not_retried() -> None:
    calls: list[int] = []

    def do() -> str:
        calls.append(1)
        raise PersistenceConflict("acct")

    client = TestClient(_build_app(do))
    response = client.get("/read")
    assert response.status_code == 409
    assert len(calls) == 1  # no retry on GET


def test_untagged_409_is_passed_through_unchanged() -> None:
    calls: list[int] = []

    def do() -> str:
        calls.append(1)
        return "noop"

    client = TestClient(_build_app(do))
    response = client.post("/plain-conflict")
    assert response.status_code == 409
    assert PERSISTENCE_CONFLICT_HEADER not in response.headers
    assert len(calls) == 1
