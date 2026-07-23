"""Local-only helpers for safe developer extension."""

from __future__ import annotations

from aoep_shared import ProviderFactory, build_factory, load_config


def local_factory(env: dict[str, str] | None = None) -> ProviderFactory:
    """Build providers with ``DEPLOY_MODE=local`` (sandbox payments, offline LLM)."""

    merged = {"DEPLOY_MODE": "local", **(env or {})}
    return build_factory(load_config(env=merged))
