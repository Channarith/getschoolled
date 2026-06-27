"""Orchestrator API for scenario-based training sessions."""

from __future__ import annotations

from typing import List, Optional

from aoep_shared.training_agents import (
    TrainingSessionStore,
    agent_roster_dict,
    list_scenarios,
)
from pydantic import BaseModel, Field


_store = TrainingSessionStore()


def get_training_store() -> TrainingSessionStore:
    return _store


class ScenarioSummary(BaseModel):
    scenario_id: str
    title: str
    domain: str
    skills: List[str] = Field(default_factory=list)


class CreateTrainingSessionRequest(BaseModel):
    scenario_id: str


class TrainingSessionView(BaseModel):
    session_id: str
    scenario_id: str
    title: str
    domain: str
    phase: str
    tick: int
    time_remaining_s: Optional[int] = None
    stress_level: float
    cues_seen: List[str]
    score: Optional[float] = None
    last_coaching: str
    active_agent: Optional[str] = None
    events: List[dict] = Field(default_factory=list)


class AgentTurnView(BaseModel):
    agent: str
    kind: str
    message: str
    meta: dict = Field(default_factory=dict)


class TickResponse(BaseModel):
    session: TrainingSessionView
    turns: List[AgentTurnView] = Field(default_factory=list)


class RespondRequest(BaseModel):
    text: str


class RespondResponse(BaseModel):
    session: TrainingSessionView
    turns: List[AgentTurnView] = Field(default_factory=list)


def _session_view(session) -> TrainingSessionView:
    v = session.to_view()
    return TrainingSessionView(**v)


def _turn_views(turns) -> List[AgentTurnView]:
    return [
        AgentTurnView(agent=t.agent, kind=t.kind, message=t.message, meta=t.meta)
        for t in turns
    ]


def list_scenario_summaries() -> List[ScenarioSummary]:
    return [
        ScenarioSummary(
            scenario_id=s.scenario_id,
            title=s.title,
            domain=s.domain.value,
            skills=s.skills,
        )
        for s in list_scenarios()
    ]


def create_training_session(scenario_id: str):
    return _store.create(scenario_id)


def get_training_session(session_id: str):
    return _store.get(session_id)


def tick_training_session(session_id: str) -> tuple:
    session = _store.get(session_id)
    if session is None:
        return None, None
    turns = session.tick()
    return session, turns


def respond_training_session(session_id: str, text: str) -> tuple:
    session = _store.get(session_id)
    if session is None:
        return None, None
    turns = session.respond(text)
    return session, turns
