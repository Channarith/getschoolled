"""Foresight - portable multimodal prediction/inference engine (patent-pending).

A reusable engine (numpy reference; CUDA/torch backend swappable) implementing
multimodal fusion, a transformer encoder + pooled state, a finite query-type
router, attention over a "liked pattern" library, parallel multi-head outputs,
and a relational graph head, with multi-threaded batch inference.
"""

from .education import (
    CourseFeature,
    LearnerForesight,
    Recommendation,
    StudentProfile,
)
from .engine import (
    FORESIGHT_VERSION,
    ClassificationHead,
    CountHead,
    ForesightConfig,
    ForesightEngine,
    ForesightOutput,
    ProbabilityHead,
    RankingHead,
    RelationalGraphHead,
    multimodal_fuse,
    pool,
    scaled_dot_product_attention,
    sigmoid,
    softmax,
)

__all__ = [
    "FORESIGHT_VERSION",
    "ForesightEngine",
    "ForesightConfig",
    "ForesightOutput",
    "ClassificationHead",
    "ProbabilityHead",
    "CountHead",
    "RankingHead",
    "RelationalGraphHead",
    "scaled_dot_product_attention",
    "softmax",
    "sigmoid",
    "pool",
    "multimodal_fuse",
    "LearnerForesight",
    "StudentProfile",
    "CourseFeature",
    "Recommendation",
]
