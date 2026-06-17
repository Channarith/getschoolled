"""Phase 6 - CMS deck authoring/import unit + API tests."""

from fastapi.testclient import TestClient

from curriculum.decks import DeckStore, SlideSpec, parse_deck_text
from curriculum.main import app

client = TestClient(app)

LESSON_TEXT = """LESSON: Intro to Volcanoes
LANGUAGE: en

SLIDE 1 | What is a Volcano?
A volcano is a rupture in the crust where molten rock escapes.
NARRATION: Today we learn what a volcano is.

SLIDE 2 | Types
Shield, cinder cone, and composite volcanoes differ in shape.
FACT: Lava is molten rock above ground.
"""


def test_parse_deck_text():
    deck = parse_deck_text(LESSON_TEXT)
    assert deck.title == "Intro to Volcanoes"
    assert deck.language == "en"
    assert len(deck.slides) == 2
    assert deck.slides[0].title == "What is a Volcano?"
    assert deck.slides[0].narration == "Today we learn what a volcano is."
    # Slide without explicit narration falls back to body.
    assert deck.slides[1].narration == deck.slides[1].body


def test_deck_store_crud():
    store = DeckStore()
    deck = store.create("D1", "en", [SlideSpec(title="s1", body="b1")])
    assert store.get(deck.deck_id).title == "D1"
    assert len(store.list()) == 1
    assert store.delete(deck.deck_id) is True
    assert store.get(deck.deck_id) is None


def test_author_deck_api():
    r = client.post(
        "/decks",
        json={"title": "My Deck", "language": "en",
              "slides": [{"title": "Intro", "body": "Hello", "narration": "Hi"}]},
    )
    assert r.status_code == 200, r.text
    deck = r.json()
    assert deck["title"] == "My Deck" and len(deck["slides"]) == 1

    # Listed + retrievable + presentation view.
    assert any(d["deck_id"] == deck["deck_id"] for d in client.get("/decks").json())
    pres = client.get(f"/decks/{deck['deck_id']}/presentation").json()
    assert pres["slides"][0]["index"] == 0
    assert pres["slides"][0]["title"] == "Intro"


def test_import_deck_api():
    r = client.post("/decks/import", content=LESSON_TEXT,
                    headers={"content-type": "text/plain"})
    assert r.status_code == 200, r.text
    deck = r.json()
    assert deck["title"] == "Intro to Volcanoes"
    assert len(deck["slides"]) == 2

    # Delete it.
    assert client.delete(f"/decks/{deck['deck_id']}").status_code == 200
    assert client.get(f"/decks/{deck['deck_id']}").status_code == 404


def test_import_rejects_empty():
    r = client.post("/decks/import", content="no slides here",
                    headers={"content-type": "text/plain"})
    assert r.status_code == 422
