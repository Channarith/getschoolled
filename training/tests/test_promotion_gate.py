from promotion_gate import decide_promotion, subject_min


def test_same_score_is_not_progress():
    allowed, reason = decide_promotion(
        name="stem-qlora",
        champion="stem-qlora",
        frozen_accuracy=0.3151,
        previous_accuracy=0.3151,
        frozen_subject_min=0.50,
        split_subject_min=0.50,
        subject_floor=0.40,
    )
    assert allowed is False
    assert reason == "score_did_not_rise"


def test_a_single_linear_algebra_item_still_sets_the_floor():
    weakest = subject_min(
        {"geometry": 0.59, "linear-algebra": 0.1379, "math-olympiad": 0.2345},
        {"geometry": 1, "linear-algebra": 1, "math-olympiad": 4},
    )
    assert weakest == 0.1379
    from promotion_gate import _subject_min_from

    # A stored subject_min that ignored n=1 must not be trusted.
    recomputed = _subject_min_from(
        {
            "subject_min": 0.2345,
            "by_category": {"linear-algebra": 0.1379, "math-olympiad": 0.2345},
            "by_category_n": {"linear-algebra": 1, "math-olympiad": 4},
        },
        1,
    )
    assert recomputed == 0.1379


def test_stem_exam_is_required_when_the_gate_asks_for_it():
    allowed, reason = decide_promotion(
        name="stem-qlora",
        champion="stem-qlora",
        frozen_accuracy=0.50,
        previous_accuracy=None,
        frozen_subject_min=0.50,
        split_subject_min=0.50,
        subject_floor=0.40,
        stem_subject_min=None,
        stem_required=True,
    )
    assert allowed is False
    assert reason == "stem_frozen_eval_required"


def test_linear_algebra_cannot_hide_in_the_average():
    weakest = subject_min(
        {"geometry": 0.59, "linear-algebra": 0.14},
        {"geometry": 4, "linear-algebra": 4},
    )
    allowed, reason = decide_promotion(
        name="stem-qlora",
        champion="stem-qlora",
        frozen_accuracy=0.40,
        previous_accuracy=None,
        frozen_subject_min=weakest,
        split_subject_min=None,
        subject_floor=0.40,
    )
    assert weakest == 0.14
    assert allowed is False
    assert reason == "subject_floor:frozen"


def test_promotes_only_when_frozen_score_rises_and_subjects_clear():
    allowed, reason = decide_promotion(
        name="stem-qlora",
        champion="stem-qlora",
        frozen_accuracy=0.42,
        previous_accuracy=0.31,
        frozen_subject_min=0.41,
        split_subject_min=0.40,
        subject_floor=0.40,
    )
    assert allowed is True
    assert reason == "score_rose"


def test_missing_frozen_exam_blocks_promotion():
    allowed, reason = decide_promotion(
        name="stem-qlora",
        champion="stem-qlora",
        frozen_accuracy=None,
        previous_accuracy=None,
        frozen_subject_min=None,
        split_subject_min=0.9,
        subject_floor=0.40,
    )
    assert allowed is False
    assert reason == "frozen_eval_required"
