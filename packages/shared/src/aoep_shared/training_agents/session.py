"""Training session orchestrator — coordinates coaching agents on each tick."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .agents import (
    CriticalThinkingCoachAgent,
    EmergencyScenarioCoachAgent,
    ForesightPrepAgent,
    LearningBehaviorCoachAgent,
    QuickDecisionAgent,
    SituationalAnalysisAgent,
)
from .models import AgentTurn, TrainingPhase, TrainingSessionState
from .scenarios import ScenarioDefinition, get_scenario


@dataclass
class TrainingSession:
    """One learner's scenario training run."""

    session_id: str
    scenario: ScenarioDefinition
    state: TrainingSessionState
    learning_coach: LearningBehaviorCoachAgent = field(default_factory=LearningBehaviorCoachAgent)
    critical_thinking: CriticalThinkingCoachAgent = field(default_factory=CriticalThinkingCoachAgent)
    situational: SituationalAnalysisAgent = field(default_factory=SituationalAnalysisAgent)
    quick_decision: QuickDecisionAgent = field(default_factory=QuickDecisionAgent)
    foresight: ForesightPrepAgent = field(default_factory=ForesightPrepAgent)
    emergency: EmergencyScenarioCoachAgent = field(default_factory=EmergencyScenarioCoachAgent)

    @classmethod
    def start(cls, scenario_id: str, *, session_id: Optional[str] = None) -> TrainingSession:
        scenario = get_scenario(scenario_id)
        if scenario is None:
            raise ValueError(f"unknown scenario: {scenario_id}")
        sid = session_id or str(uuid.uuid4())
        state = TrainingSessionState(scenario_id=scenario_id)
        return cls(session_id=sid, scenario=scenario, state=state)

    def tick(self) -> List[AgentTurn]:
        """Advance one step; agents speak in priority order (one turn per tick)."""
        self.state.tick += 1
        turns: List[AgentTurn] = []

        for agent_fn in (
            lambda: self.emergency.tick(self.state, self.scenario),
            lambda: self.quick_decision.tick(self.state, self.scenario),
            lambda: self.situational.tick(self.state, self.scenario),
            lambda: self.critical_thinking.tick(self.state, self.scenario),
            lambda: self.learning_coach.tick(self.state),
            lambda: self.foresight.tick(self.state, self.scenario),
        ):
            turn = agent_fn()
            if turn:
                turns.append(turn)
                return turns

        if self.state.phase is TrainingPhase.DONE:
            return turns
        return turns

    def respond(self, text: str) -> List[AgentTurn]:
        """Process a learner message; may trigger coaching follow-ups."""
        self.state.learner_responses.append(text)
        turns: List[AgentTurn] = []

        coach = self.learning_coach.on_response(self.state, text)
        if coach:
            turns.append(coach)

        phase = self.state.phase
        if phase is TrainingPhase.SITUATIONAL_SCAN:
            t = self.situational.on_scan_response(self.state, text, self.scenario)
            if t:
                turns.append(t)
        elif phase is TrainingPhase.DECISION:
            turns.append(self.quick_decision.on_decision(self.state, text, self.scenario))
        elif phase is TrainingPhase.FORESIGHT:
            turns.append(self.foresight.on_forecast(self.state, text))
        elif phase in (TrainingPhase.DEBRIEF, TrainingPhase.DONE):
            turns.append(
                self.critical_thinking.evaluate_response(self.state, text, self.scenario)
            )

        return turns

    def to_view(self) -> dict:
        return {
            "session_id": self.session_id,
            "scenario_id": self.scenario.scenario_id,
            "title": self.scenario.title,
            "domain": self.scenario.domain.value,
            "phase": self.state.phase.value,
            "tick": self.state.tick,
            "time_remaining_s": self.state.time_remaining_s,
            "stress_level": round(self.state.stress_level, 2),
            "cues_seen": list(self.state.cues_seen),
            "score": self.state.score,
            "last_coaching": self.state.last_coaching,
            "active_agent": self.state.active_agent,
            "references": [
                {"fact": r.fact, "source": r.source, "reference": r.reference,
                 "category": r.category, "url": r.url}
                for r in self.scenario.references
            ],
            "events": [
                {"agent": e.agent, "kind": e.kind, "detail": e.detail, "meta": e.meta}
                for e in self.state.events[-20:]
            ],
        }


class TrainingSessionStore:
    """In-memory store for training sessions (orchestrator API)."""

    def __init__(self) -> None:
        self._sessions: Dict[str, TrainingSession] = {}

    def create(self, scenario_id: str) -> TrainingSession:
        session = TrainingSession.start(scenario_id)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Optional[TrainingSession]:
        return self._sessions.get(session_id)

    def list_ids(self) -> List[str]:
        return list(self._sessions.keys())
