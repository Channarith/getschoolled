"""POST /homework/generate (Phase 6)."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def _make_deck():
    return client.post("/decks", json={
        "title": "Bio Basics",
        "slides": [
            {"title": "Photosynthesis", "body": "plants convert light, water, CO2 into glucose and oxygen"},
            {"title": "Respiration", "body": "cells release energy from glucose using oxygen"},
        ],
    }).json()["deck_id"]


def test_generate_homework_from_deck():
    deck_id = _make_deck()
    a = client.post("/homework/generate", json={
        "deck_id": deck_id, "title": "Bio HW", "subject": "biology", "num_questions": 4,
    }).json()
    assert a["title"] == "Bio HW"
    assert a["source"] == f"deck:{deck_id}"
    assert len(a["questions"]) >= 2
    assert {q["type"] for q in a["questions"]} & {"mcq", "short", "essay"}


def test_generate_requires_source():
    r = client.post("/homework/generate", json={"title": "x"})
    assert r.status_code == 422


def test_generate_unknown_deck_404():
    r = client.post("/homework/generate", json={"deck_id": "nope"})
    assert r.status_code == 404
