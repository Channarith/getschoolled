"""Curriculum service helpers for the unified learnable index."""

from __future__ import annotations

from typing import List

from aoep_shared.learnable import LearnableItem, build_learnable_index

from curriculum.catalog import CatalogStore


def _curriculum_dir() -> str:
    import os
    from pathlib import Path

    env = os.environ.get("CURRICULUM_DIR")
    if env:
        return env
    return str(Path(__file__).resolve().parents[4] / "sample-curriculum")


def build_index_for_store(catalog: CatalogStore, *, locale: str = "en") -> List[LearnableItem]:
    return build_learnable_index(
        catalog_courses=catalog.list_courses(),
        catalog_programs=catalog.list_programs(),
        locale=locale,
        curriculum_dir=_curriculum_dir(),
    )


def find_item(index: List[LearnableItem], *, global_id: str | None = None,
              source_id: str | None = None) -> LearnableItem | None:
    for item in index:
        if global_id and item.id == global_id:
            return item
        if source_id and item.source_id == source_id:
            return item
    return None
