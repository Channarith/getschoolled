"""Correction model, bulk parsing, and training-example conversion tests."""

import json

from aoep_shared.corrections import (
    PROTECTED_ATTRIBUTES,
    Correction,
    CorrectionStatus,
    TargetKind,
    correction_to_training_example,
    parse_bulk,
)


def test_correction_defaults():
    c = Correction(target_id="deck-1", corrected="fixed")
    assert c.id and c.status == CorrectionStatus.SUBMITTED
    assert c.target_kind == TargetKind.COURSE


def test_parse_bulk_jsonl():
    blob = "\n".join([
        json.dumps({"target_kind": "deck", "target_id": "d1", "locator": "0",
                    "corrected": "Plants release oxygen."}),
        json.dumps({"target_kind": "model", "locator": "what gas?", "corrected": "oxygen"}),
    ])
    rows = parse_bulk(blob, "jsonl")
    assert len(rows) == 2
    assert rows[0].target_kind == TargetKind.DECK
    assert rows[1].target_kind == TargetKind.MODEL


def test_parse_bulk_csv():
    csv_blob = (
        "target_kind,target_id,locator,corrected,rationale\n"
        "deck,d1,0,Corrected text,was wrong\n"
        "model,,what gas do plants release?,oxygen,clarity\n"
    )
    rows = parse_bulk(csv_blob, "csv")
    assert len(rows) == 2
    assert rows[1].corrected == "oxygen"


def test_correction_to_training_example_is_gold_and_redacted():
    c = Correction(
        target_kind=TargetKind.MODEL,
        locator="what gas do plants release?",
        corrected="Plants release oxygen during photosynthesis.",
        audience={"language": "en", "reading_level": "beginner",
                  "race": "X", "ethnicity": "Y"},
    )
    ex = correction_to_training_example(c)
    assert ex["reward"] == 1.0
    assert ex["instruction"] == "what gas do plants release?"
    assert ex["response"].startswith("Plants release oxygen")
    for p in PROTECTED_ATTRIBUTES:
        assert p not in ex["context"]
    assert ex["context"]["language"] == "en"
    assert "correction" in ex["tags"]


def test_parse_bulk_bad_format():
    import pytest

    with pytest.raises(ValueError):
        parse_bulk("x", "xml")
