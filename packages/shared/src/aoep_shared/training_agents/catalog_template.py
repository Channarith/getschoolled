"""Shared helpers for building scenario catalogs at scale."""

from __future__ import annotations

from itertools import product
from typing import Iterator, List, Optional, Sequence, Tuple, Optional, Sequence, Tuple

from .models import ScenarioCue, ScenarioDefinition, ScenarioDomain


def _cue(cid: str, text: str, priority: str = "medium") -> ScenarioCue:
    return ScenarioCue(cue_id=cid, text=text, priority=priority)


def _slug(*parts: str) -> str:
    return "_".join(
        p.lower().replace(" ", "_").replace("/", "_").replace("'", "")[:40]
        for p in parts if p
    )[:80]


def _default_cues(code: str, detail: str, setting: str) -> List[ScenarioCue]:
    return [
        _cue("event", detail, "critical"),
        _cue("setting", setting, "medium"),
    ]


def gen_cross_product(
    *,
    domain: ScenarioDomain,
    id_prefix: str,
    events: Sequence[Tuple[str, str, str]],
    settings: Sequence[Tuple[str, str]],
    briefing_fn,
    cues_fn=None,
    decision_prompt: str = "What are your priority actions in the next 60 seconds?",
    decision_time_limit_s: int = 60,
    emergency_steps: Optional[List[str]] = None,
    foresight_prompts: Optional[List[str]] = None,
    critical_thinking_prompts: Optional[List[str]] = None,
    debrief_rubric: Optional[List[str]] = None,
    skills: Optional[List[str]] = None,
    legacy_id: Optional[str] = None,
    legacy_match: Optional[Tuple[str, str]] = None,
) -> Iterator[ScenarioDefinition]:
    """Generate scenarios from event × setting cross-product."""
    cue_builder = cues_fn or _default_cues
    legacy_pinned = False
    for (code, label, detail), (setting_code, setting_desc) in product(events, settings):
        if (
            not legacy_pinned
            and legacy_id
            and legacy_match
            and code == legacy_match[0]
            and setting_code == legacy_match[1]
        ):
            sid = legacy_id
            legacy_pinned = True
        else:
            sid = _slug(id_prefix, code, setting_code)
        yield ScenarioDefinition(
            scenario_id=sid,
            title=f"{label} — {setting_desc}",
            domain=domain,
            briefing=briefing_fn(label, detail, setting_desc),
            cues=cue_builder(code, detail, setting_desc),
            decision_prompt=decision_prompt,
            decision_time_limit_s=decision_time_limit_s,
            emergency_steps=emergency_steps or [],
            foresight_prompts=foresight_prompts or [],
            critical_thinking_prompts=critical_thinking_prompts or [],
            debrief_rubric=debrief_rubric or [],
            skills=skills or [domain.value, "situational-analysis", "critical-thinking"],
        )
