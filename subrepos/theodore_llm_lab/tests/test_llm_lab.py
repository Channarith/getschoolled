"""Theodore LLM training lab: corpus, fairness, robot pack, HTTP console."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from aoep_shared.llm_training import (
    assemble,
    examples_from_lesson,
    examples_from_profile,
    robot_pack,
    simulate_robot_turn,
    validate_examples,
)

from theodore_llm_lab.main import app
from theodore_llm_lab.paths import fixture_root


def test_fixtures_cover_every_learning_channel():
    examples = assemble([fixture_root()])
    sources = {ex.source for ex in examples}
    assert sources == {"library", "profiles", "webcam", "audio", "games", "rag"}
    assert len(examples) >= 10


def test_profiles_never_leak_protected_or_pii():
    rows = examples_from_profile(
        {
            "age_band": "child",
            "language": "km",
            "race": "secret",
            "ethnicity": "secret",
            "name": "Mina",
            "email": "mina@example.com",
        }
    )
    dumped = rows[0].to_dict()
    ctx = dumped["context"]
    assert "race" not in ctx
    assert "ethnicity" not in ctx
    assert "name" not in ctx
    assert "email" not in ctx
    blob = json.dumps(dumped)
    assert "Mina" not in blob
    assert "secret" not in blob


def test_lesson_slides_become_teach_turns():
    text = (
        "LESSON: Demo\nLANGUAGE: en\n\n"
        "SLIDE 1 | Hello\nBody line.\nNARRATION: Speak this.\n"
        "FACT: Remember this.\n"
    )
    rows = examples_from_lesson(text)
    assert len(rows) == 2
    assert rows[0].source == "library"
    assert "Speak this" in rows[0].response
    assert "Remember this" in rows[1].response


def test_validate_rejects_empty_and_protected_context():
    assert validate_examples([]) == ["dataset is empty"]
    problems = validate_examples(
        [{"instruction": "q", "response": "a", "context": {"race": "x"}}]
    )
    assert problems


def test_robot_pack_is_gguf_onnx_and_offline():
    pack = robot_pack(example_count=12, sources={"library": 4, "webcam": 2})
    roles = {m["role"]: m["format"] for m in pack["models"]}
    assert roles["llm"] == "gguf"
    assert roles["asr"] == "onnx"
    assert pack["deploy_mode"] == "edge"
    assert pack["embodiment"] == "robot"
    assert pack["portable"] is True
    turn = simulate_robot_turn("Let's count to three.")
    assert turn["offline"] is True
    assert turn["say"] == "Let's count to three."
    assert turn["mock_actions"][0]["modality"] == "speech"


def test_http_console_assemble_check_pack_and_live_audio():
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["ok"] is True
        assert health["fixture_examples"] >= 10
        page = client.get("/").text
        assert "Train our own portable education LLM" in page
        assert "live-audio/client.js" in page
        assembled = client.post("/api/llm/assemble", json={"include_curriculum": False}).json()
        assert assembled["ok"] is True
        assert assembled["by_source"]["library"] >= 1
        checked = client.post("/api/llm/check", json={}).json()
        assert checked["ok"] is True
        assert checked["problems"] == []
        packed = client.post("/api/llm/robot-pack", json={}).json()
        assert packed["pack"]["models"][0]["quantization"] == "Q4_K_M"
        robot = client.post("/api/llm/robot-turn", json={"text": "Wave hello."}).json()
        assert robot["ok"] is True
        status = client.get("/api/live-audio/status")
        assert status.status_code == 200
