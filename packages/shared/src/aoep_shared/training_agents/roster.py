"""Canonical platform agent roster — teaching, content, and training agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class PlatformAgent:
    name: str
    role_id: str
    category: str
    description: str
    status: str = "active"  # active | partial | planned


# Harvester, presenter, chatbot (existing) + new training coaches.
PLATFORM_AGENTS: Tuple[PlatformAgent, ...] = (
    # Content pipeline
    PlatformAgent(
        "Harvester",
        "harvester",
        "content",
        "24/7 crawl, generate, and critique OER courses for the catalog.",
        "active",
    ),
    PlatformAgent(
        "AI Presenter",
        "presenter",
        "teaching",
        "Narrates slides and drives live meeting presentation plans (Meet/Zoom/Teams).",
        "active",
    ),
    PlatformAgent(
        "AI Chatbot / Tutor",
        "chatbot",
        "teaching",
        "Reads meeting chat and answers with RAG-grounded tutoring without interrupting slides.",
        "active",
    ),
    # Core live-class roster
    PlatformAgent(
        "Teaching Director",
        "director",
        "teaching",
        "Lesson state machine; balances teach vs answer vs quiz.",
        "active",
    ),
    PlatformAgent(
        "Assessment",
        "assessment",
        "teaching",
        "Pop quizzes, mastery tracking, and grading feedback.",
        "active",
    ),
    PlatformAgent(
        "Perception",
        "perception",
        "teaching",
        "Consent-gated face recognition and attention scoring.",
        "active",
    ),
    PlatformAgent(
        "Memory / Profile",
        "memory",
        "teaching",
        "Long-term learner profile, mastery graph, and adaptation overlay.",
        "active",
    ),
    # Training coaches (sensitive, awareness-driven)
    PlatformAgent(
        "Learning Behavior Coach",
        "learning_coach",
        "training",
        "Adapts pace and tone to learner signals; sensitive to frustration and wellness.",
        "active",
    ),
    PlatformAgent(
        "Critical Thinking Coach",
        "critical_thinking",
        "training",
        "Socratic probes that build reasoning chains instead of handing out answers.",
        "active",
    ),
    PlatformAgent(
        "Situational Analysis Coach",
        "situational_analysis",
        "training",
        "Reveals scenario cues progressively and trains priority identification.",
        "active",
    ),
    PlatformAgent(
        "Quick Decision Coach",
        "quick_decision",
        "training",
        "Split-minute decision drills under time pressure with structured debrief.",
        "active",
    ),
    PlatformAgent(
        "Foresight / Mental Prep Coach",
        "foresight_prep",
        "training",
        "Forecasting and mental rehearsal before situations unfold.",
        "active",
    ),
    PlatformAgent(
        "Emergency Scenario Coach",
        "emergency_training",
        "training",
        "Emergency procedures (e.g. sim airplane engine-out landing, triage, evacuation).",
        "active",
    ),
)


def list_agents(*, category: str | None = None) -> List[PlatformAgent]:
    if category is None:
        return list(PLATFORM_AGENTS)
    return [a for a in PLATFORM_AGENTS if a.category == category]


def agent_roster_dict() -> List[dict]:
    return [
        {
            "name": a.name,
            "role_id": a.role_id,
            "category": a.category,
            "description": a.description,
            "status": a.status,
        }
        for a in PLATFORM_AGENTS
    ]
