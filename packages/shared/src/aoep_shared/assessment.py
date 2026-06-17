"""Phase 5 - assessment: quizzes, definition/key-point checks, polls, mastery.

Generates multiple-choice checks from curriculum passages, grades answers, and
maps outcomes to a mastery update target that feeds the adaptive policy
(phase 4). Pure and deterministic (no LLM/network), so it is fully testable
offline; in production an LLM can author richer items behind the same shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .adaptive import Difficulty


@dataclass
class QuizItem:
    item_id: str
    topic: str
    prompt: str
    options: List[str]
    answer_index: int
    difficulty: Difficulty = Difficulty.MEDIUM

    @property
    def answer(self) -> str:
        return self.options[self.answer_index]


@dataclass
class GradeResult:
    item_id: str
    correct: bool
    mastery_target: float   # feed into MemoryStore.update_mastery target
    difficulty: Difficulty


@dataclass
class Poll:
    poll_id: str
    prompt: str
    options: List[str]
    votes: Dict[int, int] = field(default_factory=dict)

    def vote(self, option_index: int) -> None:
        if not 0 <= option_index < len(self.options):
            raise IndexError("option_index out of range")
        self.votes[option_index] = self.votes.get(option_index, 0) + 1

    def tally(self) -> Dict[str, int]:
        return {self.options[i]: self.votes.get(i, 0) for i in range(len(self.options))}

    def leader(self) -> Optional[str]:
        if not self.votes:
            return None
        idx = max(self.votes, key=self.votes.get)
        return self.options[idx]


def _split_passage(passage: str) -> Optional[Tuple[str, str]]:
    """Split a 'Title: body' curriculum passage into (term, definition)."""
    if ":" not in passage:
        return None
    title, body = passage.split(":", 1)
    title, body = title.strip(), body.strip()
    if not title or not body:
        return None
    return title, body


def definition_items_from_passages(
    passages: List[str],
    topic: str,
    *,
    max_items: int = 4,
    distractors: int = 2,
    difficulty: Difficulty = Difficulty.MEDIUM,
) -> List[QuizItem]:
    """Build definition-check MCQs: 'Which statement describes <term>?'.

    Distractors are other passages' definitions. Deterministic (no RNG): the
    correct option is placed at ``i % num_options`` so tests are stable.
    """
    parsed = [p for p in (_split_passage(s) for s in passages) if p is not None]
    items: List[QuizItem] = []
    for i, (term, definition) in enumerate(parsed[:max_items]):
        others = [d for j, (_, d) in enumerate(parsed) if j != i]
        chosen = others[:distractors]
        options = [definition] + chosen
        num = len(options)
        answer_index = i % num
        # Move the correct option (currently at 0) to answer_index.
        options[0], options[answer_index] = options[answer_index], options[0]
        items.append(
            QuizItem(
                item_id=f"{topic}-{i}",
                topic=topic,
                prompt=f"Which statement best describes: {term}?",
                options=options,
                answer_index=answer_index,
                difficulty=difficulty,
            )
        )
    return items


# Mastery target by difficulty: harder correct answers are stronger evidence of
# mastery; wrong answers pull mastery down (more so for easier items).
_CORRECT_TARGET = {
    Difficulty.EASY: 0.6,
    Difficulty.MEDIUM: 0.8,
    Difficulty.HARD: 1.0,
}
_WRONG_TARGET = {
    Difficulty.EASY: 0.0,
    Difficulty.MEDIUM: 0.1,
    Difficulty.HARD: 0.3,
}


def grade(item: QuizItem, answer_index: int) -> GradeResult:
    correct = answer_index == item.answer_index
    target = (
        _CORRECT_TARGET[item.difficulty]
        if correct
        else _WRONG_TARGET[item.difficulty]
    )
    return GradeResult(
        item_id=item.item_id,
        correct=correct,
        mastery_target=target,
        difficulty=item.difficulty,
    )
