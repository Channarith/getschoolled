"""Load and query the scenario catalog (400+ built-in situations)."""

from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .catalog_builder import default_catalog_path, scenario_from_dict
from .models import ScenarioDefinition, ScenarioDomain
from .tracks import TrainingTrack, get_track, list_tracks


@lru_cache(maxsize=1)
def _load_raw_catalog() -> dict:
    path = default_catalog_path()
    if not path.is_file():
        from .catalog_builder import write_catalog

        write_catalog(path)
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_scenarios() -> Dict[str, ScenarioDefinition]:
    raw = _load_raw_catalog()
    return {
        item["scenario_id"]: scenario_from_dict(item)
        for item in raw.get("scenarios", [])
    }


def catalog_meta() -> dict:
    raw = _load_raw_catalog()
    return {
        "version": raw.get("version", 1),
        "generated_at": raw.get("generated_at", ""),
        "count": raw.get("count", len(_load_scenarios())),
        "domains": raw.get("domains", {}),
    }


def list_scenarios(
    *,
    domain: Optional[str] = None,
    skill: Optional[str] = None,
    q: Optional[str] = None,
    offset: int = 0,
    limit: Optional[int] = None,
) -> List[ScenarioDefinition]:
    items = list(_load_scenarios().values())
    if domain:
        items = [s for s in items if s.domain.value == domain]
    if skill:
        skill_l = skill.lower()
        items = [s for s in items if skill_l in [sk.lower() for sk in s.skills]]
    if q:
        ql = q.lower()
        items = [
            s for s in items
            if ql in s.title.lower()
            or ql in s.briefing.lower()
            or ql in s.scenario_id.lower()
        ]
    items.sort(key=lambda s: (s.domain.value, s.scenario_id))
    if offset:
        items = items[offset:]
    if limit is not None:
        items = items[:limit]
    return items


def count_scenarios(
    *,
    domain: Optional[str] = None,
    skill: Optional[str] = None,
    q: Optional[str] = None,
) -> int:
    return len(list_scenarios(domain=domain, skill=skill, q=q, offset=0, limit=None))


def get_scenario(scenario_id: str) -> Optional[ScenarioDefinition]:
    found = _load_scenarios().get(scenario_id)
    if found is not None:
        return found
    # Fall back to deterministic procedural generation for <family>__<index> ids.
    from .procedural import resolve_procedural

    return resolve_procedural(scenario_id)


def catalog_capacity() -> dict:
    """Total addressable scenarios — materialized plus procedurally generable."""
    from .procedural import capacity_by_family, total_capacity

    materialized = len(_load_scenarios())
    proc_total = total_capacity()
    return {
        "materialized": materialized,
        "procedural_capacity": proc_total,
        "total_addressable": materialized + proc_total,
        "families": capacity_by_family(),
    }


def list_families_meta() -> List[dict]:
    from .procedural import list_families

    return [
        {
            "family_id": f.family_id,
            "title": f.title,
            "domain": f.domain.value,
            "capacity": f.capacity,
            "skills": list(f.skills),
        }
        for f in list_families()
    ]


def generate_scenario(family_id: str, index: int) -> Optional[ScenarioDefinition]:
    from .procedural import generate

    return generate(family_id, index)


def random_procedural_scenario(
    *,
    family_id: Optional[str] = None,
    seed: Optional[int] = None,
) -> Optional[ScenarioDefinition]:
    from .procedural import FAMILIES, generate, list_families

    rng = random.Random(seed)
    families = [FAMILIES[family_id]] if family_id in FAMILIES else list_families()
    if not families:
        return None
    fam = rng.choice(families)
    return generate(fam.family_id, rng.randrange(fam.capacity))


def list_domains() -> List[Tuple[str, int]]:
    meta = catalog_meta()
    domains = meta.get("domains", {})
    return sorted(domains.items(), key=lambda x: (-x[1], x[0]))


def reload_catalog() -> None:
    """Clear caches after catalog rebuild (tests)."""
    _load_raw_catalog.cache_clear()
    _load_scenarios.cache_clear()


def _matches_track(s: ScenarioDefinition, track: TrainingTrack) -> bool:
    if track.domains and s.domain.value in track.domains:
        return True
    skill_set = {sk.lower() for sk in s.skills}
    if track.skills and any(sk.lower() in skill_set for sk in track.skills):
        return True
    text = f"{s.title} {s.briefing} {s.scenario_id}".lower()
    if track.keywords and any(kw.lower() in text for kw in track.keywords):
        return True
    return False


def list_scenarios_for_track(
    track_id: str,
    *,
    offset: int = 0,
    limit: Optional[int] = None,
) -> List[ScenarioDefinition]:
    track = get_track(track_id)
    if track is None:
        return []
    items = [s for s in _load_scenarios().values() if _matches_track(s, track)]
    items.sort(key=lambda s: (s.domain.value, s.scenario_id))
    if offset:
        items = items[offset:]
    if limit is not None:
        items = items[:limit]
    return items


def count_scenarios_for_track(track_id: str) -> int:
    track = get_track(track_id)
    if track is None:
        return 0
    return sum(1 for s in _load_scenarios().values() if _matches_track(s, track))


def random_scenario(
    *,
    domain: Optional[str] = None,
    track_id: Optional[str] = None,
    seed: Optional[int] = None,
) -> Optional[ScenarioDefinition]:
    if track_id:
        pool = list_scenarios_for_track(track_id)
    else:
        pool = list_scenarios(domain=domain, limit=None)
    if not pool:
        return None
    rng = random.Random(seed)
    return rng.choice(pool)
