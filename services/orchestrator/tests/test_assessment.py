"""Phase 5 - assessment unit tests."""

from aoep_shared.adaptive import Difficulty
from aoep_shared.assessment import (
    Poll,
    QuizItem,
    definition_items_from_passages,
    grade,
)

PASSAGES = [
    "Photosynthesis: plants convert light into chemical energy stored in sugars.",
    "Chlorophyll: the green pigment that absorbs light for photosynthesis.",
    "Oxygen: a byproduct of photosynthesis released into the air.",
    "Glucose: the sugar a plant uses for energy.",
]


def test_definition_items_have_correct_answer_mapping():
    items = definition_items_from_passages(PASSAGES, "photosynthesis", max_items=4)
    assert len(items) == 4
    for i, item in enumerate(items):
        # The option at answer_index must be the term's own definition.
        term = PASSAGES[i].split(":", 1)[0]
        expected_def = PASSAGES[i].split(":", 1)[1].strip()
        assert item.answer == expected_def
        assert term.lower() in item.prompt.lower()
        assert len(item.options) >= 2


def test_definition_items_skip_malformed_passages():
    items = definition_items_from_passages(["no colon here", "A: def a"], "t")
    assert len(items) == 1
    assert items[0].answer == "def a"


def test_grade_correct_and_wrong_targets_by_difficulty():
    item = QuizItem(
        item_id="t-0",
        topic="t",
        prompt="?",
        options=["right", "wrong"],
        answer_index=0,
        difficulty=Difficulty.HARD,
    )
    good = grade(item, 0)
    bad = grade(item, 1)
    assert good.correct is True and good.mastery_target == 1.0
    assert bad.correct is False and bad.mastery_target == 0.3  # hard wrong is lenient


def test_grade_easy_wrong_is_strict():
    item = QuizItem("e-0", "t", "?", ["a", "b"], answer_index=1, difficulty=Difficulty.EASY)
    assert grade(item, 0).mastery_target == 0.0
    assert grade(item, 1).mastery_target == 0.6


def test_poll_vote_tally_leader():
    poll = Poll("p1", "Favorite?", ["A", "B", "C"])
    poll.vote(0)
    poll.vote(1)
    poll.vote(1)
    assert poll.tally() == {"A": 1, "B": 2, "C": 0}
    assert poll.leader() == "B"
    assert Poll("p2", "?", ["A"]).leader() is None
