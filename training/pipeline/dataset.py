"""Build training examples from classes + audience context + feedback.

FAIRNESS GUARDRAIL: the model is conditioned ONLY on pedagogically-relevant
features (CONDITIONING_FEATURES). Protected attributes (race, ethnicity) are
NEVER emitted into a training example's context; ``assert_no_protected`` and
``redact_protected`` enforce this as defense in depth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

# Allowlist: only these audience features may condition the model.
CONDITIONING_FEATURES = (
    "age_band",
    "language",
    "reading_level",
    "learning_style",
    "professionalism",
    "prior_mastery",
)

# Protected attributes: retained only for aggregate bias monitoring, never used
# as model inputs / conditioning.
PROTECTED_ATTRIBUTES = ("race", "ethnicity")


@dataclass
class AudienceContext:
    age_band: str = "adult"            # child | teen | adult
    language: str = "en"
    reading_level: str = "intermediate"  # beginner | intermediate | advanced
    learning_style: str = "mixed"      # visual | auditory | kinesthetic | reading | mixed
    professionalism: str = "neutral"   # casual | neutral | formal
    prior_mastery: float = 0.5         # 0..1 from the mastery graph
    # Protected attributes (monitoring only; excluded from conditioning).
    race: Optional[str] = None
    ethnicity: Optional[str] = None

    def conditioning_dict(self) -> Dict[str, object]:
        """Only the allowlisted, non-protected pedagogical features."""
        return {k: getattr(self, k) for k in CONDITIONING_FEATURES}


def redact_protected(context: Dict[str, object]) -> Dict[str, object]:
    """Return a copy of ``context`` with any protected attributes removed."""
    return {k: v for k, v in context.items() if k not in PROTECTED_ATTRIBUTES}


def assert_no_protected(context: Dict[str, object]) -> None:
    leaked = [k for k in PROTECTED_ATTRIBUTES if k in context]
    if leaked:
        raise ValueError(
            f"protected attribute(s) {leaked} must not appear in training context"
        )


@dataclass
class TrainingExample:
    instruction: str
    context: Dict[str, object]
    response: str
    reward: float = 0.0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        ctx = redact_protected(self.context)
        assert_no_protected(ctx)
        return {
            "instruction": self.instruction,
            "context": ctx,
            "response": self.response,
            "reward": round(self.reward, 4),
            "tags": list(self.tags),
        }


def build_example(
    instruction: str,
    response: str,
    audience: AudienceContext,
    *,
    reward: float = 0.0,
    tags: Sequence[str] = (),
) -> TrainingExample:
    return TrainingExample(
        instruction=instruction.strip(),
        context=audience.conditioning_dict(),
        response=response.strip(),
        reward=reward,
        tags=list(tags),
    )


def class_session_to_examples(
    turns: Sequence[Dict[str, str]],
    audience: AudienceContext,
    *,
    rewards: Optional[Sequence[float]] = None,
    tags: Sequence[str] = (),
) -> List[TrainingExample]:
    """Pair student questions with teacher answers into training examples.

    ``turns`` is a transcript like ``[{"role": "student", "text": ...},
    {"role": "teacher", "text": ...}, ...]``. ``rewards`` (optional) aligns to
    each produced (student->teacher) pair.
    """
    examples: List[TrainingExample] = []
    i = 0
    pair_idx = 0
    while i < len(turns) - 1:
        a, b = turns[i], turns[i + 1]
        if a.get("role") == "student" and b.get("role") == "teacher":
            reward = rewards[pair_idx] if rewards and pair_idx < len(rewards) else 0.0
            examples.append(
                build_example(a["text"], b["text"], audience, reward=reward, tags=tags)
            )
            pair_idx += 1
            i += 2
        else:
            i += 1
    return examples


def to_jsonl(examples: Sequence[TrainingExample]) -> str:
    return "\n".join(json.dumps(e.to_dict(), ensure_ascii=False) for e in examples)
