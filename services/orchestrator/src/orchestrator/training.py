"""Orchestrator API for scenario-based training sessions."""

from __future__ import annotations

from typing import List, Optional

from aoep_shared.training_agents import (
    TrainingSessionStore,
    agent_roster_dict,
    catalog_capacity,
    catalog_meta,
    count_scenarios,
    count_scenarios_for_track,
    generate_scenario,
    get_scenario,
    get_track,
    knowledge_overview,
    knowledge_source_list,
    knowledge_store_status,
    list_domains,
    list_families_meta,
    list_scenarios,
    list_scenarios_for_track,
    list_tracks,
    random_procedural_scenario,
    random_scenario,
    search_knowledge,
    track_to_dict,
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


class ScenarioListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    scenarios: List[ScenarioSummary] = Field(default_factory=list)


class CatalogMetaResponse(BaseModel):
    version: int
    generated_at: str
    count: int
    from_packs: int = 0
    domains: dict[str, int] = Field(default_factory=dict)


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
    references: List[dict] = Field(default_factory=list)
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


def catalog_summary() -> CatalogMetaResponse:
    meta = catalog_meta()
    return CatalogMetaResponse(**meta)


def list_scenario_summaries(
    *,
    domain: Optional[str] = None,
    skill: Optional[str] = None,
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> ScenarioListResponse:
    total = count_scenarios(domain=domain, skill=skill, q=q)
    items = list_scenarios(domain=domain, skill=skill, q=q, offset=offset, limit=limit)
    return ScenarioListResponse(
        total=total,
        offset=offset,
        limit=limit,
        scenarios=[
            ScenarioSummary(
                scenario_id=s.scenario_id,
                title=s.title,
                domain=s.domain.value,
                skills=s.skills,
            )
            for s in items
        ],
    )


def list_domain_counts() -> list[dict]:
    return [{"domain": d, "count": n} for d, n in list_domains()]


class TrackSummary(BaseModel):
    track_id: str
    title: str
    description: str
    domains: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    scenario_count: int = 0
    recommended_count: int = 12


class TrackScenarioListResponse(BaseModel):
    track_id: str
    title: str
    total: int
    scenarios: List[ScenarioSummary] = Field(default_factory=list)


def list_track_summaries() -> List[TrackSummary]:
    return [
        TrackSummary(
            **{k: v for k, v in track_to_dict(t).items() if k != "keywords"},
            scenario_count=count_scenarios_for_track(t.track_id),
        )
        for t in list_tracks()
    ]


def track_scenarios(
    track_id: str,
    *,
    offset: int = 0,
    limit: int = 50,
) -> Optional[TrackScenarioListResponse]:
    track = get_track(track_id)
    if track is None:
        return None
    total = count_scenarios_for_track(track_id)
    items = list_scenarios_for_track(track_id, offset=offset, limit=limit)
    return TrackScenarioListResponse(
        track_id=track_id,
        title=track.title,
        total=total,
        scenarios=[
            ScenarioSummary(
                scenario_id=s.scenario_id,
                title=s.title,
                domain=s.domain.value,
                skills=s.skills,
            )
            for s in items
        ],
    )


def pick_random_scenario(
    *,
    domain: Optional[str] = None,
    track_id: Optional[str] = None,
    seed: Optional[int] = None,
) -> Optional[ScenarioSummary]:
    s = random_scenario(domain=domain, track_id=track_id, seed=seed)
    if s is None:
        return None
    return ScenarioSummary(
        scenario_id=s.scenario_id,
        title=s.title,
        domain=s.domain.value,
        skills=s.skills,
    )


class CapacityResponse(BaseModel):
    materialized: int
    procedural_capacity: int
    total_addressable: int
    families: dict[str, int] = Field(default_factory=dict)


class FamilySummary(BaseModel):
    family_id: str
    title: str
    domain: str
    capacity: int
    skills: List[str] = Field(default_factory=list)


class ReferenceFactView(BaseModel):
    fact: str
    source: str
    reference: str
    category: str = "guideline"
    url: str = ""


class GeneratedScenario(BaseModel):
    scenario_id: str
    title: str
    domain: str
    briefing: str
    decision_prompt: str
    decision_time_limit_s: int
    cues: List[dict] = Field(default_factory=list)
    emergency_steps: List[str] = Field(default_factory=list)
    foresight_prompts: List[str] = Field(default_factory=list)
    critical_thinking_prompts: List[str] = Field(default_factory=list)
    debrief_rubric: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    references: List[ReferenceFactView] = Field(default_factory=list)


def _generated_view(s) -> GeneratedScenario:
    return GeneratedScenario(
        scenario_id=s.scenario_id,
        title=s.title,
        domain=s.domain.value,
        briefing=s.briefing,
        decision_prompt=s.decision_prompt,
        decision_time_limit_s=s.decision_time_limit_s,
        cues=[{"cue_id": c.cue_id, "text": c.text, "priority": c.priority} for c in s.cues],
        emergency_steps=s.emergency_steps,
        foresight_prompts=s.foresight_prompts,
        critical_thinking_prompts=s.critical_thinking_prompts,
        debrief_rubric=s.debrief_rubric,
        skills=s.skills,
        references=[
            ReferenceFactView(
                fact=r.fact, source=r.source, reference=r.reference,
                category=r.category, url=r.url,
            )
            for r in s.references
        ],
    )


def capacity_report() -> CapacityResponse:
    return CapacityResponse(**catalog_capacity())


def list_family_summaries() -> List[FamilySummary]:
    return [FamilySummary(**f) for f in list_families_meta()]


def generate_one(family_id: str, index: int) -> Optional[GeneratedScenario]:
    s = generate_scenario(family_id, index)
    if s is None:
        return None
    return _generated_view(s)


def generate_random(
    *, family_id: Optional[str] = None, seed: Optional[int] = None
) -> Optional[GeneratedScenario]:
    s = random_procedural_scenario(family_id=family_id, seed=seed)
    if s is None:
        return None
    return _generated_view(s)


def get_full_scenario(scenario_id: str) -> Optional[GeneratedScenario]:
    s = get_scenario(scenario_id)
    if s is None:
        return None
    return _generated_view(s)


class KnowledgeStoreStatus(BaseModel):
    backend: str
    persistent: bool
    db_path: str = ""
    fts5: bool = False
    count: int = 0
    signature: str = ""


class KnowledgeMetaResponse(BaseModel):
    count: int
    builtin: int = 0
    from_packs: int = 0
    sources: int
    categories: dict[str, int] = Field(default_factory=dict)
    domains: dict[str, int] = Field(default_factory=dict)
    store: KnowledgeStoreStatus | None = None


class GrowthStatusResponse(BaseModel):
    knowledge_facts: int
    scenario_catalog: int
    scenario_capacity: int
    slang_entries: int
    presentation_techniques: int
    content_packs: dict = Field(default_factory=dict)


def growth_status() -> GrowthStatusResponse:
    from aoep_shared.content_packs import pack_summary
    from aoep_shared.presentation_skills import technique_count
    from aoep_shared.slang import lexicon_stats
    from aoep_shared.training_agents import catalog_capacity, catalog_meta, knowledge_overview

    cap = catalog_capacity()
    return GrowthStatusResponse(
        knowledge_facts=knowledge_overview()["count"],
        scenario_catalog=catalog_meta()["count"],
        scenario_capacity=cap.get("total_addressable", 0),
        slang_entries=lexicon_stats()["total"],
        presentation_techniques=technique_count(),
        content_packs=pack_summary(),
    )


class KnowledgeListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    facts: List[ReferenceFactView] = Field(default_factory=list)


def knowledge_meta_view() -> KnowledgeMetaResponse:
    return KnowledgeMetaResponse(**knowledge_overview())


def knowledge_sources_view() -> list[dict]:
    return knowledge_source_list()


def knowledge_store_view() -> KnowledgeStoreStatus:
    return KnowledgeStoreStatus(**knowledge_store_status())


def knowledge_search_view(
    *,
    q: Optional[str] = None,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> KnowledgeListResponse:
    total, items = search_knowledge(
        q=q, domain=domain, category=category, source=source, offset=offset, limit=limit
    )
    return KnowledgeListResponse(
        total=total,
        offset=offset,
        limit=limit,
        facts=[ReferenceFactView(**f) for f in items],
    )


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
