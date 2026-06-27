"""Cognitive training agents for critical thinking & emergency-response drills.

A self-contained, offline-first subsystem that trains *how a person thinks* under
pressure (situational awareness, forecasting/pre-mortem, split-second decisions,
critical reasoning) and adapts to each learner's behavior - e.g. flying a
simulated engine-out approach to an emergency landing.

Public API:
- :func:`run_training_agents_lab` - end-to-end offline drill (CLI/test).
- :class:`TrainingSession` - drive a scenario through the agents.
- :func:`list_scenarios` / :func:`get_scenario` - the built-in scenario registry.
- The five agents in :mod:`.agents`.
"""

from .agents import (
    BehaviorAdaptation,
    CriticalThinkingAgent,
    ForecastingAgent,
    LearningBehaviorAgent,
    PreMortem,
    RapidDecisionAgent,
    RapidDecisionResult,
    ReasoningReview,
    SituationalAwarenessAgent,
    SituationPicture,
    TrainingAgentRole,
)
from .engine import DecisionOutcome, PhaseBrief, TrainingSession
from .lab import TrainingAgentsLabResult, run_training_agents_lab
from .scenario import (
    BUILTIN_SCENARIOS,
    DecisionOption,
    Scenario,
    ScenarioPhase,
    get_scenario,
    list_scenarios,
)

__all__ = [
    "run_training_agents_lab",
    "TrainingAgentsLabResult",
    "TrainingSession",
    "PhaseBrief",
    "DecisionOutcome",
    "Scenario",
    "ScenarioPhase",
    "DecisionOption",
    "BUILTIN_SCENARIOS",
    "list_scenarios",
    "get_scenario",
    "TrainingAgentRole",
    "SituationalAwarenessAgent",
    "SituationPicture",
    "ForecastingAgent",
    "PreMortem",
    "RapidDecisionAgent",
    "RapidDecisionResult",
    "CriticalThinkingAgent",
    "ReasoningReview",
    "LearningBehaviorAgent",
    "BehaviorAdaptation",
]
