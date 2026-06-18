"""AI disclosure / transparency metadata (Trust layer, Phase 1).

A small, serializable record stating that an interaction is AI-driven, which
model/persona produced it, who the human of record is, and that answers are
grounded with citations. Surfaced in the UI (a persistent badge + a public
transparency page) so the platform discloses the AI rather than disguising it -
the baseline trust requirement and aligned with AI-transparency regulation
(e.g. EU AI Act Article 50).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Disclosure(BaseModel):
    is_ai: bool = True
    instructor: str = "AI Instructor"
    model_name: str = "education-base"
    persona: str = "friendly"
    human_of_record: Optional[str] = None
    generated_with: str = "AOEP agentic teaching system"
    grounded_with_citations: bool = True

    def disclosure_line(self) -> str:
        """A one-line, user-facing disclosure string."""
        if not self.is_ai:
            who = self.human_of_record or "a human instructor"
            return f"This class is taught by {who}."
        parts = [
            f"This class is taught by an AI instructor "
            f"(model: {self.model_name}, persona: {self.persona})."
        ]
        if self.grounded_with_citations:
            parts.append("Answers are grounded in the course material with citations.")
        if self.human_of_record:
            parts.append(f"A human of record ({self.human_of_record}) reviews the content.")
        return " ".join(parts)


def disclosure_from_config(
    config,
    *,
    persona: str = "friendly",
    human_of_record: Optional[str] = None,
) -> Disclosure:
    """Build a Disclosure from an AppConfig (uses the configured LLM model)."""
    return Disclosure(
        model_name=getattr(config, "llm_model", "education-base"),
        persona=persona,
        human_of_record=human_of_record,
    )
