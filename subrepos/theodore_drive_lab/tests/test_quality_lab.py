"""Tests for Drive Mode fine-tune lab."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import theodore_drive_lab.bakeoff as bakeoff_mod
from theodore_drive_lab.answer_grounding import evaluate_answers
from theodore_drive_lab.bakeoff import DriveBakeoffRunner
from theodore_drive_lab.drive_tuning import DriveTuning
from theodore_drive_lab.main import app
from theodore_drive_lab.wake_eval import (
    evaluate_wake,
    has_wake_word,
    is_likely_echo,
    load_wake_cases,
    parse_wake_utterance,
)


def test_wake_word_and_commands():
    assert has_wake_word("hey sala pause")
    assert has_wake_word("Salareen next")
    assert not has_wake_word("what is gravity")
    assert parse_wake_utterance("hey sala pause")["kind"] == "pause"
    assert parse_wake_utterance("hey sala what is gravity")["kind"] == "question"
    assert parse_wake_utterance("what is gravity")["kind"] == "none"


def test_echo_detection():
    tts = "Plants convert sunlight into energy through photosynthesis."
    assert is_likely_echo(
        "plants convert sunlight into energy", tts, min_overlap=0.5
    )
    assert not is_likely_echo("I want a sandwich", tts, min_overlap=0.5)


def test_wake_eval_fixture_quality():
    report = evaluate_wake(load_wake_cases(), DriveTuning())
    assert report["n"] >= 8
    assert report["wake_precision"] >= 0.8
    assert report["wake_recall"] >= 0.8
    assert report["echo_accuracy"] >= 0.5


def test_answer_grounding():
    report = evaluate_answers(tuning=DriveTuning())
    assert report["n"] >= 3
    assert report["grounded_rate"] > 0.5
    assert report["answer_quality"] > 0.0


def test_bakeoff_improves_or_keeps_champion():
    runner = DriveBakeoffRunner()
    before = float(runner.champion["metrics"]["drive_quality"])
    out = runner.run_bakeoff(rounds=8)
    after = float(out["champion"]["metrics"]["drive_quality"])
    assert out["rounds"] == 8
    assert after >= before - 1e-9
    assert out["telemetry"]["bakeoff_rounds"] >= 8


def test_api_endpoints():
    bakeoff_mod._RUNNER = DriveBakeoffRunner()
    with TestClient(app) as client:
        assert client.get("/health").json()["ok"] is True
        assert client.post("/api/drive/wake/eval").status_code == 200
        parsed = client.post("/api/drive/wake/parse", json={"text": "hey sala pause"})
        assert parsed.status_code == 200
        assert parsed.json()["kind"] == "pause"
        assert client.post("/api/drive/answer/eval").status_code == 200
        b = client.post("/api/drive/bakeoff", json={"rounds": 4})
        assert b.status_code == 200
        assert b.json()["rounds"] == 4
        assert client.get("/api/drive/champion").status_code == 200
        assert client.post("/api/drive/tuning/preset/snappy").status_code == 200
        bad = client.post("/api/drive/tuning/preset/nope")
        assert bad.status_code == 404


def test_tuning_validation():
    with pytest.raises(ValueError):
        DriveTuning(pause_submit_ms=10)
