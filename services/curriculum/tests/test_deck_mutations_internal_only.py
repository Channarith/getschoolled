"""Deck create/import/delete are content mutations, not public APIs.

Course and program CRUD already required internal auth; the deck routes did
not, so anyone who could reach the service could insert or destroy the teaching
content a class is about to present.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from curriculum.main import app


@pytest.fixture(autouse=True)
def _enable_internal_auth(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)


def test_deck_mutations_require_internal_auth():
    client = TestClient(app)
    created = client.post("/decks", json={
        "title": "Injected", "language": "en",
        "slides": [{"title": "s", "body": "b"}],
    })
    assert created.status_code in (401, 403), created.text

    imported = client.post("/decks/import", content="# Injected\n- point\n",
                           headers={"Content-Type": "text/plain"})
    assert imported.status_code in (401, 403), imported.text

    deleted = client.delete("/decks/any-deck-id")
    assert deleted.status_code in (401, 403), deleted.text


def test_reading_decks_stays_open(monkeypatch):
    """Only the mutations are gated; the catalog is still readable."""
    client = TestClient(app)
    assert client.get("/decks").status_code == 200
