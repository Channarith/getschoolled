"""Shared state and types for scenario-based training agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from aoep_shared.adaptive import LearnerSignals
from aoep_shared.learner_adaptation import LearnerAdaptation


class TrainingAgentRole(str, Enum):
    """Specialized coaching agents for sensitive, awareness-driven training."""

    LEARNING_COACH = "learning_coach"
    CRITICAL_THINKING = "critical_thinking"
    SITUATIONAL_ANALYSIS = "situational_analysis"
    QUICK_DECISION = "quick_decision"
    FORESIGHT_PREP = "foresight_prep"
    EMERGENCY_TRAINING = "emergency_training"


class TrainingPhase(str, Enum):
    BRIEFING = "briefing"
    SITUATIONAL_SCAN = "situational_scan"
    DECISION = "decision"
    FORESIGHT = "foresight"
    DEBRIEF = "debrief"
    DONE = "done"


class ScenarioDomain(str, Enum):
    AVIATION = "aviation"
    MEDICAL = "medical"
    FIRE_SAFETY = "fire_safety"
    MARITIME = "maritime"
    CYBERSECURITY = "cybersecurity"
    INDUSTRIAL = "industrial"
    TRANSPORT = "transport"
    WEATHER = "weather"
    SECURITY = "security"
    LEADERSHIP = "leadership"
    EDUCATION = "education"
    HOSPITALITY = "hospitality"
    CONSTRUCTION = "construction"
    AGRICULTURE = "agriculture"
    TACTICAL = "tactical"
    FINANCE = "finance"
    MEDIA_LITERACY = "media_literacy"
    CHILD_SAFETY = "child_safety"
    MENTAL_HEALTH = "mental_health"
    SPORTS = "sports"
    GENERAL = "general"
    NURSING = "nursing"
    HAZMAT = "hazmat"
    ENERGY = "energy"
    SEARCH_RESCUE = "search_rescue"
    LEGAL = "legal"
    PARENTING = "parenting"
    CONFLICT = "conflict"
    DISASTER_RECOVERY = "disaster_recovery"
    AVIATION_IFR = "aviation_ifr"
    WILDERNESS = "wilderness"
    WATER_SAFETY = "water_safety"
    FOOD_SAFETY = "food_safety"
    RETAIL = "retail"
    MINING = "mining"
    PHARMA = "pharma"
    SOCIAL_WORK = "social_work"
    TELECOM = "telecom"

    @classmethod
    def from_value(cls, raw: str) -> ScenarioDomain:
        try:
            return cls(raw)
        except ValueError:
            return cls.GENERAL


@dataclass
class TrainingEvent:
    agent: str
    kind: str
    detail: str
    meta: dict = field(default_factory=dict)


@dataclass
class ScenarioCue:
    """A situational signal the learner may notice (or miss)."""

    cue_id: str
    text: str
    priority: str = "medium"  # low | medium | high | critical
    revealed: bool = False


@dataclass
class ScenarioDefinition:
    scenario_id: str
    title: str
    domain: ScenarioDomain
    briefing: str
    cues: List[ScenarioCue] = field(default_factory=list)
    decision_prompt: str = ""
    decision_time_limit_s: int = 60
    emergency_steps: List[str] = field(default_factory=list)
    foresight_prompts: List[str] = field(default_factory=list)
    critical_thinking_prompts: List[str] = field(default_factory=list)
    debrief_rubric: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)


@dataclass
class TrainingSessionState:
    """Blackboard for a scenario training session."""

    scenario_id: str
    phase: TrainingPhase = TrainingPhase.BRIEFING
    tick: int = 0
    time_remaining_s: Optional[int] = None
    cues_seen: List[str] = field(default_factory=list)
    learner_responses: List[str] = field(default_factory=list)
    decisions_made: List[str] = field(default_factory=list)
    stress_level: float = 0.0
    signals: LearnerSignals = field(default_factory=LearnerSignals)
    adaptation: LearnerAdaptation = field(default_factory=LearnerAdaptation)
    events: List[TrainingEvent] = field(default_factory=list)
    active_agent: Optional[str] = None
    last_coaching: str = ""
    score: Optional[float] = None

    def log(self, agent: TrainingAgentRole | str, kind: str, detail: str, **meta) -> None:
        role = agent.value if isinstance(agent, TrainingAgentRole) else agent
        self.events.append(TrainingEvent(agent=role, kind=kind, detail=detail, meta=meta))
        self.active_agent = role
        if kind in ("coach", "prompt", "nudge", "emergency", "foresight", "decision"):
            self.last_coaching = detail


@dataclass
class AgentTurn:
    """One agent utterance during a training tick."""

    agent: str
    kind: str
    message: str
    meta: Dict[str, object] = field(default_factory=dict)
