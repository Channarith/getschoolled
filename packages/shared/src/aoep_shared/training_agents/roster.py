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
        "Theodore (AI Presenter)",
        "presenter",
        "teaching",
        "Named AI professor. Narrates slides and drives live presentation plans "
        "(Meet/Zoom/Teams), teaching with strategies back-propagated from top "
        "online instructors: curiosity hooks, first-principles reasoning, story, "
        "everyday relevance, comprehension checks, and a memorable close. Rehearses "
        "and refines each take via aoep_shared.theodore.",
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
    # Cognitive training suite (consolidated from the cognitive_trainer engines;
    # served via /api/cognitive/*; richer pedagogy: Bloom, OODA/DECIDE, AAR sims).
    PlatformAgent(
        "Cognitive Coach",
        "cognitive_coach",
        "cognitive",
        "Detects cross-session learning patterns and routes the next session by wellness.",
        "active",
    ),
    PlatformAgent(
        "Critical Thinking Trainer",
        "critical_thinking_trainer",
        "cognitive",
        "Bloom-level Socratic questioning, fallacy detection, and argument mapping.",
        "active",
    ),
    PlatformAgent(
        "Situational Awareness Trainer",
        "situational_awareness_trainer",
        "cognitive",
        "OODA and DECIDE framework drills with cue-recognition scoring.",
        "active",
    ),
    PlatformAgent(
        "Rapid Decision Trainer",
        "rapid_decision_trainer",
        "cognitive",
        "Recognition-primed drill library with pressure tiers and after-decision review.",
        "active",
    ),
    PlatformAgent(
        "Emergency Scenario Trainer",
        "emergency_scenario_trainer",
        "cognitive",
        "Branching emergency simulations with phase trees and After-Action Review.",
        "active",
    ),
    PlatformAgent(
        "Mental Readiness Trainer",
        "mental_readiness_trainer",
        "cognitive",
        "Pre-mortems, mental rehearsal, threat-and-error management, stress inoculation.",
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
