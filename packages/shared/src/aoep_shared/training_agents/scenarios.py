"""Built-in scenario definitions — loads the full catalog (400+ situations)."""

from __future__ import annotations

from .catalog import (
    catalog_meta,
    count_scenarios,
    get_scenario,
    list_domains,
    list_scenarios,
    reload_catalog,
)
from .models import ScenarioDefinition

__all__ = [
    "catalog_meta",
    "count_scenarios",
    "get_scenario",
    "list_domains",
    "list_scenarios",
    "reload_catalog",
    "ScenarioDefinition",
]
