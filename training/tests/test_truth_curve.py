from truth_curve import record_human_agreement, truth_fields


def test_abstention_is_detected_and_human_agreement_starts_empty():
    row = {
        "id": "abstain-001",
        "instruction": "Passage from the lesson 'Maps':\nRivers flow downhill.\n\nUsing only this passage, what can you tell me about Linear Algebra?",
        "tags": ["Science", "abstain"],
    }
    fields = truth_fields(
        "The passage does not cover that, so I can't answer it from this material.",
        row,
    )
    assert fields["abstained"] is True
    assert fields["abstain_expected"] is True
    assert fields["abstain_correct"] is True
    assert fields["human_agreement"] is None
    assert fields["groundedness"] >= 0


def test_human_agreement_fills_a_later_row(tmp_path):
    from truth_curve import append_truth_row

    path = tmp_path / "truth.jsonl"
    append_truth_row(str(path), {"id": "recall-001", "human_agreement": None, "groundedness": 0.8})
    touched = record_human_agreement(str(path), "recall-001", True)
    assert touched == 1
    text = path.read_text(encoding="utf-8")
    assert '"human_agreement": true' in text
