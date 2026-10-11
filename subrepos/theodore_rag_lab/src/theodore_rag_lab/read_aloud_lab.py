"""Read-aloud pronunciation trainer surface for the Theodore RAG lab."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from aoep_shared.dictionary_curriculum import (
    load_progress,
    next_read_aloud,
    score_read_aloud,
)


def read_aloud_next(
    *,
    language: str = "en",
    learner_id: str = "local",
    seed: Optional[int] = None,
) -> dict[str, Any]:
    return next_read_aloud(language=language, learner_id=learner_id, seed=seed)


def read_aloud_score(
    *,
    sentence: str,
    heard: str,
    target_forms: Sequence[str],
    mouth_openness: Optional[float] = None,
    language: str = "en",
    learner_id: str = "local",
) -> dict[str, Any]:
    return score_read_aloud(
        sentence=sentence,
        heard=heard,
        target_forms=list(target_forms or []),
        mouth_openness=mouth_openness,
        language=language,
        learner_id=learner_id,
    )


def read_aloud_progress(*, learner_id: str = "local") -> dict[str, Any]:
    return load_progress(learner_id).to_dict()
