"""Education LLM training data pipeline (scaffold).

Pure, dependency-free helpers that turn class transcripts + audience context +
user feedback into training examples. Actual fine-tuning runs on a separate GPU
cloud agent (see ../README.txt).
"""

from .dataset import (
    CONDITIONING_FEATURES,
    PROTECTED_ATTRIBUTES,
    AudienceContext,
    TrainingExample,
    build_example,
    class_session_to_examples,
    redact_protected,
    to_jsonl,
)
from .feedback import Feedback, aggregate, reward_from_feedback

__all__ = [
    "CONDITIONING_FEATURES",
    "PROTECTED_ATTRIBUTES",
    "AudienceContext",
    "TrainingExample",
    "build_example",
    "class_session_to_examples",
    "redact_protected",
    "to_jsonl",
    "Feedback",
    "aggregate",
    "reward_from_feedback",
]
