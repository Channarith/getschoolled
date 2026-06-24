"""Thin HTTP client from the orchestrator to the memory service.

The live teaching loop records per-student behavior/mastery and reads back the
aggregated adaptive signals so quiz difficulty and pacing personalize during a
class. This client is intentionally tiny and stdlib-only (matching
``scripts/retention_purge.py``); it is **best-effort and fails open**: when the
memory service is unset (``MEMORY_URL`` empty) or unreachable, reads return
neutral :class:`LearnerSignals` and writes are no-ops, so the single-service
offline demo and the unit tests keep working unchanged.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Optional

from aoep_shared.adaptive import LearnerSignals

# Short timeouts: a hung/slow memory service must never stall a live class.
# Writes are best-effort (fire-on-the-hot-path), so cap them tighter; the read
# blocks the quiz response (difficulty needs the result) so it gets a bit longer.
_WRITE_TIMEOUT_S = 1.0
_READ_TIMEOUT_S = 2.0

_log = logging.getLogger(__name__)


class MemoryClient:
    """Best-effort client to the memory service ``/behavior``/``/mastery``/``/learner``."""

    def __init__(self, base_url: Optional[str]) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.enabled = bool(self.base_url)

    # -- transport ---------------------------------------------------------- #
    def _post(self, path: str, body: dict) -> Optional[dict]:
        if not self.enabled:
            return None
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path, data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=_WRITE_TIMEOUT_S) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            # Connection refused / timeout / non-JSON => degrade open. Log at
            # debug so a misconfigured MEMORY_URL or a failing upstream is
            # diagnosable instead of silently looking like "memory disabled".
            _log.debug("memory POST %s failed: %s", path, exc)
            return None

    def _get(self, path: str) -> Optional[dict]:
        if not self.enabled:
            return None
        req = urllib.request.Request(self.base_url + path, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=_READ_TIMEOUT_S) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            _log.debug("memory GET %s failed: %s", path, exc)
            return None

    # -- writes (fire-and-forget) ------------------------------------------ #
    def record_behavior(
        self,
        student_id: str,
        topic: str,
        *,
        quiz_correct: Optional[bool] = None,
        response_latency_s: Optional[float] = None,
        attention: Optional[float] = None,
        asked_question: bool = False,
        saw_slide: bool = False,
    ) -> None:
        """POST a learning-behavior event. Best-effort; never raises."""
        self._post("/behavior", {
            "student_id": student_id,
            "topic": topic,
            "quiz_correct": quiz_correct,
            "response_latency_s": response_latency_s,
            "attention": attention,
            "asked_question": asked_question,
            "saw_slide": saw_slide,
        })

    def update_mastery(self, student_id: str, topic: str, correct: bool) -> Optional[float]:
        """POST a quiz outcome to update BKT mastery. Returns the new score or None."""
        resp = self._post("/mastery", {
            "student_id": student_id, "topic": topic, "correct": correct,
        })
        if resp is None:
            return None
        score = resp.get("mastery")
        return float(score) if isinstance(score, (int, float)) else None

    # -- reads (drive adaptive difficulty/pacing) -------------------------- #
    def learner_signals(self, student_id: str, topic: str) -> LearnerSignals:
        """GET aggregated adaptive signals. Returns neutral defaults on any failure."""
        resp = self._get(f"/learner/{student_id}/{topic}")
        if not resp:
            return LearnerSignals()
        defaults = LearnerSignals()
        return LearnerSignals(
            topic_mastery=_as_float(resp.get("topic_mastery"), defaults.topic_mastery),
            quiz_accuracy=_as_float(resp.get("quiz_accuracy"), defaults.quiz_accuracy),
            avg_response_latency_s=_as_float(
                resp.get("avg_response_latency_s"), defaults.avg_response_latency_s),
            attention_trend=_as_float(resp.get("attention_trend"), defaults.attention_trend),
            question_rate=_as_float(resp.get("question_rate"), defaults.question_rate),
        )


def _as_float(value, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) else default
