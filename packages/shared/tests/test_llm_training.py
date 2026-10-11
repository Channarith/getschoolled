"""Shared all-in-one LLM training corpus (used by Theodore LLM Lab)."""

from __future__ import annotations

import json

from aoep_shared.llm_training import (
    SOURCES,
    assemble,
    examples_from_dictionary,
    examples_from_profile,
    export_dictionary_training_jsonl,
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


def test_sources_include_dictionary():
    assert "dictionary" in SOURCES


def test_examples_from_dictionary_gloss_and_inflection():
    rows = examples_from_dictionary({
        "lemma": "school",
        "language": "en",
        "gloss_en": "a place for teaching",
        "kind": "literal",
        "review_status": "approved",
        "inflections": {"plural": "schools"},
        "translations": {"km": {"target": "សាលា", "roman": "sala"}},
        "examples": [{"text": "She walked to school."}],
    })
    assert any(ex.source == "dictionary" for ex in rows)
    assert any("mean" in ex.instruction.lower() for ex in rows)
    assert any(ex.response == "schools" for ex in rows)
    assert any("Khmer" in ex.instruction for ex in rows)


def test_assemble_dictionary_staging(tmp_path, monkeypatch):
    root = tmp_path / "dictionary"
    staging = root / "staging"
    staging.mkdir(parents=True)
    row = {
        "id": "en-school",
        "lemma": "school",
        "language": "en",
        "gloss_en": "a place for teaching",
        "kind": "literal",
        "review_status": "auto",
        "inflections": {"plural": "schools"},
    }
    (staging / "en.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    monkeypatch.setenv("AOEP_DICTIONARY_DIR", str(root))
    examples = assemble([tmp_path / "empty"])
    assert any(ex.source == "dictionary" for ex in examples)
    out = root / "export" / "train.jsonl"
    n = export_dictionary_training_jsonl(root, out)
    assert n >= 1
    assert out.is_file()
