"""Delivery-mode tracks + model-cards endpoint (Trust layer, Phase 5)."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def test_course_default_delivery_mode_is_ai():
    c = client.post("/courses", json={"title": "Default", "subject": "general"}).json()
    assert c["delivery_mode"] == "ai"


def test_catalog_filters_by_delivery_mode():
    client.post("/courses", json={"title": "Human-led", "subject": "art", "delivery_mode": "human"})
    client.post("/courses", json={"title": "Hybrid", "subject": "math", "delivery_mode": "hybrid"})
    human = client.get("/catalog", params={"delivery_mode": "human"}).json()
    titles = [c["title"] for c in human["courses"]]
    assert "Human-led" in titles
    assert "Hybrid" not in titles
    assert all(c["delivery_mode"] == "human" for c in human["courses"])


def test_model_cards_endpoint_returns_list():
    body = client.get("/model-cards").json()
    assert "model_cards" in body and isinstance(body["model_cards"], list)
