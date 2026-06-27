"""Scenario-based training agents for critical thinking and emergency drills."""

from .agents import (
    CriticalThinkingCoachAgent,
    EmergencyScenarioCoachAgent,
    ForesightPrepAgent,
    LearningBehaviorCoachAgent,
    QuickDecisionAgent,
    SituationalAnalysisAgent,
)
from .catalog import catalog_meta, count_scenarios, get_scenario, list_domains, list_scenarios, reload_catalog
from .models import (
    AgentTurn,
    ScenarioDefinition,
    TrainingAgentRole,
    TrainingEvent,
    TrainingPhase,
    TrainingSessionState,
)
from .roster import PLATFORM_AGENTS, PlatformAgent, agent_roster_dict, list_agents
from .scenarios import catalog_meta, count_scenarios, list_domains, list_scenarios
from .session import TrainingSession, TrainingSessionStore

__all__ = [
    "AgentTurn",
    "catalog_meta",
    "count_scenarios",
    "CriticalThinkingCoachAgent",
    "EmergencyScenarioCoachAgent",
    "ForesightPrepAgent",
    "get_scenario",
    "LearningBehaviorCoachAgent",
    "list_domains",
    "list_scenarios",
    "PLATFORM_AGENTS",
    "PlatformAgent",
    "QuickDecisionAgent",
    "reload_catalog",
    "ScenarioDefinition",
    "SituationalAnalysisAgent",
    "TrainingAgentRole",
    "TrainingEvent",
    "TrainingPhase",
    "TrainingSession",
    "TrainingSessionState",
    "TrainingSessionStore",
    "agent_roster_dict",
    "list_agents",
]
