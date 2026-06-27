"""Critical-thinking & emergency-response training sessions (web-facing).

Thin orchestrator wrapper over :mod:`aoep_shared.training_agents`: keeps the live
:class:`TrainingSession` objects and shapes them for the API. Sessions are held
in-process (these are short, interactive drills); the cognitive agents are pure
and deterministic so the loop works offline with no model server.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from aoep_shared.schemas import ClassType
from aoep_shared.training_agents import (
    TrainingSession,
    get_scenario,
    list_scenarios,
)


class TrainingSessions:
    def __init__(self) -> None:
        self._sessions: Dict[str, TrainingSession] = {}

    def list_scenarios(self) -> List[dict]:
        return [s.to_summary() for s in list_scenarios()]

    def start(self, scenario_id: str, class_type: str = "solo") -> TrainingSession:
        scenario = get_scenario(scenario_id)
        if scenario is None:
            raise KeyError(scenario_id)
        try:
            ct = ClassType(class_type)
        except ValueError:
            ct = ClassType.SOLO
        session = TrainingSession(scenario=scenario, class_type=ct)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> TrainingSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def _progress(self, session: TrainingSession) -> dict:
        ids = [p.id for p in session.scenario.phases]
        total = len(ids)
        if session.done:
            index = total
        else:
            index = ids.index(session.current_phase_id) if session.current_phase_id in ids else 0
        return {"phase_index": index, "phases_total": total}

    def view(
        self, session: TrainingSession, *, noticed: Optional[List[str]] = None
    ) -> dict:
        out: dict = {
            "session_id": session.session_id,
            "scenario_id": session.scenario.id,
            "scenario_title": session.scenario.title,
            "domain": session.scenario.domain,
            "class_type": session.class_type.value,
            "done": session.done,
            **self._progress(session),
        }
        if session.done:
            out["brief"] = None
            out["summary"] = session.summary()
        else:
            out["brief"] = session.brief(noticed=noticed).as_dict()
            out["summary"] = None
        return out

    def decide(
        self, session_id: str, option_id: str, *, elapsed_s: float, rationale: str = ""
    ) -> dict:
        session = self.get(session_id)
        outcome = session.decide(option_id, elapsed_s=elapsed_s, rationale=rationale)
        out = outcome.as_dict()
        out["session_id"] = session.session_id
        out.update(self._progress(session))
        out["next_brief"] = (
            None if session.done else session.brief().as_dict()
        )
        out["summary"] = session.summary() if session.done else None
        return out
