"""High-level clients for the core AOEP developer workflows."""

from __future__ import annotations

import urllib.parse
from typing import Any

from aoep_shared.adaptive import LearnerSignals

from .transport import JSONTransport


def _segment(value: str) -> str:
    return urllib.parse.quote(value, safe="")


class ServiceClient:
    """Common operations available on every AOEP service."""

    def __init__(self, transport: JSONTransport) -> None:
        self.transport = transport

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Call an endpoint not yet represented by a typed convenience method."""

        return self.transport.request(
            method,
            path,
            query=query,
            json_body=json_body,
            headers=headers,
        )

    def health(self) -> dict[str, Any]:
        return self.transport.request("GET", "/health")

    def version(self) -> dict[str, Any]:
        return self.transport.request("GET", "/version")


class OrchestratorClient(ServiceClient):
    """Teaching-loop, lesson-planning, and learner Q&A operations."""

    def list_lessons(
        self,
        *,
        query: str = "",
        language: str = "",
        audience: str = "",
    ) -> list[dict[str, Any]]:
        return self.transport.request(
            "GET",
            "/api/lessons",
            query={"q": query, "language": language, "audience": audience},
        )

    def lesson_plan(
        self,
        lesson_id: str,
        *,
        profile_score: str = "",
        session_length: str = "medium",
        session_budget_min: int | None = None,
        observed_pace: str = "",
    ) -> dict[str, Any]:
        return self.transport.request(
            "POST",
            f"/api/lessons/{_segment(lesson_id)}/plan",
            json_body={
                "profile_score": profile_score,
                "session_length": session_length,
                "session_budget_min": session_budget_min,
                "observed_pace": observed_pace,
            },
        )

    def start_session(
        self,
        lesson_id: str,
        *,
        class_type: str = "group",
        student_id: str | None = None,
        profile_score: str = "",
        session_length: str = "",
        session_budget_min: int | None = None,
        observed_pace: str = "",
    ) -> dict[str, Any]:
        return self.transport.request(
            "POST",
            "/api/sessions",
            json_body={
                "lesson_id": lesson_id,
                "class_type": class_type,
                "student_id": student_id,
                "profile_score": profile_score,
                "session_length": session_length,
                "session_budget_min": session_budget_min,
                "observed_pace": observed_pace,
            },
        )

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self.transport.request(
            "GET", f"/api/sessions/{_segment(session_id)}"
        )

    def advance(self, session_id: str) -> dict[str, Any]:
        return self.transport.request(
            "POST", f"/api/sessions/{_segment(session_id)}/advance"
        )

    def ask(
        self,
        session_id: str,
        text: str,
        *,
        language: str = "en",
    ) -> dict[str, Any]:
        return self.transport.request(
            "POST",
            f"/api/sessions/{_segment(session_id)}/ask",
            json_body={"text": text, "language": language},
        )


class IdentityClient(ServiceClient):
    """Accounts, user sessions, and rewards operations."""

    def signup(
        self,
        email: str,
        password: str,
        *,
        display_name: str = "",
        region: str = "us",
        update_session: bool = True,
    ) -> dict[str, Any]:
        result = self.transport.request(
            "POST",
            "/auth/signup",
            json_body={
                "email": email,
                "password": password,
                "display_name": display_name,
                "region": region,
            },
        )
        if update_session and isinstance(result.get("token"), str):
            self.transport.set_bearer_token(result["token"])
        return result

    def login(
        self,
        email: str,
        password: str,
        *,
        update_session: bool = True,
    ) -> dict[str, Any]:
        result = self.transport.request(
            "POST",
            "/auth/login",
            json_body={"email": email, "password": password},
        )
        if update_session and isinstance(result.get("token"), str):
            self.transport.set_bearer_token(result["token"])
        return result

    def me(self) -> dict[str, Any]:
        return self.transport.request("GET", "/auth/me")

    def rewards(self) -> dict[str, Any]:
        return self.transport.request("GET", "/rewards")

    def rewards_catalog(self) -> dict[str, Any]:
        return self.transport.request("GET", "/rewards/catalog")

    def redeem_reward(self, prize_id: str) -> dict[str, Any]:
        return self.transport.request(
            "POST", "/rewards/redeem", json_body={"prize_id": prize_id}
        )


class CurriculumClient(ServiceClient):
    """Unified learnable-content and course-catalog operations."""

    def search(
        self,
        query: str = "",
        *,
        category: str | None = None,
        source: str | None = None,
        media_format: str | None = None,
        level: str | None = None,
        language: str | None = None,
        maturity: str | None = None,
        hands_on: bool | None = None,
        tag: str | None = None,
        audience: str | None = None,
        core_skill: bool | None = None,
        kids: bool = False,
        limit: int = 50,
        offset: int = 0,
        locale: str = "en",
    ) -> dict[str, Any]:
        return self.transport.request(
            "GET",
            "/learn/search",
            query={
                "q": query,
                "category": category,
                "source": source,
                "format": media_format,
                "level": level,
                "language": language,
                "maturity": maturity,
                "hands_on": hands_on,
                "tag": tag,
                "audience": audience,
                "core_skill": core_skill,
                "kids": kids,
                "limit": limit,
                "offset": offset,
                "locale": locale,
            },
        )

    def get_item(self, global_id: str) -> dict[str, Any]:
        return self.transport.request(
            "GET", f"/learn/items/{_segment(global_id)}"
        )

    def list_courses(self) -> list[dict[str, Any]]:
        return self.transport.request("GET", "/courses")

    def get_course(self, course_id: str) -> dict[str, Any]:
        return self.transport.request("GET", f"/courses/{_segment(course_id)}")

    def catalog(self, *, delivery_mode: str | None = None) -> dict[str, Any]:
        return self.transport.request(
            "GET", "/catalog", query={"delivery_mode": delivery_mode}
        )


class MemoryClient(ServiceClient):
    """Adaptive learner-signal operations.

    Memory routes require an internal token in standard deployments. Unlike the
    orchestrator's best-effort hot-path adapter, this public SDK client surfaces
    service failures to the developer.
    """

    def learner_signals(self, student_id: str, topic: str) -> LearnerSignals:
        result = self.transport.request(
            "GET", f"/learner/{_segment(student_id)}/{_segment(topic)}"
        )
        defaults = LearnerSignals()
        return LearnerSignals(
            topic_mastery=_number(result.get("topic_mastery"), defaults.topic_mastery),
            quiz_accuracy=_number(result.get("quiz_accuracy"), defaults.quiz_accuracy),
            avg_response_latency_s=_number(
                result.get("avg_response_latency_s"),
                defaults.avg_response_latency_s,
            ),
            attention_trend=_number(
                result.get("attention_trend"), defaults.attention_trend
            ),
            question_rate=_number(result.get("question_rate"), defaults.question_rate),
        )

    def record_behavior(
        self,
        student_id: str,
        topic: str,
        *,
        quiz_correct: bool | None = None,
        response_latency_s: float | None = None,
        attention: float | None = None,
        asked_question: bool = False,
        saw_slide: bool = False,
    ) -> dict[str, Any]:
        return self.transport.request(
            "POST",
            "/behavior",
            json_body={
                "student_id": student_id,
                "topic": topic,
                "quiz_correct": quiz_correct,
                "response_latency_s": response_latency_s,
                "attention": attention,
                "asked_question": asked_question,
                "saw_slide": saw_slide,
            },
        )

    def update_mastery(
        self, student_id: str, topic: str, correct: bool
    ) -> float:
        result = self.transport.request(
            "POST",
            "/mastery",
            json_body={
                "student_id": student_id,
                "topic": topic,
                "correct": correct,
            },
        )
        value = result.get("mastery")
        if not isinstance(value, (int, float)):
            raise ValueError("memory response did not include a numeric mastery")
        return float(value)


def _number(value: Any, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) else default
