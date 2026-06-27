"""Scenario-based training agents for critical thinking and emergency drills."""

from .agents import (
    CriticalThinkingCoachAgent,
    EmergencyScenarioCoachAgent,
    ForesightPrepAgent,
    LearningBehaviorCoachAgent,
    QuickDecisionAgent,
    SituationalAnalysisAgent,
)
from .catalog import (
    catalog_meta,
    count_scenarios,
    count_scenarios_for_track,
    get_scenario,
    list_domains,
    list_scenarios,
    list_scenarios_for_track,
    random_scenario,
    reload_catalog,
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
from .tracks import TRAINING_TRACKS, TrainingTrack, get_track, list_tracks, track_to_dict
from .session import TrainingSession, TrainingSessionStore

__all__ = [
    "AgentTurn",
    "catalog_meta",
    "count_scenarios",
    "count_scenarios_for_track",
    "CriticalThinkingCoachAgent",
    "EmergencyScenarioCoachAgent",
    "ForesightPrepAgent",
    "get_scenario",
    "get_track",
    "LearningBehaviorCoachAgent",
    "list_domains",
    "list_scenarios",
    "list_scenarios_for_track",
    "list_tracks",
    "PLATFORM_AGENTS",
    "PlatformAgent",
    "QuickDecisionAgent",
    "random_scenario",
    "reload_catalog",
    "ScenarioDefinition",
    "SituationalAnalysisAgent",
    "TRAINING_TRACKS",
    "track_to_dict",
    "TrainingAgentRole",
    "TrainingEvent",
    "TrainingPhase",
    "TrainingSession",
    "TrainingSessionState",
    "TrainingSessionStore",
    "TrainingTrack",
    "agent_roster_dict",
    "list_agents",
]
