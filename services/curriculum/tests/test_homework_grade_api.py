"""POST /homework/grade (Phase 9) - end-to-end via curriculum."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def _deck():
    return client.post("/decks", json={
        "title": "Bio", "slides": [
            {"title": "Photosynthesis", "body": "plants convert light water and carbon dioxide into glucose and oxygen"},
        ],
    }).json()["deck_id"]


def test_grade_uses_catalog_context():
    deck_id = _deck()
    assignment = {
        "title": "HW", "subject": "biology",
        "questions": [
            {"type": "short", "prompt": "Explain photosynthesis", "answer_key": ""},
            {"type": "mcq", "prompt": "What is released?",
             "options": ["oxygen", "iron"], "answer_index": 0},
        ],
    }
    body = client.post("/homework/grade", json={
        "assignment": assignment,
        "answers": ["Plants convert light water and carbon dioxide into glucose and oxygen", "oxygen"],
        "deck_id": deck_id,
        "subject": "biology",
    }).json()
    assert body["max_score"] == 2.0
    assert body["score"] >= 1.0
    # The MCQ should be correct.
    mcq = [it for it in body["items"] if it["type"] == "mcq"][0]
    assert mcq["correct"] is True
    assert "authorship_label" in body


def test_grade_from_submission_text_segments():
    assignment = {"title": "HW", "subject": "general",
                  "questions": [{"type": "short", "prompt": "q1", "answer_key": ""},
                                {"type": "short", "prompt": "q2", "answer_key": ""}]}
    body = client.post("/homework/grade", json={
        "assignment": assignment,
        "submission_text": "1. First answer about cells.\n2. Second answer about energy.",
    }).json()
    assert len(body["items"]) == 2
