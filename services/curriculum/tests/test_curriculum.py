from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["service"] == "curriculum"


def test_corpus_loaded():
    assert client.get("/curriculum/count").json()["documents"] >= 1


def test_search_returns_relevant_lesson():
    body = client.get(
        "/curriculum/search", params={"q": "plants convert sunlight energy"}
    ).json()
    assert body["results"]
    assert "photosynthesis" in body["results"][0]["doc_id"].lower()
