"""In-lab lesson alert action executor.

The live monitor's "Run lesson action" button posts here so each alert does a
real, observable side-effect inside the sandbox (private message log, rejoin
prompt, integrity game challenge, watchlist) — not just an acknowledge toast.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any

from .games import WebcamLearningGameEngine
from .types import ClassMode, WebcamGameType


def _action_presentation(
    action_key: str,
    participant_id: str,
) -> dict[str, str]:
    """Return the visual direction and spoken line for the live Theodore stage."""
    learner = participant_id.replace("-", " ").replace("_", " ").strip().title()
    learner = learner or "everyone"
    presentations = {
        "notify_student_privately_and_reinforce_integrity": {
            "visual_effect": "shield",
            "visual_icon": "🛡️",
            "visual_title": "Integrity focus challenge",
            "visual_body": f"Theodore is starting a private focus check for {learner}.",
            "speech_text": (
                f"{learner}, let's reset together. Please face the lesson and show me "
                "you are ready. I have started a quick focus challenge for you."
            ),
        },
        "alert_lesson_and_request_student_rejoin": {
            "visual_effect": "wave",
            "visual_icon": "👋",
            "visual_title": "Come back to the lesson",
            "visual_body": f"Theodore is calling {learner} back into class.",
            "speech_text": (
                f"{learner}, we paused your part of the lesson. Come back when you "
                "are ready, and I will help you continue where you stopped."
            ),
        },
        "monitor_and_prompt_if_state_persists": {
            "visual_effect": "scan",
            "visual_icon": "🔎",
            "visual_title": "Watching for a change",
            "visual_body": f"Theodore is monitoring {learner} before intervening.",
            "speech_text": (
                f"I am keeping an eye on the learning signal for {learner}. "
                "If it continues, I will step in with a helpful prompt."
            ),
        },
        "review_silhouette_and_confirm_presence": {
            "visual_effect": "spotlight",
            "visual_icon": "💡",
            "visual_title": "Camera presence check",
            "visual_body": f"Theodore is checking whether {learner} is visible.",
            "speech_text": (
                f"{learner}, I can see a shape but not your face. Please move into "
                "the light, sit a little closer, and look toward the screen."
            ),
        },
        "acknowledge_positive_engagement": {
            "visual_effect": "celebrate",
            "visual_icon": "⭐",
            "visual_title": "Great learning energy",
            "visual_body": f"Theodore is celebrating {learner}'s engagement.",
            "speech_text": (
                f"Great work, {learner}! Your focus and energy are helping the "
                "lesson. Keep it going!"
            ),
        },
        "check_in_privately_and_offer_support": {
            "visual_effect": "heart",
            "visual_icon": "💙",
            "visual_title": "Private wellbeing check-in",
            "visual_body": f"Theodore is offering {learner} support.",
            "speech_text": (
                f"Hey {learner}, I am checking in. If you need help or a short "
                "break, tell me. We can work through this together."
            ),
        },
        "prompt_learner_to_refocus": {
            "visual_effect": "refocus",
            "visual_icon": "🎯",
            "visual_title": "Refocus with Theodore",
            "visual_body": f"Theodore is guiding {learner} back to the lesson.",
            "speech_text": (
                f"{learner}, eyes back to the lesson. Take one breath, find the "
                "current step, and let's continue together."
            ),
        },
        "review_group_interventions": {
            "visual_effect": "dashboard",
            "visual_icon": "📊",
            "visual_title": "Reviewing class support",
            "visual_body": "Theodore is reviewing interventions for the whole class.",
            "speech_text": (
                "I am reviewing the class now. I will prioritize learners who need "
                "help, invite missing students back, and keep the lesson moving."
            ),
        },
    }
    return presentations.get(
        action_key,
        {
            "visual_effect": "announce",
            "visual_icon": "✨",
            "visual_title": "Theodore takes action",
            "visual_body": f"Theodore is responding for {learner}.",
            "speech_text": (
                f"I have recorded the lesson action for {learner}. "
                "I will keep the class informed."
            ),
        },
    )


@dataclass
class LessonActionResult:
    ok: bool
    action: str
    code: str
    participant_id: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


class LessonActionLog:
    """Bounded per-session log of executed lesson actions."""

    def __init__(self, max_events: int = 200, max_messages: int = 500) -> None:
        self._max_events = max_events
        self._max_messages = max_messages
        self._events: dict[str, list[dict[str, Any]]] = {}
        self._private_messages: dict[str, list[dict[str, Any]]] = {}
        self._watchlist: dict[str, set[str]] = {}
        self._rejoin_requests: dict[str, list[str]] = {}

    def _append(self, session_id: str, event: dict[str, Any]) -> None:
        bucket = self._events.setdefault(session_id, [])
        bucket.append(event)
        if len(bucket) > self._max_events:
            del bucket[: len(bucket) - self._max_events]

    def _append_private_message(self, session_id: str, note: dict[str, Any]) -> None:
        bucket = self._private_messages.setdefault(session_id, [])
        bucket.append(note)
        if len(bucket) > self._max_messages:
            del bucket[: len(bucket) - self._max_messages]

    def _append_rejoin(self, session_id: str, participant_id: str) -> None:
        bucket = self._rejoin_requests.setdefault(session_id, [])
        bucket.append(participant_id)
        if len(bucket) > self._max_messages:
            del bucket[: len(bucket) - self._max_messages]

    def events(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._events.get(session_id, []))

    def private_messages(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._private_messages.get(session_id, []))

    def watchlist(self, session_id: str) -> list[str]:
        return sorted(self._watchlist.get(session_id, set()))

    def rejoin_requests(self, session_id: str) -> list[str]:
        return list(self._rejoin_requests.get(session_id, []))

    def execute(
        self,
        *,
        session_id: str,
        code: str,
        action: str,
        participant_id: str = "",
        message: str = "",
        game_engine: WebcamLearningGameEngine | None = None,
    ) -> LessonActionResult:
        action_key = (action or "").strip().lower()
        now = int(time() * 1000)
        details: dict[str, Any] = {"timestamp_ms": now, "code": code}
        details["presentation"] = _action_presentation(action_key, participant_id)

        if action_key == "notify_student_privately_and_reinforce_integrity":
            note = {
                "participant_id": participant_id,
                "timestamp_ms": now,
                "channel": "private",
                "body": (
                    f"Integrity check: we noticed distraction signals "
                    f"({code}). Please keep eyes on the lesson."
                ),
            }
            self._append_private_message(session_id, note)
            challenge = None
            if game_engine is not None and participant_id:
                challenge = game_engine.create_challenge(
                    session_id=session_id,
                    mode=ClassMode.GROUP,
                    learning_prompt="Confirm you are still focused on the lesson.",
                    participant_ids=[participant_id],
                    preferred_game_type=WebcamGameType.INTEGRITY_GUARD,
                )
                details["challenge_id"] = challenge.challenge_id
                details["challenge_title"] = challenge.title
            details["private_message"] = note
            summary = (
                f"Private integrity message sent to {participant_id or 'class'}"
                + (f"; issued game '{challenge.title}'" if challenge else "")
            )
        elif action_key == "alert_lesson_and_request_student_rejoin":
            self._append_rejoin(session_id, participant_id or "unknown")
            details["rejoin_requested_for"] = participant_id
            summary = f"Lesson alerted; rejoin requested for {participant_id or 'unknown'}"
        elif action_key == "monitor_and_prompt_if_state_persists":
            if participant_id:
                self._watchlist.setdefault(session_id, set()).add(participant_id)
            details["watchlist"] = self.watchlist(session_id)
            summary = f"Added {participant_id or 'session'} to the watchlist"
        elif action_key == "review_silhouette_and_confirm_presence":
            if participant_id:
                self._watchlist.setdefault(session_id, set()).add(participant_id)
            note = {
                "participant_id": participant_id,
                "timestamp_ms": now,
                "channel": "private",
                "body": (
                    "We see a filled shape but no live face. Please sit closer to "
                    "the camera and face the screen."
                ),
            }
            self._append_private_message(session_id, note)
            details["private_message"] = note
            summary = f"Silhouette review: prompted {participant_id or 'learner'} to show face"
        elif action_key == "acknowledge_positive_engagement":
            summary = (
                f"Positive engagement noted for {participant_id or 'class'} — "
                "great energy, keep it up!"
            )
            details["acknowledged"] = True
        elif action_key == "check_in_privately_and_offer_support":
            note = {
                "participant_id": participant_id,
                "timestamp_ms": now,
                "channel": "private",
                "body": (
                    "Hey, just checking in — if anything's on your mind or you need "
                    "a break, let me know. We're here for you."
                ),
            }
            self._append_private_message(session_id, note)
            details["private_message"] = note
            summary = f"Wellbeing check-in sent privately to {participant_id or 'learner'}"
        elif action_key == "prompt_learner_to_refocus":
            summary = f"Refocus prompt issued to {participant_id or 'learner'}"
            details["prompted"] = True
        elif action_key == "review_group_interventions":
            watched = self.watchlist(session_id)
            summary = (
                f"Reviewed group interventions "
                f"({len(watched)} on watchlist, "
                f"{len(self.rejoin_requests(session_id))} rejoin requests)"
            )
            details["watchlist"] = watched
            details["rejoin_requests"] = self.rejoin_requests(session_id)
        else:
            summary = f"Recorded lesson action '{action or 'unknown'}' for {participant_id or 'class'}"
            details["raw_action"] = action

        event = {
            "timestamp_ms": now,
            "code": code,
            "action": action_key or action,
            "participant_id": participant_id,
            "message": message,
            "summary": summary,
            "details": details,
        }
        self._append(session_id, event)
        return LessonActionResult(
            ok=True,
            action=action_key or action,
            code=code,
            participant_id=participant_id,
            summary=summary,
            details=details,
        )
