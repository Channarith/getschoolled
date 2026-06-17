"""API tests for phase 4 (adaptive plan) and phase 5 (quiz + grade)."""

from fastapi.testclient import TestClient

from orchestrator.main import app

client = TestClient(app)

PASSAGES = [
    "Photosynthesis: plants convert light into chemical energy stored in sugars.",
    "Chlorophyll: the green pigment that absorbs light for photosynthesis.",
    "Oxygen: a byproduct of photosynthesis released into the air.",
]


def test_director_plan_slows_for_struggling_solo_student():
    r = client.post(
        "/director/plan",
        json={
            "class_type": "solo",
            "slides_total": 10,
            "slide_index": 2,
            "pending_questions": 0,
            "attention": 0.3,
            "slides_since_quiz": 0,
            "topic_mastery": 0.2,
            "quiz_accuracy": 0.3,
            "avg_response_latency_s": 18.0,
            "attention_trend": 0.3,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pacing"] == "slow"
    assert body["difficulty"] == "easy"
    assert body["reteach"] is True


def test_quiz_then_grade_roundtrip():
    quiz = client.post(
        "/assessment/quiz",
        json={"topic": "photosynthesis", "passages": PASSAGES, "max_items": 3},
    ).json()
    assert len(quiz["items"]) == 3
    item = quiz["items"][0]

    # Grading the item's own answer_index must be correct.
    correct = client.post(
        "/assessment/grade",
        json={
            "item_id": item["item_id"],
            "options": item["options"],
            "answer_index": item["answer_index"],
            "chosen_index": item["answer_index"],
            "difficulty": item["difficulty"],
        },
    ).json()
    assert correct["correct"] is True
    assert correct["mastery_target"] > 0.5

    wrong_choice = (item["answer_index"] + 1) % len(item["options"])
    wrong = client.post(
        "/assessment/grade",
        json={
            "item_id": item["item_id"],
            "options": item["options"],
            "answer_index": item["answer_index"],
            "chosen_index": wrong_choice,
            "difficulty": item["difficulty"],
        },
    ).json()
    assert wrong["correct"] is False
