"""Serialize and build the scenario catalog."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .catalog_generators import generate_all_scenarios
from .models import ReferenceFact, ScenarioCue, ScenarioDefinition, ScenarioDomain


def scenario_to_dict(s: ScenarioDefinition) -> dict:
    return {
        "scenario_id": s.scenario_id,
        "title": s.title,
        "domain": s.domain.value,
        "briefing": s.briefing,
        "cues": [
            {"cue_id": c.cue_id, "text": c.text, "priority": c.priority}
            for c in s.cues
        ],
        "decision_prompt": s.decision_prompt,
        "decision_time_limit_s": s.decision_time_limit_s,
        "emergency_steps": s.emergency_steps,
        "foresight_prompts": s.foresight_prompts,
        "critical_thinking_prompts": s.critical_thinking_prompts,
        "debrief_rubric": s.debrief_rubric,
        "skills": s.skills,
        "references": [
            {"fact": r.fact, "source": r.source, "reference": r.reference,
             "category": r.category, "url": r.url}
            for r in s.references
        ],
    }


def scenario_from_dict(raw: dict) -> ScenarioDefinition:
    return ScenarioDefinition(
        scenario_id=raw["scenario_id"],
        title=raw["title"],
        domain=ScenarioDomain.from_value(raw["domain"]),
        briefing=raw["briefing"],
        cues=[
            ScenarioCue(
                cue_id=c["cue_id"],
                text=c["text"],
                priority=c.get("priority", "medium"),
            )
            for c in raw.get("cues", [])
        ],
        decision_prompt=raw.get("decision_prompt", ""),
        decision_time_limit_s=int(raw.get("decision_time_limit_s", 60)),
        emergency_steps=list(raw.get("emergency_steps", [])),
        foresight_prompts=list(raw.get("foresight_prompts", [])),
        critical_thinking_prompts=list(raw.get("critical_thinking_prompts", [])),
        debrief_rubric=list(raw.get("debrief_rubric", [])),
        skills=list(raw.get("skills", [])),
        references=[
            ReferenceFact(
                fact=r["fact"], source=r["source"], reference=r["reference"],
                category=r.get("category", "guideline"), url=r.get("url", ""),
            )
            for r in raw.get("references", [])
        ],
    )


def build_catalog_payload() -> dict:
    scenarios = generate_all_scenarios()
    scenarios.sort(key=lambda s: (s.domain.value, s.scenario_id))
    domains: Dict[str, int] = {}
    for s in scenarios:
        domains[s.domain.value] = domains.get(s.domain.value, 0) + 1
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(scenarios),
        "domains": domains,
        "scenarios": [scenario_to_dict(s) for s in scenarios],
    }


def default_catalog_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "scenario_catalog.json"


def write_catalog(path: Path | None = None) -> dict:
    path = path or default_catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_catalog_payload()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
