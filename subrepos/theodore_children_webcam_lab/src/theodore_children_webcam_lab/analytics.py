"""Aggregate-only, privacy-safe fun analytics."""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from threading import Lock
from typing import Any

FORBIDDEN_KEYS = {
    "audio", "video", "frame", "frames", "image", "landmarks", "skeleton",
    "transcript", "heard", "name", "email", "student_id", "face_id",
    "behavior", "misbehave",
}
COMPONENT_KEYS = {"play", "spark", "giggle", "keep_going", "drop_off"}
MAX_SAMPLES = 400
ALLOWED_KEYS = {
    "activity_id", "age_band", "outcome", "attempts", "duration_ms", "fun_score",
    "components", "celebration_kind", "miss_gag_id", "theme_pack", "seated_only",
    "hit_count", "spawn_count", "round", "time_limit_ms", "time_remaining_ms",
    "expression", "region",
}


def sanitize_event(raw: dict[str, Any]) -> dict[str, Any]:
    lowered = {str(key).lower() for key in raw}
    forbidden = lowered & FORBIDDEN_KEYS
    if forbidden:
        raise ValueError(f"Private analytics fields are not accepted: {sorted(forbidden)}")
    event = {key: value for key, value in raw.items() if key in ALLOWED_KEYS}
    activity = str(event.get("activity_id") or "").strip()
    if not activity or len(activity) > 80:
        raise ValueError("activity_id is required and must be at most 80 characters")
    event["activity_id"] = activity
    event["fun_score"] = max(0, min(100, int(event.get("fun_score") or 0)))
    event["duration_ms"] = max(0, min(3_600_000, int(event.get("duration_ms") or 0)))
    event["attempts"] = max(0, min(100, int(event.get("attempts") or 0)))
    event["age_band"] = event.get("age_band") if event.get("age_band") in {"4-6", "7-10"} else "unknown"
    raw_components = event.get("components")
    if raw_components is None:
        event.pop("components", None)
    elif not isinstance(raw_components, dict):
        raise ValueError("components must be a score breakdown object")
    else:
        event["components"] = {
            key: int(value)
            for key, value in raw_components.items()
            if key in COMPONENT_KEYS
        }
    return event


class AggregateAnalytics:
    """Retain aggregates only; no event or child history."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._scores: dict[str, list[int]] = defaultdict(list)
        self._durations: dict[str, list[int]] = defaultdict(list)
        self._outcomes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def record(self, raw: dict[str, Any]) -> dict[str, Any]:
        event = sanitize_event(raw)
        activity = event["activity_id"]
        with self._lock:
            scores = self._scores[activity]
            durations = self._durations[activity]
            scores.append(event["fun_score"])
            durations.append(event["duration_ms"])
            if len(scores) > MAX_SAMPLES:
                del scores[: len(scores) - MAX_SAMPLES]
                del durations[: len(durations) - MAX_SAMPLES]
            self._outcomes[activity][str(event.get("outcome") or "unknown")] += 1
        return {"accepted": True, "activity_id": activity}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            activities = {}
            for activity, scores in self._scores.items():
                durations = self._durations[activity]
                activities[activity] = {
                    "plays": len(scores),
                    "fun_score_median": round(median(scores), 1),
                    "duration_ms_median": round(median(durations), 1),
                    "outcomes": dict(self._outcomes[activity]),
                }
        return {"activities": activities, "activity_count": len(activities)}
