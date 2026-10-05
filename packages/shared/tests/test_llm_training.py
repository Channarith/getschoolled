"""Shared all-in-one LLM training corpus (used by Theodore LLM Lab)."""

from __future__ import annotations

from aoep_shared.llm_training import (
    assemble,
    examples_from_profile,
    robot_pack,
    validate_examples,
    write_jsonl,
)


def test_write_jsonl_roundtrip(tmp_path):
    examples = examples_from_profile({"age_band": "teen", "language": "en"})
    path = tmp_path / "train.jsonl"
    n = write_jsonl(examples, path)
    assert n == 1
    line = path.read_text(encoding="utf-8").strip()
    assert "instruction" in line
    assert "teen" in line


def test_assemble_empty_root(tmp_path):
    assert assemble([tmp_path]) == []
    assert validate_examples([]) == ["dataset is empty"]


def test_robot_pack_flash_contract():
    pack = robot_pack()
    assert any("package_edge.sh" in step for step in pack["flash"])
    assert pack["safety"]["protected_attributes_in_weights"] is False
