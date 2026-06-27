"""Scenario-based training agents for critical thinking and emergency drills."""

from .agents import (
    CriticalThinkingCoachAgent,
    EmergencyScenarioCoachAgent,
    ForesightPrepAgent,
    LearningBehaviorCoachAgent,
    QuickDecisionAgent,
    SituationalAnalysisAgent,
)
from .models import (
    AgentTurn,
    ScenarioDefinition,
    TrainingAgentRole,
    TrainingEvent,
    TrainingPhase,
    TrainingSessionState,
)
from .roster import PLATFORM_AGENTS, PlatformAgent, agent_roster_dict, list_agents
from .scenarios import BUILTIN_SCENARIOS, get_scenario, list_scenarios
from .session import TrainingSession, TrainingSessionStore

__all__ = [
    "AgentTurn",
    "BUILTIN_SCENARIOS",
    "CriticalThinkingCoachAgent",
    "EmergencyScenarioCoachAgent",
    "ForesightPrepAgent",
    "LearningBehaviorCoachAgent",
    "PLATFORM_AGENTS",
    "PlatformAgent",
    "QuickDecisionAgent",
    "ScenarioDefinition",
    "SituationalAnalysisAgent",
    "TrainingAgentRole",
    "TrainingEvent",
    "TrainingPhase",
    "TrainingSession",
    "TrainingSessionState",
    "TrainingSessionStore",
    "agent_roster_dict",
    "get_scenario",
    "list_agents",
    "list_scenarios",
]
