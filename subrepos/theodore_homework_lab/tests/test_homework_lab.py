"""Tests for 50+ methodology homework lab."""

from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_homework_lab.generate import (
    generate_assignment,
    generate_full_battery,
    generate_item,
    wrap_shared_classic,
)
from theodore_homework_lab.grade import gold_answer_for, grade_assignment, grade_item
from theodore_homework_lab.main import app
from theodore_homework_lab.methodologies import (
    METHODOLOGY_IDS,
    list_methodologies,
    methodology_count,
)
from theodore_homework_lab.quality import HomeworkTuning, get_runner, run_gold_battery
import theodore_homework_lab.quality as ql


PASSAGES = [
    "photosynthesis: plants make food using light water and carbon dioxide",
    "chlorophyll: green pigment that captures light energy",
]


def test_registry_has_over_50_methodologies():
    assert methodology_count() >= 50
    assert len(METHODOLOGY_IDS) == methodology_count()
    families = {m.family for m in list_methodologies()}
    assert "media" in families
    assert "audio" in families
    assert "game" in families
    assert "language" in families


def test_every_methodology_generates_and_gold_grades():
    """Each of 50+ types must generate an item and accept its gold answer."""
    failures = []
    for mid in METHODOLOGY_IDS:
        item = generate_item(
            mid,
            passages=PASSAGES,
            subject="science",
            locale="es",
            context={
                "verse": "Count with me one two three",
                "meaning_en": "Practice counting one through three.",
            },
        )
        assert item.methodology == mid
        assert item.prompt
        gold = gold_answer_for(item)
        g = grade_item(item, gold)
        if g.score < 0.5:
            failures.append((mid, g.score, g.rationale))
    assert not failures, f"gold grade failures: {failures[:10]}"


def test_full_battery_covers_all_methodologies():
    assignment = generate_full_battery(passages=PASSAGES, subject="science")
    assert len(assignment.items) == methodology_count()
    assert set(assignment.methodologies_used) == set(METHODOLOGY_IDS)
    report = grade_assignment(
        assignment, {it.item_id: gold_answer_for(it) for it in assignment.items}
    )
    assert report.percentage >= 70.0
    assert len(report.methodology_coverage) == methodology_count()


def test_mixed_assignment_and_wrong_answers_score_low():
    assignment = generate_assignment(
        title="Mixed",
        passages=PASSAGES,
        methodologies=["mcq", "spelling", "translate_verse", "matching", "summarize"],
        max_items=5,
        context={"verse": "Red is warm like morning light", "meaning_en": "Red feels warm."},
    )
    assert len(assignment.items) == 5
    wrong = ["zzz", "nope", "???", "bad", "x"]
    report = grade_assignment(assignment, wrong)
    assert report.percentage < 40.0


def test_wrap_shared_classic_uses_production_generator():
    assignment = wrap_shared_classic(PASSAGES, title="Classic", subject="science")
    assert assignment.items
    assert any(it.methodology == "mcq" for it in assignment.items)


def test_tuning_presets():
    t = HomeworkTuning.preset("strict")
    assert t.fuzzy_threshold == 0.7
    t2 = t.patched({"max_items_default": 8})
    assert t2.max_items_default == 8


def test_api_methodologies_generate_grade_gold():
    ql._RUNNER = None
    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200
        assert h.json()["methodologies"] >= 50

        m = client.get("/api/homework/methodologies")
        assert m.status_code == 200
        assert m.json()["total_registered"] >= 50

        bat = client.post(
            "/api/homework/generate/battery",
            json={"title": "Battery", "passages": PASSAGES, "subject": "science"},
        )
        assert bat.status_code == 200
        assert bat.json()["methodology_count"] >= 50
        assignment = bat.json()["assignment"]

        # grade first item wrong
        item0 = assignment["items"][0]
        g = client.post(
            "/api/homework/grade",
            json={"assignment": {"assignment_id": assignment["assignment_id"],
                                   "title": assignment["title"],
                                   "items": [item0]},
                  "answers": ["definitely-wrong-answer-xyz"]},
        )
        assert g.status_code == 200

        gold = client.post("/api/homework/eval/gold")
        assert gold.status_code == 200
        assert gold.json()["methodology_count"] >= 50
        assert gold.json()["percentage"] >= 70.0

        tel = client.get("/api/homework/telemetry")
        assert tel.status_code == 200


def test_run_gold_battery_helper():
    result = run_gold_battery()
    assert result["methodology_count"] >= 50
    assert result["percentage"] >= 70.0
